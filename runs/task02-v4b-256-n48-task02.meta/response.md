breaker_state.py
```python
"""Breaker states authored by caller policy layers."""

from enum import Enum, auto


class BreakerState(Enum):
    """
    The three breaker states used by callers and subscribers.

    These values are authored by the caller's policy layer and carried through
    CallContext. The breaker's failure path does not decide them.
    """

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


BreakerState.CLOSED.__doc__ = (
    "The caller's policy considers the breaker closed. Calls are allowed and "
    "failures may accumulate."
)
BreakerState.OPEN.__doc__ = (
    "The caller's policy considers the breaker open. Calls are expected to be "
    "rejected or bypassed."
)
BreakerState.HALF_OPEN.__doc__ = (
    "The caller's policy considers the breaker half-open. Trial calls are being "
    "allowed to probe recovery."
)
```

call_context.py
```python
"""Immutable description of a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """
    Immutable context for one downstream call attempt.

    caller_state is caller-authored and must be delivered to subscribers
    unchanged. The breaker does not filter, remap, or reinterpret it.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState
```

breaker_events.py
```python
"""Subscriber contract for circuit breaker events."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """
    Callback signatures the module-level NOTIFIER object must support.

    The context passed to every callback is the same CallContext supplied to
    the breaker method. caller_state is not filtered, remapped, or reinterpreted.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Called after an accepted failure has incremented the breaker's failure count.

        Guarantees:
        - failure_count is the post-increment failure count.
        - threshold is the breaker's configured failure threshold.
        - context is the full CallContext supplied to record_failure.
        - context.caller_state is unchanged.
        - If this failure causes the breaker to transition to OPEN,
          emit_breaker_opened will be emitted after this callback.
        """

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Called after an accepted success has been processed.

        Guarantees:
        - current_state is the breaker's state after any reset caused by this
          success.
        - If the breaker was not open, its failure count has already been reset
          to zero before this callback.
        - context is the full CallContext supplied to record_success.
        - context.caller_state is unchanged.
        """

    def emit_breaker_opened(self, breaker_name: str, context: CallContext) -> None:
        """
        Called exactly once for a transition to OPEN.

        Guarantees:
        - The breaker state has already been mutated to OPEN before this callback.
        - It is emitted after emit_call_failed for the failure that caused the
          transition.
        - It is never emitted for a failure recorded while the breaker is already
          open.
        - context is the full CallContext supplied to record_failure.
        - context.caller_state is unchanged.
        """


NOTIFIER: Notifier
```

circuit_breaker.py
```python
"""Production circuit breaker that notifies subscribers via NOTIFIER."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """
    Circuit breaker that records call outcomes and emits events through NOTIFIER.

    The breaker holds no references to any other system. NOTIFIER is its sole
    point of contact. It never changes CallContext.caller_state.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Initialize a circuit breaker.

        Args:
            name: Breaker name passed to subscriber callbacks.
            failure_threshold: Number of failures that transitions the breaker to
                OPEN.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record a failed downstream call.

        If the breaker is already OPEN, the call is ignored entirely. If
        duration_ms is negative, the context is dropped with a warning.
        Otherwise, the failure count is incremented. If the threshold is reached,
        the breaker transitions to OPEN before any notification is emitted.

        Args:
            context: Immutable context for the failed call.
        """
        if self._state is BreakerState.OPEN:
            return

        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropped failure context with negative "
                f"duration_ms={context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        self._failure_count += 1
        opened_now = self._failure_count >= self._failure_threshold
        if opened_now:
            self._state = BreakerState.OPEN

        failure_count = self._failure_count
        notifier = breaker_events.NOTIFIER
        notifier.emit_call_failed(
            self._name,
            context,
            failure_count,
            self._failure_threshold,
        )

        if opened_now:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record a successful downstream call.

        If duration_ms is negative, the context is dropped with a warning.
        Otherwise, if the breaker is not OPEN, its failure count is reset to zero
        before notification. The success event is always emitted for valid input.

        Args:
            context: Immutable context for the successful call.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropped success context with negative "
                f"duration_ms={context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        current_state = self._state
        notifier = breaker_events.NOTIFIER
        notifier.emit_call_succeeded(self._name, context, current_state)

    def reset(self) -> None:
        """
        Return the breaker to CLOSED with a zero failure count.

        This emits no events.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED
```
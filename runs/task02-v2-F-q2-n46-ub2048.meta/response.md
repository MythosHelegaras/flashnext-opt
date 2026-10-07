breaker_state.py
```python
"""Enumeration of breaker states authored by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """The caller's view of circuit breaker state.

    These values are authored by the caller's policy layer. The breaker does
    not decide or reinterpret them in its failure path.
    """

    CLOSED = auto()
    """The caller considers the breaker closed and calls are permitted."""

    OPEN = auto()
    """The caller considers the breaker open and calls are not permitted."""

    HALF_OPEN = auto()
    """The caller considers the breaker half-open and trial calls are permitted."""
```

call_context.py
```python
"""Immutable description of a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable context for one downstream call attempt.

    Attributes:
        duration_ms: How long the call took, in milliseconds.
        endpoint: The target endpoint, or None for anonymous calls.
        caller_state: The caller's view of breaker state when the call was issued.
    """

    duration_ms: int
    """How long the call took, in milliseconds."""

    endpoint: str | None
    """The target endpoint, or None for anonymous calls."""

    caller_state: BreakerState
    """The caller's view of breaker state when the call was issued."""
```

breaker_events.py
```python
"""Subscriber contract for circuit breaker events.

This module declares the callback signatures a notifier must support. It does
not implement a notifier. The host application is expected to assign a
module-level ``NOTIFIER`` object before the breaker emits events.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CallFailedCallback(Protocol):
    """Callback signature for a recorded call failure."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Receive a failure event.

        Guarantees:
        - The event is emitted only after the breaker's internal failure count
          has been incremented.
        - If the failure caused the breaker to transition to OPEN, the internal
          state is already OPEN before this callback is invoked.
        - ``context`` is the exact ``CallContext`` object passed to
          ``CircuitBreaker.record_failure``. Its ``caller_state`` is unchanged.
        - ``failure_count`` is the post-increment failure count.
        - ``threshold`` is the configured failure threshold.
        """
        ...


class CallSucceededCallback(Protocol):
    """Callback signature for a recorded call success."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Receive a success event.

        Guarantees:
        - The event is emitted after any state mutation caused by the success.
        - If the breaker was not OPEN, the failure count has already been reset
          to zero before this callback is invoked.
        - If the breaker was OPEN, no failure-count mutation occurs.
        - ``context`` is the exact ``CallContext`` object passed to
          ``CircuitBreaker.record_success``. Its ``caller_state`` is unchanged.
        - ``current_state`` is the breaker's internal state after the success
          mutation.
        """
        ...


class BreakerOpenedCallback(Protocol):
    """Callback signature for a breaker transition to OPEN."""

    def __call__(self, breaker_name: str, context: CallContext) -> None:
        """Receive a breaker-opened event.

        Guarantees:
        - The event is emitted exactly once per transition to OPEN.
        - The event is emitted after the breaker's internal state is already
          OPEN.
        - The event is not emitted if the breaker was already OPEN before the
          failure was recorded.
        - ``context`` is the exact ``CallContext`` object passed to
          ``CircuitBreaker.record_failure``. Its ``caller_state`` is unchanged.
        """
        ...


class Notifier(Protocol):
    """Notifier object contract used by ``CircuitBreaker``."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Emit a call failure event.

        Guarantees are documented on ``CallFailedCallback``.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Emit a call success event.

        Guarantees are documented on ``CallSucceededCallback``.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Emit a breaker-opened event.

        Guarantees are documented on ``BreakerOpenedCallback``.
        """
        ...


# The host application assigns this module-level object. It is intentionally
# not implemented here.
NOTIFIER: Notifier
```

circuit_breaker.py
```python
"""Production circuit breaker that notifies through breaker_events.NOTIFIER."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """A small circuit breaker that reports events through ``NOTIFIER``.

    The breaker holds no references to any other system. Its sole external
    contact is the module-level ``NOTIFIER`` object declared in
    ``breaker_events``.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Create a closed breaker with a zero failure count."""
        self._name = name
        self._failure_threshold = failure_threshold
        self._state = BreakerState.CLOSED
        self._failure_count = 0

    def record_failure(self, context: CallContext) -> None:
        """Record a failed call and notify subscribers.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning before any state change or notification. Failures recorded
        while the breaker is already OPEN are ignored entirely.

        The internal failure count is incremented before any event is emitted.
        If the threshold is reached, the state is set to OPEN before the first
        event is emitted, so reentrant calls observe the post-mutation state.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: CallContext.duration_ms must be non-negative; "
                f"got {context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        opened_now = False
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            opened_now = True

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )
        if opened_now:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful call and notify subscribers.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning before any state change or notification. A success always emits
        ``call_succeeded``. If the breaker is not OPEN, the failure count is
        reset before the event is emitted. If the breaker is OPEN, the failure
        count is left unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: CallContext.duration_ms must be non-negative; "
                f"got {context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """Return the breaker to CLOSED with a zero failure count.

        This method emits no events.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0
```
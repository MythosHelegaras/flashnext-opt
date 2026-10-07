## breaker_state.py

```python
"""Breaker state enum supplied by the caller's policy layer."""

from enum import Enum


class BreakerState(Enum):
    """States authored by the caller's policy layer.

    These values are supplied by the caller. The breaker's failure path must
    not decide, filter, remap, or reinterpret them.
    """

    CLOSED = 1
    OPEN = 2
    HALF_OPEN = 3


BreakerState.CLOSED.__doc__ = """
The caller's policy currently treats the breaker as closed.
"""

BreakerState.OPEN.__doc__ = """
The caller's policy currently treats the breaker as open.
"""

BreakerState.HALF_OPEN.__doc__ = """
The caller's policy currently treats the breaker as half-open.
"""
```

## call_context.py

```python
"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one downstream call attempt.

    Attributes:
        duration_ms: How long the call took, in milliseconds.
        endpoint: Target endpoint, or None for anonymous calls.
        caller_state: Caller's view of breaker state when the call was issued.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState
```

## breaker_events.py

```python
"""Subscriber contract for circuit breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Callback contract that the module-level NOTIFIER must satisfy."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify subscribers that an accepted failure has been recorded.

        Guarantees:
        - Called only after the breaker's failure count has been incremented.
        - `context` is the exact CallContext passed to record_failure. The
          breaker does not mutate, filter, remap, or reinterpret
          `context.caller_state`.
        - `failure_count` is the post-mutation failure count for this failure.
        - `threshold` is the breaker's configured failure threshold.
        - Not called for invalid contexts with negative duration_ms.
        - Not called for failures received while the breaker is already open.
        - May be called for the failure that causes the breaker to transition
          to open. In that case, the open guard is already in its
          post-mutation state before this callback runs.
        - For a failure that causes the transition, this callback is emitted
          before emit_breaker_opened.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify subscribers that an accepted success has been recorded.

        Guarantees:
        - Called after any success mutation. If the breaker is not open, the
          failure count has already been reset to zero before this callback
          runs.
        - If the breaker is open, the failure count is not reset.
        - `context` is the exact CallContext passed to record_success,
          unchanged.
        - `current_state` is `context.caller_state`, unchanged. It is the
          caller's state, not a breaker-derived state.
        - Not called for invalid contexts with negative duration_ms.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify subscribers that the breaker has transitioned to open.

        Guarantees:
        - Called exactly once per transition from not-open to open.
        - Not called while the breaker is already open.
        - Called after the open guard is set, so reentrant record_failure calls
          are ignored.
        - `context` is the CallContext of the failure that caused the
          transition, unchanged.
        - Called after emit_call_failed for the same failure.
        """
        ...


# The concrete notifier object must be assigned to this module-level name
# before CircuitBreaker emits events.
NOTIFIER: Notifier
```

## circuit_breaker.py

```python
"""Circuit breaker that records call outcomes and notifies NOTIFIER."""

import warnings

import breaker_events
from call_context import CallContext


class CircuitBreaker:
    """Records downstream call outcomes and emits breaker events.

    The breaker maintains only a failure count and an open flag. It does not
    maintain or decide BreakerState values; CallContext.caller_state is passed
    through to subscribers unchanged. NOTIFIER is the sole point of contact.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize a closed breaker.

        Args:
            name: Name identifying the breaker in notifications.
            failure_threshold: Number of recorded failures that causes the
                breaker to open.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._is_open: bool = False

    def record_failure(self, context: CallContext) -> None:
        """Record a downstream failure.

        If duration_ms is negative, the context is dropped with a warning and
        no state mutation or notification occurs.

        If the breaker is already open, the failure is ignored entirely.

        Otherwise, the failure count is incremented first. If the count reaches
        the threshold, the open guard is set before any notification. The full
        context is emitted unchanged, followed by breaker_opened if this call
        caused the transition.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CircuitBreaker {self._name!r}: dropping CallContext with "
                f"negative duration_ms={context.duration_ms!r}",
                stacklevel=2,
            )
            return

        if self._is_open:
            return

        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._is_open = True

        transitioned_to_open = self._is_open

        notifier: breaker_events.Notifier = breaker_events.NOTIFIER
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if transitioned_to_open:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a downstream success.

        If duration_ms is negative, the context is dropped with a warning and
        no state mutation or notification occurs.

        If the breaker is not open, the failure count is reset to zero before
        notification. If the breaker is open, the failure count is not reset.
        The full context and its unchanged caller_state are emitted.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CircuitBreaker {self._name!r}: dropping CallContext with "
                f"negative duration_ms={context.duration_ms!r}",
                stacklevel=2,
            )
            return

        if not self._is_open:
            self._failure_count = 0

        notifier: breaker_events.Notifier = breaker_events.NOTIFIER
        notifier.emit_call_succeeded(
            self._name,
            context,
            context.caller_state,
        )

    def reset(self) -> None:
        """Return the breaker to closed with a zero failure count.

        No notifications are emitted.
        """
        self._is_open = False
        self._failure_count = 0
```
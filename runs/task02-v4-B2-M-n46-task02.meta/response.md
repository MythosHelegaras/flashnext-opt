breaker_state.py
```python
"""Breaker states authored by caller policy."""

from enum import Enum, auto


class BreakerState(Enum):
    """Breaker state supplied by the caller's policy layer.

    These values describe the caller's view at the moment a call is issued.
    They are never decided inside the breaker's failure path.
    """

    CLOSED = auto()
    """Caller policy considers the breaker closed and normal calls allowed."""

    OPEN = auto()
    """Caller policy considers the breaker open; the breaker failure path does not set this value."""

    HALF_OPEN = auto()
    """Caller policy considers the breaker half-open; the breaker failure path does not set this value."""


BreakerState.CLOSED.__doc__ = (
    "Caller policy considers the breaker closed and normal calls allowed."
)
BreakerState.OPEN.__doc__ = (
    "Caller policy considers the breaker open; the breaker failure path does not set this value."
)
BreakerState.HALF_OPEN.__doc__ = (
    "Caller policy considers the breaker half-open; the breaker failure path does not set this value."
)
```

call_context.py
```python
"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one downstream call attempt.

    ``caller_state`` is the caller's view of breaker state when the call was
    issued. It must reach every subscriber unchanged.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState
```

breaker_events.py
```python
"""Subscriber contract for circuit breaker notifications.

The notifier itself is not implemented here. The runtime is assumed to provide
a module-level ``NOTIFIER`` object conforming to :class:`Notifier`.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Callback signatures required of the notifier.

    Callbacks may be invoked synchronously from breaker methods and may
    reenter those methods.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify subscribers that a call failed.

        Guarantees:
        - Called only from ``CircuitBreaker.record_failure`` after the failure
          count has been incremented.
        - ``context`` is the original immutable ``CallContext``; its
          ``caller_state`` is unchanged.
        - ``failure_count`` is the post-increment failure count for the breaker.
        - ``threshold`` is the configured failure threshold.
        - If this failure caused a transition to OPEN, ``emit_breaker_opened``
          is emitted after this callback returns.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify subscribers that a call succeeded.

        Guarantees:
        - Called only from ``CircuitBreaker.record_success`` after any
          success-side mutation has occurred.
        - If the breaker was not open, the failure count has already been reset
          to zero.
        - If the breaker was open, the failure count has not been reset.
        - ``context`` is the original immutable ``CallContext``; its
          ``caller_state`` is unchanged.
        - ``current_state`` is the breaker's state after mutation.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify subscribers that the breaker transitioned to OPEN.

        Guarantees:
        - Called exactly once per transition to OPEN.
        - Not called for subsequent failures while the breaker remains OPEN.
        - Called after the corresponding ``emit_call_failed`` notification for
          the failure that caused the transition.
        - ``context`` is the original immutable ``CallContext``; its
          ``caller_state`` is unchanged.
        """
        ...


NOTIFIER: Notifier  # Provided externally; this module does not implement it.
```

circuit_breaker.py
```python
"""Circuit breaker that notifies through ``breaker_events.NOTIFIER``."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """Circuit breaker that records call outcomes and emits notifications.

    The breaker holds no references to any other system. ``NOTIFIER`` is its
    sole point of contact.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize a CLOSED breaker with zero recorded failures."""
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._state: BreakerState = BreakerState.CLOSED
        self._failure_count: int = 0

    def record_failure(self, context: CallContext) -> None:
        """Record a failed call.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. An already-open breaker ignores the call entirely. The failure
        count and state are mutated before any notification is emitted. If the
        failure causes a transition to OPEN, ``breaker_opened`` is emitted once.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropping call context with negative duration_ms: {context.duration_ms}",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        opened_now: bool = False
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            opened_now = True

        notifier: breaker_events.Notifier = breaker_events.NOTIFIER
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )
        if opened_now:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful call.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. If the breaker is not open, the failure count is reset to zero
        before the success notification is emitted. If the breaker is open, the
        failure count is left unchanged. The original context is emitted
        unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropping call context with negative duration_ms: {context.duration_ms}",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier: breaker_events.Notifier = breaker_events.NOTIFIER
        notifier.emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """Return the breaker to CLOSED with a zero failure count.

        This method emits no notifications.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0
```
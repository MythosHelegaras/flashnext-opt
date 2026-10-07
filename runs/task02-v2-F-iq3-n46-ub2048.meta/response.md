```python
# breaker_state.py
"""
Breaker state enum.

The values in this enum are authored by the caller's policy layer. The
circuit breaker's failure path does not decide which caller_state a call
context carries; it only records its own internal open/closed state.
"""

from enum import Enum


class BreakerState(Enum):
    """Breaker states visible to callers and subscribers."""

    CLOSED = "closed"
    """Closed: calls are allowed and failures are counted normally."""

    OPEN = "open"
    """Open: the breaker is not accepting new failure recording."""

    HALF_OPEN = "half_open"
    """Half-open: caller policy may probe with limited calls."""
```

```python
# call_context.py
"""
Immutable context for a single downstream call attempt.

CallContext carries exactly three fields. Its caller_state field is the
caller's view of breaker state at the moment the call was issued. That value
is load-bearing and must reach every subscriber unchanged.
"""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one call attempt."""

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState
```

```python
# breaker_events.py
"""
Subscriber contract for circuit breaker events.

This module defines the shape of NOTIFIER only. It does not implement a
notifier. The deployment must provide a module-level NOTIFIER object that
conforms to Notifier.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Callback contract required by CircuitBreaker."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Emit an accepted call failure.

        Guarantees:
          - Called only for failures accepted by the breaker.
          - context is the exact CallContext supplied to record_failure.
          - context.caller_state is unchanged and not reinterpreted.
          - failure_count is the breaker's failure count after incrementing
            for this failure.
          - threshold is the breaker's configured failure threshold.
          - This may be called for the failure that causes the breaker to
            transition to OPEN.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Emit an accepted call success.

        Guarantees:
          - Called only for successes accepted by the breaker.
          - context is the exact CallContext supplied to record_success.
          - context.caller_state is unchanged and not reinterpreted.
          - current_state is the breaker's state after any success-side
            mutation.
          - If the breaker was not open, its failure count has already been
            reset before this callback is invoked.
          - If the breaker was open, its failure count is not reset.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """
        Emit the transition of a breaker to OPEN.

        Guarantees:
          - Called exactly once per transition to OPEN.
          - Not called for repeated failures while the breaker is already open.
          - Not called by reset().
          - context is the failure context that caused the transition.
          - context.caller_state is unchanged and not reinterpreted.
        """
        ...
```

```python
# circuit_breaker.py
"""
Circuit breaker with event notifications.

The module expects a module-level NOTIFIER object conforming to
breaker_events.Notifier to be injected before use. NOTIFIER is the breaker's
sole point of contact with external systems.
"""

import warnings

from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext

NOTIFIER: Notifier


class CircuitBreaker:
    """
    Failure-counting circuit breaker.

    The breaker maintains its own internal state and failure count. It does
    not use CallContext.caller_state to decide whether to record a failure.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a breaker.

        Args:
            name: Identifier used in emitted events.
            failure_threshold: Number of recorded failures required to open
                the breaker.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record a downstream call failure.

        Behaviour:
          - A negative duration_ms is dropped with a warning.
          - If the breaker is already open, the failure is ignored entirely.
          - Otherwise, the failure count is incremented.
          - If the incremented count reaches the failure threshold, the
            breaker transitions to OPEN before any notification is emitted.
          - emit_call_failed is emitted with the full context.
          - If this failure caused the transition to OPEN, emit_breaker_opened
            is emitted exactly once.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropping CallContext with negative duration_ms={context.duration_ms}",
                category=UserWarning,
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

        NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened_now:
            NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record a downstream call success.

        Behaviour:
          - A negative duration_ms is dropped with a warning.
          - If the breaker is not open, the failure count is reset to zero
            before notification.
          - If the breaker is open, the failure count is not reset.
          - emit_call_succeeded is emitted with the full context and the
            breaker's current state after any mutation.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropping CallContext with negative duration_ms={context.duration_ms}",
                category=UserWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """
        Return the breaker to CLOSED with a zero failure count.

        This emits no events.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED
```
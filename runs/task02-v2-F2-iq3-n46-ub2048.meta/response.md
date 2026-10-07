Here are the four files.

## breaker_state.py

```python
"""Breaker state enum for caller-authored policy states."""

from enum import Enum


class BreakerState(Enum):
    """Policy states supplied by the caller's policy layer.

    These values describe the caller's view of a circuit breaker at the time
    a call was issued. They are authored by the caller and are not inferred,
    filtered, remapped, or rewritten by CircuitBreaker.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


BreakerState.CLOSED.__doc__ = (
    "Caller policy state: the breaker is closed and calls are allowed."
)
BreakerState.OPEN.__doc__ = (
    "Caller policy state: the breaker is open and calls are not allowed."
)
BreakerState.HALF_OPEN.__doc__ = (
    "Caller policy state: the breaker is half-open and probing with limited calls."
)
```

## call_context.py

```python
"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one downstream call attempt.

    The fields are exactly:
        duration_ms: elapsed call duration in milliseconds.
        endpoint: target endpoint, or None for anonymous calls.
        caller_state: caller-authored breaker state at call issue.

    CallContext.caller_state is a load-bearing product requirement.
    CircuitBreaker passes the original context to subscribers unchanged and
    never filters, remaps, or reinterprets caller_state.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState
```

## breaker_events.py

```python
"""Subscriber contract for circuit-breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Protocol describing the NOTIFIER object required by CircuitBreaker."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify a failed call.

        Guarantees:
            - Called only after CircuitBreaker has incremented its failure count.
            - context is the original CallContext, unchanged.
            - failure_count is the post-increment failure count for this failure.
            - threshold is the breaker's configured failure threshold.
            - If this failure caused the breaker to open, the breaker's internal
              state is already OPEN before this callback is invoked, so reentrant
              record_failure calls are ignored.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify a successful call.

        Guarantees:
            - Called only after CircuitBreaker has completed success processing.
            - context is the original CallContext, unchanged.
            - If the breaker was not open, its failure count has already been
              reset to zero before this callback is invoked.
            - current_state is the breaker's state after any success mutation:
              OPEN if the breaker was already open, otherwise CLOSED.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify a transition to OPEN.

        Guarantees:
            - Called exactly once for a transition from non-open to OPEN.
            - Not called for failures while the breaker is already open.
            - Not called by reset().
            - context is the original CallContext, unchanged.
            - The breaker's internal state is already OPEN before this callback
              is invoked.
        """
        ...


# The service injects this module-level object before CircuitBreaker emits.
NOTIFIER: Notifier
```

## circuit_breaker.py

```python
"""Failure-count circuit breaker that communicates only through NOTIFIER."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """A failure-count circuit breaker.

    The breaker maintains only its name, failure threshold, failure count, and
    open state. Its sole point of contact with the outside world is the
    module-level breaker_events.NOTIFIER object. It never reads or rewrites
    CallContext.caller_state.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize a closed breaker.

        Args:
            name: breaker name passed to notifications.
            failure_threshold: failure count at which the breaker opens.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """Record a failed call.

        If the breaker is already open, the call is ignored entirely before any
        validation or notification.

        If the breaker is closed and context.duration_ms is negative, a warning
        is emitted and the failure is dropped.

        Otherwise, the failure count is incremented first. If the incremented
        count reaches failure_threshold, the breaker state is set to OPEN before
        any notification, then emit_call_failed is invoked, then
        emit_breaker_opened is invoked. If the count does not reach the
        threshold, only emit_call_failed is invoked.
        """
        if self._state is BreakerState.OPEN:
            return

        if context.duration_ms < 0:
            warnings.warn(
                f"negative duration_ms {context.duration_ms} dropped by breaker {self._name!r}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        self._failure_count += 1
        failure_count = self._failure_count
        threshold = self._failure_threshold

        if failure_count >= threshold:
            self._state = BreakerState.OPEN

            notifier = breaker_events.NOTIFIER
            notifier.emit_call_failed(
                self._name,
                context,
                failure_count,
                threshold,
            )
            notifier.emit_breaker_opened(
                self._name,
                context,
            )
        else:
            breaker_events.NOTIFIER.emit_call_failed(
                self._name,
                context,
                failure_count,
                threshold,
            )

    def record_success(self, context: CallContext) -> None:
        """Record a successful call.

        If context.duration_ms is negative, a warning is emitted and the success
        is dropped.

        If the breaker is not open, its failure count is reset to zero before
        notification. If the breaker is open, the failure count is left unchanged.
        emit_call_succeeded is then invoked with the breaker's current state.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"negative duration_ms {context.duration_ms} dropped by breaker {self._name!r}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        breaker_events.NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """Return the breaker to CLOSED with a zero failure count.

        This method emits no notifications.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0
```
### breaker_state.py
```python
"""States selected by caller policy for circuit-breaker interactions.

These values are authored outside the circuit breaker. CircuitBreaker never
decides to enter HALF_OPEN; that choice belongs to the caller's policy layer.
"""

from enum import Enum, auto


class BreakerState(Enum):
    """Authoritative breaker state carried by CallContext."""

    CLOSED = auto()
    """The circuit is closed and calls are expected to succeed."""

    OPEN = auto()
    """The circuit is open and additional failures must not be recorded."""

    HALF_OPEN = auto()
    """The circuit is probing and is selected only by caller policy."""
```


### call_context.py
```python
"""Immutable metadata for one downstream call attempt."""

from breaker_state import BreakerState


class CallContext:
    """Immutable metadata describing one downstream call attempt.

    Negative duration_ms values are not rejected when constructing a context.
    CircuitBreaker treats them as invalid event input and drops them with a
    warning instead of raising an exception.
    """

    __slots__ = ("duration_ms", "endpoint", "caller_state")

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

    def __init__(
        self: "CallContext",
        duration_ms: int,
        endpoint: str | None,
        caller_state: BreakerState,
    ) -> None:
        """Create an immutable call context.

        The context carries the caller-authored breaker state unchanged. A
        breaker must pass this object through to subscribers without filtering,
        remapping, or otherwise interpreting caller_state.
        """
        object.__setattr__(self, "duration_ms", duration_ms)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "caller_state", caller_state)

    def __setattr__(self: "CallContext", name: str, value: object) -> None:
        """Reject any mutation of a CallContext field."""
        raise AttributeError("CallContext is immutable")

    def __delattr__(self: "CallContext", name: str) -> None:
        """Reject deletion of any CallContext field."""
        raise AttributeError("CallContext is immutable")

    def __repr__(self: "CallContext") -> str:
        """Return a debug representation of the call context."""
        return (
            f"CallContext(duration_ms={self.duration_ms!r}, "
            f"endpoint={self.endpoint!r}, "
            f"caller_state={self.caller_state!r})"
        )

    def __eq__(self: "CallContext", other: object) -> bool:
        """Compare field values with another CallContext."""
        if not isinstance(other, CallContext):
            return NotImplemented

        return (
            self.duration_ms == other.duration_ms
            and self.endpoint == other.endpoint
            and self.caller_state is other.caller_state
        )

    def __hash__(self: "CallContext") -> int:
        """Return a hash consistent with __eq__."""
        return hash((self.duration_ms, self.endpoint, self.caller_state))
```


### breaker_events.py
```python
"""Subscriber contract for circuit-breaker events.

This module defines the callback shapes a notifier must implement. The concrete
NOTIFIER object is supplied by the service composition root; it is not
implemented here. The circuit breaker resolves NOTIFIER through this module at
call time, so the service may replace breaker_events.NOTIFIER before events are
emitted.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Protocol for the module-level NOTIFIER object.

    The notifier methods are called synchronously. The circuit breaker does not
    transform, filter, remap, or reinterpret CallContext. Therefore any
    callback that receives a context receives the same caller-authored state in
    context.caller_state.
    """

    def emit_call_failed(
        self: "Notifier",
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify that one valid failure was accepted by the breaker.

        Guarantees:
        - Called only after CircuitBreaker has already mutated its failure
          count.
        - Not called for invalid negative duration_ms.
        - Not called for failures delivered to an already-open breaker.
        - failure_count is the post-mutation failure count for the accepted
          failure.
        - threshold is the breaker's configured failure threshold.
        - For a failure that opens the breaker, this event is emitted before
          emit_breaker_opened for the same transition.
        - context is passed through unchanged.
        """
        ...

    def emit_call_succeeded(
        self: "Notifier",
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify that one valid success was accepted by the breaker.

        Guarantees:
        - Called only after any post-success state mutation has already happened.
        - If the breaker was not open, the failure count is already reset to
          zero before this callback.
        - If the breaker was open, the failure count remains unchanged.
        - current_state is the breaker's internal state after that mutation. It
          is not context.caller_state.
        - context is passed through unchanged.
        """
        ...

    def emit_breaker_opened(
        self: "Notifier",
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify that an accepted failure transitioned the breaker to OPEN.

        Guarantees:
        - Called exactly once per transition to OPEN.
        - Never called for additional failures while the breaker is already
          open.
        - The breaker's internal state is already OPEN before this callback.
        - context is the failure context that caused the transition and is
          passed through unchanged.
        - For a transition caused by a failure, this event follows the matching
          emit_call_failed event.
        """
        ...


NOTIFIER: Notifier | None = None
"""Module-level notifier placeholder to be bound by the production service."""
```


### circuit_breaker.py
```python
"""Count-based circuit breaker with synchronous event notification."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """Count-based circuit breaker.

    The breaker records failures until a configured threshold is reached, then
    transitions to OPEN. It reports events through breaker_events.NOTIFIER and
    never stores references to subscribers or other runtime systems.

    HALF_OPEN belongs to caller policy. This breaker never selects HALF_OPEN
    from its failure path. The breaker never inspects context.caller_state to
    make decisions; it only passes the full context through to subscribers.
    """

    __slots__ = ("_name", "_failure_threshold", "_failure_count", "_state")

    _name: str
    _failure_threshold: int
    _failure_count: int
    _state: BreakerState

    def __init__(
        self: "CircuitBreaker",
        name: str,
        failure_threshold: int = 5,
    ) -> None:
        """Create a CLOSED circuit breaker with zero recorded failures."""
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self: "CircuitBreaker", context: CallContext) -> None:
        """Record one downstream failure and emit the corresponding event.

        Invalid negative duration_ms contexts are dropped with a warning and
        produce no state change or notification.

        If the breaker is already OPEN, the failure is ignored entirely after
        input validation. Otherwise, the failure count is incremented before any
        notification. If the increment reaches or exceeds the configured
        threshold, internal state is set to OPEN before the first notification.
        This makes reentrant calls to record_failure from callbacks observe the
        correct post-mutation guard.

        For an accepted failure, emit_call_failed is emitted with the full
        original context. If that failure opened the breaker,
        emit_breaker_opened is then emitted with the same original context.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name} dropped call record with negative "
                f"duration_ms={context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        failure_count = self._failure_count
        threshold = self._failure_threshold
        transitioned_to_open = failure_count >= threshold

        if transitioned_to_open:
            self._state = BreakerState.OPEN

        breaker_events.NOTIFIER.emit_call_failed(
            self._name,
            context,
            failure_count,
            threshold,
        )

        if transitioned_to_open:
            breaker_events.NOTIFIER.emit_breaker_opened(
                self._name,
                context,
            )

    def record_success(self: "CircuitBreaker", context: CallContext) -> None:
        """Record one downstream success and emit the corresponding event.

        Invalid negative duration_ms contexts are dropped with a warning and
        produce no state change or notification.

        State mutation happens before notification. If the breaker is not open,
        the failure count is reset to zero before emit_call_succeeded is called.
        If the breaker is open, the failure count is left unchanged.

        emit_call_succeeded receives current_state as the breaker's internal
        state after mutation. It also receives the full original context
        unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name} dropped call record with negative "
                f"duration_ms={context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        current_state = self._state

        breaker_events.NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            current_state,
        )

    def reset(self: "CircuitBreaker") -> None:
        """Return the breaker to CLOSED with zero recorded failures.

        This method emits no notifications.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0
```
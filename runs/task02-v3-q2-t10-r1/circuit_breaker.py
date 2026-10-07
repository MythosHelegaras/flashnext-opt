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

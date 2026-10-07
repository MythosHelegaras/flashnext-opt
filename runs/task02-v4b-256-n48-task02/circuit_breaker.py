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

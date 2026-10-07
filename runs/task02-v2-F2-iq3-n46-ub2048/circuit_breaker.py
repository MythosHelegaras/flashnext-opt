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

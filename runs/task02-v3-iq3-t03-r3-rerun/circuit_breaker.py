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

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

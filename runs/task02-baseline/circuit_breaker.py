# circuit_breaker.py
"""Production circuit breaker that notifies subscribers via NOTIFIER."""

import warnings

import breaker_events
from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext


def _notifier() -> Notifier:
    """Return the application-provided notifier."""
    return breaker_events.NOTIFIER


class CircuitBreaker:
    """A circuit breaker that emits notifications through NOTIFIER.

    The breaker holds no references to any other system. The module-level
    ``NOTIFIER`` object is its sole point of contact.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Create a closed breaker with a zero failure count."""
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._state: BreakerState = BreakerState.CLOSED
        self._failure_count: int = 0
        self._opening: bool = False

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call.

        Invalid negative-duration contexts are dropped with a warning. If the
        breaker is already OPEN, the failure is ignored entirely. Otherwise the
        failure count is incremented before any notification. If the count
        reaches the threshold, the state and an internal opening guard are set
        before notifications are emitted. The opened event is emitted only if
        that guard is still current after the failure notification. The original
        context is passed unchanged.
        """
        if self._is_invalid_duration(context):
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        will_open = self._failure_count >= self._failure_threshold

        if will_open:
            self._state = BreakerState.OPEN
            self._opening = True

        notifier = _notifier()

        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if will_open and self._opening and self._state is BreakerState.OPEN:
            self._opening = False
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call.

        Invalid negative-duration contexts are dropped with a warning. If the
        breaker is not OPEN, the failure count is reset to zero before the
        success notification. If the breaker is OPEN, the failure count is left
        unchanged. The original context is passed unchanged.
        """
        if self._is_invalid_duration(context):
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier = _notifier()

        notifier.emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """Return the breaker to CLOSED with a zero failure count."""
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._opening = False

    def _is_invalid_duration(self, context: CallContext) -> bool:
        """Warn and return ``True`` if ``context.duration_ms`` is negative."""
        if context.duration_ms < 0:
            warnings.warn(
                f"Circuit breaker {self._name!r} dropped a call context with "
                f"negative duration_ms={context.duration_ms!r}.",
                category=UserWarning,
                stacklevel=3,
            )
            return True

        return False

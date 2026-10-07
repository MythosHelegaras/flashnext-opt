"""A small reusable circuit breaker.

The breaker communicates only through the module-level ``NOTIFIER`` contract
declared in ``breaker_events``. It keeps no references to subscribers or other
systems.
"""

import warnings

import breaker_events as _breaker_events
from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext

# The assumed notifier may be supplied on this module or on breaker_events.
# This declaration does not implement NOTIFIER.
NOTIFIER: Notifier | None


def _get_notifier() -> Notifier | None:
    """Return the assumed module-level NOTIFIER object, if any is bound."""
    notifier: Notifier | None = getattr(_breaker_events, "NOTIFIER", None)
    if notifier is None:
        notifier = globals().get("NOTIFIER", None)
    return notifier


def _emit_call_failed(
    breaker_name: str,
    context: CallContext,
    failure_count: int,
    threshold: int,
) -> None:
    """Forward a failed-call event to NOTIFIER when available."""
    notifier = _get_notifier()
    if notifier is None:
        return
    notifier.emit_call_failed(breaker_name, context, failure_count, threshold)


def _emit_call_succeeded(
    breaker_name: str,
    context: CallContext,
    current_state: BreakerState,
) -> None:
    """Forward a succeeded-call event to NOTIFIER when available."""
    notifier = _get_notifier()
    if notifier is None:
        return
    notifier.emit_call_succeeded(breaker_name, context, current_state)


def _emit_breaker_opened(breaker_name: str, context: CallContext) -> None:
    """Forward a breaker-opened event to NOTIFIER when available."""
    notifier = _get_notifier()
    if notifier is None:
        return
    notifier.emit_breaker_opened(breaker_name, context)


def _warn_negative_duration(context: CallContext) -> None:
    """Drop a negative-duration call context with a warning."""
    try:
        warnings.warn(
            (
                f"CallContext has negative duration_ms={context.duration_ms}; "
                "call event dropped."
            ),
            UserWarning,
            stacklevel=3,
        )
    except Warning:
        pass


class CircuitBreaker:
    """A threshold-based circuit breaker with no outbound dependencies."""

    __slots__ = ("_name", "_failure_threshold", "_failure_count", "_state")

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Create a CLOSED breaker with a zero failure count.

        Args:
            name: Identifier for this breaker passed to notifier events.
            failure_threshold: Failure count at which CLOSED becomes OPEN.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call and notify accepted failures.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. When the breaker is already OPEN, a failure is ignored
        entirely. When the failure count reaches ``failure_threshold``, the
        internal state is changed to OPEN before notifications are emitted.

        Args:
            context: The immutable call context to pass unchanged to subscribers.
        """
        if context.duration_ms < 0:
            _warn_negative_duration(context)
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        failure_count = self._failure_count
        tripped = failure_count >= self._failure_threshold
        if tripped:
            self._state = BreakerState.OPEN

        _emit_call_failed(self._name, context, failure_count, self._failure_threshold)
        if tripped:
            _emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call and emit success.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. When the breaker is not OPEN, the failure count is reset to
        zero before the success notification.

        Args:
            context: The immutable call context to pass unchanged to subscribers.
        """
        if context.duration_ms < 0:
            _warn_negative_duration(context)
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        _emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """Reset the breaker to CLOSED with a zero failure count.

        This method emits no events.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED

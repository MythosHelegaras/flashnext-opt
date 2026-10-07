"""Production circuit breaker that notifies through breaker_events.NOTIFIER."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """A small circuit breaker that reports events through ``NOTIFIER``.

    The breaker holds no references to any other system. Its sole external
    contact is the module-level ``NOTIFIER`` object declared in
    ``breaker_events``.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Create a closed breaker with a zero failure count."""
        self._name = name
        self._failure_threshold = failure_threshold
        self._state = BreakerState.CLOSED
        self._failure_count = 0

    def record_failure(self, context: CallContext) -> None:
        """Record a failed call and notify subscribers.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning before any state change or notification. Failures recorded
        while the breaker is already OPEN are ignored entirely.

        The internal failure count is incremented before any event is emitted.
        If the threshold is reached, the state is set to OPEN before the first
        event is emitted, so reentrant calls observe the post-mutation state.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: CallContext.duration_ms must be non-negative; "
                f"got {context.duration_ms}",
                RuntimeWarning,
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

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )
        if opened_now:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful call and notify subscribers.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning before any state change or notification. A success always emits
        ``call_succeeded``. If the breaker is not OPEN, the failure count is
        reset before the event is emitted. If the breaker is OPEN, the failure
        count is left unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: CallContext.duration_ms must be non-negative; "
                f"got {context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """Return the breaker to CLOSED with a zero failure count.

        This method emits no events.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0

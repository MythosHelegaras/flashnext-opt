"""Production circuit breaker that notifies subscribers through NOTIFIER."""

import warnings

import breaker_events
from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """
    A small circuit breaker that reports calls through ``NOTIFIER``.

    The breaker holds no references to any other system. ``NOTIFIER`` is its
    sole point of contact. Internal state is mutated before subscriber
    notifications so synchronous callbacks observe the post-mutation state.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a circuit breaker.

        Args:
            name: Name reported to subscribers.
            failure_threshold: Failure count that opens the breaker.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record a failed call.

        Negative ``duration_ms`` values are dropped with a warning. A failure
        on an already-open breaker is ignored. Otherwise the failure count is
        incremented, and if the threshold is reached the internal state is set
        to OPEN before any notification is emitted. When a transition occurs,
        ``call_failed`` is emitted before ``breaker_opened``.
        """
        duration_ms: int = context.duration_ms
        if duration_ms < 0:
            warnings.warn(
                f"Circuit breaker {self._name!r} ignored a failure with negative duration_ms={duration_ms}.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        notifier: Notifier = breaker_events.NOTIFIER

        self._failure_count += 1
        opened: bool = False
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            opened = True

        # The state is already OPEN before the first notification, so a
        # synchronous callback into record_failure sees the post-mutation guard.
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record a successful call.

        Negative ``duration_ms`` values are dropped with a warning. If the
        breaker is not OPEN, the failure count is reset to zero before
        ``call_succeeded`` is emitted.
        """
        duration_ms: int = context.duration_ms
        if duration_ms < 0:
            warnings.warn(
                f"Circuit breaker {self._name!r} ignored a success with negative duration_ms={duration_ms}.",
                UserWarning,
                stacklevel=2,
            )
            return

        notifier: Notifier = breaker_events.NOTIFIER

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        # The failure count is already reset before notification.
        notifier.emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """
        Return the breaker to CLOSED with a zero failure count.

        No notifications are emitted.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0


__all__ = ["CircuitBreaker"]

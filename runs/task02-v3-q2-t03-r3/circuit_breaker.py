"""Circuit breaker that notifies subscribers through ``NOTIFIER``."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """A small circuit breaker that reports events through ``NOTIFIER``.

    The breaker holds no references to any other system. ``NOTIFIER`` is its
    sole point of contact.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize a closed circuit breaker.

        Args:
            name: Name reported to subscribers.
            failure_threshold: Number of recorded failures that opens the
                breaker.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. Failures recorded while the breaker is already OPEN are
        ignored. Otherwise, the internal failure count is incremented first. If
        the count reaches ``failure_threshold``, the breaker state is set to
        OPEN before any notification fires. The method then emits
        ``call_failed`` and, if this call transitioned the breaker to OPEN,
        emits ``breaker_opened`` exactly once.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}. "
                "Failure event dropped.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        transitioned_to_open = False
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            transitioned_to_open = True

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if transitioned_to_open:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. If the breaker is not OPEN, the failure count is reset to zero
        before notification. The method then emits ``call_succeeded`` with the
        breaker's current state after any mutation.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}. "
                "Success event dropped.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """Return the breaker to CLOSED with a zero failure count.

        This method emits nothing.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0

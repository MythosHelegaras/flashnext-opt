# circuit_breaker.py
"""Named circuit breaker recorder and notifier adapter."""

import warnings

import breaker_events
from breaker_events import BreakerNotifier
from call_context import CallContext
from breaker_state import BreakerState


class CircuitBreaker:
    """Failure recorder for one named circuit breaker.

    State mutations complete before notifications are prepared and emitted.
    The production-provided `NOTIFIER` object is the breaker's sole external
    point of contact.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize a breaker in `CLOSED` state with zero recorded failures.

        Args:
            name: Logical name used in notifications.
            failure_threshold: Number of accepted failures that causes an
                internal transition to `OPEN`.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call.

        Guarantees:
          - A negative `context.duration_ms` is dropped with a warning and
            causes no state mutation or notification.
          - If the breaker is already internally `OPEN`, the call is ignored
            entirely.
          - Otherwise, the internal failure count is incremented first.
          - If that increment reaches the threshold, the breaker state is set
            to `OPEN` before any notification fires, so synchronous reentrancy
            sees the open guard already in its post-mutation state.
          - The full immutable context is passed unchanged to
            `NOTIFIER.emit_call_failed`.
          - If this failure is the one that opened the breaker,
            `NOTIFIER.emit_breaker_opened` is emitted exactly once for this
            transition.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CircuitBreaker.record_failure dropped invalid context: "
                f"breaker={self._name!r}, duration_ms={context.duration_ms!r}",
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        notifier: BreakerNotifier = breaker_events.NOTIFIER

        self._failure_count += 1

        opened_now = False
        if self._failure_count >= self._failure_threshold:
            if self._state is not BreakerState.OPEN:
                self._state = BreakerState.OPEN
                opened_now = True

        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened_now:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call.

        Guarantees:
          - A negative `context.duration_ms` is dropped with a warning and
            causes no state mutation or notification.
          - If the breaker is not internally `OPEN`, its failure count is
            reset to zero before notification.
          - If the breaker is internally `OPEN`, the failure count is not
            reset.
          - The full immutable context is passed unchanged to
            `NOTIFIER.emit_call_succeeded`.
          - `NOTIFIER.emit_call_succeeded` receives the breaker state after
            mutation and before emission.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CircuitBreaker.record_success dropped invalid context: "
                f"breaker={self._name!r}, duration_ms={context.duration_ms!r}",
                stacklevel=2,
            )
            return

        notifier: BreakerNotifier = breaker_events.NOTIFIER

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """Return the breaker to `CLOSED` with a zero failure count.

        Guarantees:
          - Internal state becomes `BreakerState.CLOSED`.
          - The internal failure count becomes zero.
          - No notification is emitted.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED

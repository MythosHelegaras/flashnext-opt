"""
Synchronous circuit breaker that communicates exclusively through NOTIFIER.

The breaker holds no references to any other system. The global `NOTIFIER`
object is its sole point of contact.
"""

import warnings

from breaker_state import BreakerState
from call_context import CallContext
from breaker_events import BreakerNotifier

# The application is expected to provide this module-level object before any
# breaker records a call. No notifier is defined or imported here.
NOTIFIER: BreakerNotifier


def _notifier() -> BreakerNotifier:
    """
    Return the application-provided global notifier object.
    """
    return NOTIFIER


class CircuitBreaker:
    """
    A synchronous failure-count circuit breaker.

    The breaker tracks only:
        - its configured failure threshold
        - a non-negative failure count
        - a breaker state

    It notifies subscribers through `NOTIFIER` only.
    """

    __slots__ = (
        "_name",
        "_failure_threshold",
        "_failure_count",
        "_state",
    )

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a new breaker.

        Args:
            name:
                Breaker name passed through to every notification.
            failure_threshold:
                Number of accepted failures required before the breaker
                transitions to OPEN.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record a failed call attempt.

        Behavior:
            - Negative `duration_ms` is dropped with a warning.
            - If the breaker is already OPEN, the call is ignored entirely.
            - Otherwise, the internal failure count is incremented first.
            - If the incremented count reaches the threshold, the state is
              mutated to OPEN before any notification is emitted.
            - `emit_call_failed` is always emitted for accepted failures.
            - If this failure opened the breaker, `emit_breaker_opened` is then
              emitted once.

        The caller-supplied `context.caller_state` is passed through unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CallContext.duration_ms must be non-negative; dropping "
                f"failure event for breaker {self._name!r}.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        notifier = _notifier()

        self._failure_count += 1

        transition_to_open = self._failure_count >= self._failure_threshold
        if transition_to_open:
            self._state = BreakerState.OPEN

        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if transition_to_open:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record a successful call attempt.

        Behavior:
            - Negative `duration_ms` is dropped with a warning.
            - If the breaker is not OPEN, the internal failure count is reset
              to zero before notification.
            - If the breaker is OPEN, success does not reset the failure count
              and does not close the breaker.
            - `emit_call_succeeded` is emitted after any corresponding
              internal mutation.
            - The notifier receives the breaker's current state after
              success processing.

        The caller-supplied `context.caller_state` is passed through unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CallContext.duration_ms must be non-negative; dropping "
                f"success event for breaker {self._name!r}.",
                UserWarning,
                stacklevel=2,
            )
            return

        notifier = _notifier()

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """
        Reset the breaker to CLOSED with a zero failure count.

        This method emits no notifications.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED

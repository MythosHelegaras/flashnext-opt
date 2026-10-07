"""Failure-threshold circuit breaker that reports through module-level NOTIFIER."""

import warnings

from breaker_state import BreakerState
from breaker_events import CircuitBreakerNotifier
from call_context import CallContext

# The service installs this module-level object before invoking breaker methods.
# It is intentionally not implemented here.
NOTIFIER: CircuitBreakerNotifier


class CircuitBreaker:
    """A small failure-threshold circuit breaker.

    The breaker holds no references to any external system. ``NOTIFIER`` is its
    sole point of contact with subscribers.

    Internal state is updated before notifications so synchronous callbacks may
    observe the post-mutation state, including a reentrant failure seeing an
    already-open breaker and being ignored.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Create a breaker.

        Args:
            name:
                Identifier passed to every ``NOTIFIER`` callback.
            failure_threshold:
                Number of accepted failures that causes a transition to
                ``BreakerState.OPEN``.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED
        self._open_transition: int = 0

    def _warn_invalid_duration(self, context: CallContext) -> bool:
        """Warn and drop a call result with a negative duration.

        Args:
            context:
                Candidate immutable call context.

        Returns:
            ``True`` if the context should be dropped, otherwise ``False``.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CallContext duration_ms="
                f"{context.duration_ms} is negative; "
                f"ignoring call result for breaker {self._name!r}.",
                UserWarning,
                stacklevel=3,
            )
            return True

        return False

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call attempt.

        Invalid negative-duration contexts are dropped with a warning.

        If the breaker is already open, the failure is ignored entirely.

        Otherwise, the failure count is incremented first. If the count reaches
        the configured threshold, the breaker transitions to
        ``BreakerState.OPEN`` before any notification is emitted. The breaker
        then emits ``emit_call_failed`` with the unchanged context, and then,
        if still in the same transition to ``OPEN``, emits
        ``emit_breaker_opened``.

        Args:
            context:
                Immutable description of the failed call attempt.
        """
        if self._warn_invalid_duration(context):
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1

        opening_transition = False
        transition_token = 0

        if self._failure_count >= self._failure_threshold:
            self._open_transition += 1
            transition_token = self._open_transition
            self._state = BreakerState.OPEN
            opening_transition = True

        NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if (
            opening_transition
            and self._state is BreakerState.OPEN
            and self._open_transition == transition_token
        ):
            NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call attempt.

        Invalid negative-duration contexts are dropped with a warning.

        If the breaker is not open, the failure count is reset to zero before
        notification. The breaker state is not otherwise changed.

        If the breaker is already open, the failure count is not reset.

        The unchanged context is passed to ``NOTIFIER.emit_call_succeeded`` along
        with the breaker's current state.

        Args:
            context:
                Immutable description of the successful call attempt.
        """
        if self._warn_invalid_duration(context):
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """Return the breaker to closed state with zero failures.

        No notifier event is emitted.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED

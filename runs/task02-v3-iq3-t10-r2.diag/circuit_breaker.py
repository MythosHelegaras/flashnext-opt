"""Failure-count circuit breaker for production use."""

import warnings

from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext

NOTIFIER: Notifier


class CircuitBreaker:
    """Tracks downstream-call failures and notifies `NOTIFIER`.

    The breaker holds no references to other systems. `NOTIFIER` is its only
    point of contact.

    Mutations are completed before notifications so that reentrant callbacks
    observe the post-mutation state.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize an instance.

        Args:
            name: Breaker name used in every notification.
            failure_threshold: Number of failures required to open the breaker.
                Defaults to 5.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._is_open = False

    def record_failure(self, context: CallContext) -> None:
        """Record a failure.

        If `context.duration_ms` is negative, the call is dropped with a
        warning and no state mutation or notification occurs.

        Otherwise, if the breaker is already open, the call is ignored entirely.

        For a valid failure on a non-open breaker, state is mutated before any
        notification:

        - The failure count is incremented.
        - If the failure count reaches `failure_threshold`, the breaker is
          transitioned to `OPEN` before the first notification.
        - `NOTIFIER.emit_call_failed` is emitted.
        - If this failure caused the transition, `NOTIFIER.emit_breaker_opened`
          is emitted exactly once for that transition.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"invalid CallContext for breaker {self._name!r}: "
                f"duration_ms={context.duration_ms} is negative",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._is_open:
            return

        self._failure_count += 1
        opened_now = self._failure_count >= self._failure_threshold
        if opened_now:
            self._is_open = True

        NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened_now:
            NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a success.

        If `context.duration_ms` is negative, the call is dropped with a
        warning and no state mutation or notification occurs.

        Otherwise, state mutation happens before notification:

        - If the breaker is not open, its failure count is reset to zero.
        - If the breaker is open, its failure count is not reset.
        - `NOTIFIER.emit_call_succeeded` is emitted with the current internal
          breaker state.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"invalid CallContext for breaker {self._name!r}: "
                f"duration_ms={context.duration_ms} is negative",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if not self._is_open:
            self._failure_count = 0

        current_state: BreakerState = (
            BreakerState.OPEN if self._is_open else BreakerState.CLOSED
        )
        NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            current_state,
        )

    def reset(self) -> None:
        """Return the breaker to `CLOSED` with a zero failure count.

        This emits no notifications.
        """
        self._is_open = False
        self._failure_count = 0

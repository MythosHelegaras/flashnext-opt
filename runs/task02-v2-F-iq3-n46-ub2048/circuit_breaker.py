# circuit_breaker.py
"""
Circuit breaker with event notifications.

The module expects a module-level NOTIFIER object conforming to
breaker_events.Notifier to be injected before use. NOTIFIER is the breaker's
sole point of contact with external systems.
"""

import warnings

from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext

NOTIFIER: Notifier


class CircuitBreaker:
    """
    Failure-counting circuit breaker.

    The breaker maintains its own internal state and failure count. It does
    not use CallContext.caller_state to decide whether to record a failure.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a breaker.

        Args:
            name: Identifier used in emitted events.
            failure_threshold: Number of recorded failures required to open
                the breaker.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record a downstream call failure.

        Behaviour:
          - A negative duration_ms is dropped with a warning.
          - If the breaker is already open, the failure is ignored entirely.
          - Otherwise, the failure count is incremented.
          - If the incremented count reaches the failure threshold, the
            breaker transitions to OPEN before any notification is emitted.
          - emit_call_failed is emitted with the full context.
          - If this failure caused the transition to OPEN, emit_breaker_opened
            is emitted exactly once.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropping CallContext with negative duration_ms={context.duration_ms}",
                category=UserWarning,
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

        NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened_now:
            NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record a downstream call success.

        Behaviour:
          - A negative duration_ms is dropped with a warning.
          - If the breaker is not open, the failure count is reset to zero
            before notification.
          - If the breaker is open, the failure count is not reset.
          - emit_call_succeeded is emitted with the full context and the
            breaker's current state after any mutation.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"{self._name}: dropping CallContext with negative duration_ms={context.duration_ms}",
                category=UserWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """
        Return the breaker to CLOSED with a zero failure count.

        This emits no events.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED

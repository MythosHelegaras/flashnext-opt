# circuit_breaker.py
"""Circuit breaker that records call outcomes and emits events via NOTIFIER."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """
    A small reusable circuit breaker.

    The breaker holds no references to any other system. Its sole point of
    contact is the module-level `NOTIFIER` object defined by `breaker_events`.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a closed breaker.

        Args:
            name: Name passed to notifier events.
            failure_threshold: Number of accepted failures that opens the breaker.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record an accepted call failure.

        Invalid contexts with negative `duration_ms` are dropped with a warning.
        Failures recorded while the breaker is already OPEN are ignored entirely.
        Otherwise the failure count is incremented, and if it reaches the
        configured threshold the breaker transitions to OPEN before any
        notification is emitted.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        transitioned_to_open: bool = False
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            transitioned_to_open = True

        breaker_events.NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if transitioned_to_open:
            breaker_events.NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record an accepted call success.

        Invalid contexts with negative `duration_ms` are dropped with a warning.
        Otherwise the breaker emits a success event. If the breaker is not OPEN,
        the failure count is reset to zero before the notification is emitted.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        breaker_events.NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """
        Return the breaker to CLOSED with a zero failure count.

        This method emits nothing.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0

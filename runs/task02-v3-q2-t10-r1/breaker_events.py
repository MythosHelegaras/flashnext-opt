"""Subscriber contract for circuit-breaker events.

This module defines the callback shapes a notifier must implement. The concrete
NOTIFIER object is supplied by the service composition root; it is not
implemented here. The circuit breaker resolves NOTIFIER through this module at
call time, so the service may replace breaker_events.NOTIFIER before events are
emitted.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Protocol for the module-level NOTIFIER object.

    The notifier methods are called synchronously. The circuit breaker does not
    transform, filter, remap, or reinterpret CallContext. Therefore any
    callback that receives a context receives the same caller-authored state in
    context.caller_state.
    """

    def emit_call_failed(
        self: "Notifier",
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify that one valid failure was accepted by the breaker.

        Guarantees:
        - Called only after CircuitBreaker has already mutated its failure
          count.
        - Not called for invalid negative duration_ms.
        - Not called for failures delivered to an already-open breaker.
        - failure_count is the post-mutation failure count for the accepted
          failure.
        - threshold is the breaker's configured failure threshold.
        - For a failure that opens the breaker, this event is emitted before
          emit_breaker_opened for the same transition.
        - context is passed through unchanged.
        """
        ...

    def emit_call_succeeded(
        self: "Notifier",
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify that one valid success was accepted by the breaker.

        Guarantees:
        - Called only after any post-success state mutation has already happened.
        - If the breaker was not open, the failure count is already reset to
          zero before this callback.
        - If the breaker was open, the failure count remains unchanged.
        - current_state is the breaker's internal state after that mutation. It
          is not context.caller_state.
        - context is passed through unchanged.
        """
        ...

    def emit_breaker_opened(
        self: "Notifier",
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify that an accepted failure transitioned the breaker to OPEN.

        Guarantees:
        - Called exactly once per transition to OPEN.
        - Never called for additional failures while the breaker is already
          open.
        - The breaker's internal state is already OPEN before this callback.
        - context is the failure context that caused the transition and is
          passed through unchanged.
        - For a transition caused by a failure, this event follows the matching
          emit_call_failed event.
        """
        ...


NOTIFIER: Notifier | None = None
"""Module-level notifier placeholder to be bound by the production service."""

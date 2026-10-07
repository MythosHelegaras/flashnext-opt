"""Subscriber contract for circuit-breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Protocol describing the NOTIFIER object required by CircuitBreaker."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify a failed call.

        Guarantees:
            - Called only after CircuitBreaker has incremented its failure count.
            - context is the original CallContext, unchanged.
            - failure_count is the post-increment failure count for this failure.
            - threshold is the breaker's configured failure threshold.
            - If this failure caused the breaker to open, the breaker's internal
              state is already OPEN before this callback is invoked, so reentrant
              record_failure calls are ignored.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify a successful call.

        Guarantees:
            - Called only after CircuitBreaker has completed success processing.
            - context is the original CallContext, unchanged.
            - If the breaker was not open, its failure count has already been
              reset to zero before this callback is invoked.
            - current_state is the breaker's state after any success mutation:
              OPEN if the breaker was already open, otherwise CLOSED.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify a transition to OPEN.

        Guarantees:
            - Called exactly once for a transition from non-open to OPEN.
            - Not called for failures while the breaker is already open.
            - Not called by reset().
            - context is the original CallContext, unchanged.
            - The breaker's internal state is already OPEN before this callback
              is invoked.
        """
        ...


# The service injects this module-level object before CircuitBreaker emits.
NOTIFIER: Notifier

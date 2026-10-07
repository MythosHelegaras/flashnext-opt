# breaker_events.py
"""
Subscriber contract for circuit breaker events.

This module defines the shape of NOTIFIER only. It does not implement a
notifier. The deployment must provide a module-level NOTIFIER object that
conforms to Notifier.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Callback contract required by CircuitBreaker."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Emit an accepted call failure.

        Guarantees:
          - Called only for failures accepted by the breaker.
          - context is the exact CallContext supplied to record_failure.
          - context.caller_state is unchanged and not reinterpreted.
          - failure_count is the breaker's failure count after incrementing
            for this failure.
          - threshold is the breaker's configured failure threshold.
          - This may be called for the failure that causes the breaker to
            transition to OPEN.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Emit an accepted call success.

        Guarantees:
          - Called only for successes accepted by the breaker.
          - context is the exact CallContext supplied to record_success.
          - context.caller_state is unchanged and not reinterpreted.
          - current_state is the breaker's state after any success-side
            mutation.
          - If the breaker was not open, its failure count has already been
            reset before this callback is invoked.
          - If the breaker was open, its failure count is not reset.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """
        Emit the transition of a breaker to OPEN.

        Guarantees:
          - Called exactly once per transition to OPEN.
          - Not called for repeated failures while the breaker is already open.
          - Not called by reset().
          - context is the failure context that caused the transition.
          - context.caller_state is unchanged and not reinterpreted.
        """
        ...

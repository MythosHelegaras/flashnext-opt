"""Subscriber contract for circuit breaker events."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """
    Callback signatures the module-level NOTIFIER object must support.

    The context passed to every callback is the same CallContext supplied to
    the breaker method. caller_state is not filtered, remapped, or reinterpreted.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Called after an accepted failure has incremented the breaker's failure count.

        Guarantees:
        - failure_count is the post-increment failure count.
        - threshold is the breaker's configured failure threshold.
        - context is the full CallContext supplied to record_failure.
        - context.caller_state is unchanged.
        - If this failure causes the breaker to transition to OPEN,
          emit_breaker_opened will be emitted after this callback.
        """

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Called after an accepted success has been processed.

        Guarantees:
        - current_state is the breaker's state after any reset caused by this
          success.
        - If the breaker was not open, its failure count has already been reset
          to zero before this callback.
        - context is the full CallContext supplied to record_success.
        - context.caller_state is unchanged.
        """

    def emit_breaker_opened(self, breaker_name: str, context: CallContext) -> None:
        """
        Called exactly once for a transition to OPEN.

        Guarantees:
        - The breaker state has already been mutated to OPEN before this callback.
        - It is emitted after emit_call_failed for the failure that caused the
          transition.
        - It is never emitted for a failure recorded while the breaker is already
          open.
        - context is the full CallContext supplied to record_failure.
        - context.caller_state is unchanged.
        """


NOTIFIER: Notifier

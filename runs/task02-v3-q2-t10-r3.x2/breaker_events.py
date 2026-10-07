"""
Subscriber contract for circuit breaker notifications.

This module defines the notification protocol only. It does not implement or
define a notifier object.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class BreakerNotifier(Protocol):
    """
    Notification protocol required by `CircuitBreaker`.

    The application is expected to provide a module-level `NOTIFIER` object whose
    structure satisfies this protocol.

    Callbacks are invoked synchronously by the breaker. If a callback raises an
    exception, the breaker does not catch it. Any internal state mutations
    already performed before the first callback remain in effect. Events after
    the exception may not be delivered.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Called once for every accepted failure after the breaker's internal
        failure count has been incremented.

        Guarantees:
            - Fires for every accepted `CircuitBreaker.record_failure()` call.
            - Does not fire for already-open breaker failures.
            - Does not fire for invalid negative-duration contexts.
            - `context` is the exact caller-supplied `CallContext`, unchanged.
            - `failure_count` is the breaker's failure count after incrementing
              for this failure.
            - `threshold` is the breaker's configured failure threshold.
            - When this failure reaches `threshold`, the breaker state has
              already been mutated to `BreakerState.OPEN` before this callback
              begins.
            - In that same outer `record_failure()` call, `emit_breaker_opened`
              follows this callback.
            - Callbacks may reenter the breaker synchronously. The breaker's
              guard state is already post-mutation before this callback starts.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Called once for every accepted success after any corresponding internal
        success processing has already happened.

        Guarantees:
            - Fires for every accepted `CircuitBreaker.record_success()` call.
            - Does not fire for invalid negative-duration contexts.
            - `context` is the exact caller-supplied `CallContext`, unchanged.
            - `current_state` is the breaker's internal state after the success
              was processed.
            - If the breaker was not open, the internal failure count has
              already been reset to zero before this callback begins.
            - If the breaker was open, no state or failure-count mutation was
              performed for success.
            - This event may fire while the breaker is open.
            - Callbacks may reenter the breaker synchronously.
        """
        ...

    def emit_breaker_opened(self, breaker_name: str, context: CallContext) -> None:
        """
        Called once when the breaker transitions into `BreakerState.OPEN`.

        Guarantees:
            - Fires exactly once per transition into OPEN.
            - Never fires again while the breaker is already open.
            - Fires after the breaker state has already been mutated to OPEN.
            - Fires after `emit_call_failed` for the same failure that caused
              the transition.
            - `context` is the exact caller-supplied failure context that caused
              the transition, unchanged.
            - Callbacks may reenter the breaker synchronously, and the breaker's
              open guard is already active before this callback starts.
        """
        ...

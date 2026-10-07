"""Subscriber callback contract for circuit breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreakerNotifier(Protocol):
    """Required notifier interface for ``CircuitBreaker``.

    A module-level object named ``NOTIFIER`` must satisfy this contract. It is
    intentionally not defined here.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify subscribers that a downstream call failed.

        Guarantees:
            - ``context`` is the exact immutable ``CallContext`` supplied by the
              caller.
            - ``context.caller_state`` is passed through unchanged.
            - ``failure_count`` is the breaker's failure count after the accepted
              failure mutation.
            - ``threshold`` is the breaker's configured failure threshold at
              notification time.
            - This callback is not emitted for invalid negative-duration input.
            - This callback is not emitted when the breaker was already open and
              therefore ignored the failure.
            - If this failure caused a transition to ``BreakerState.OPEN``, the
              breaker's internal state already reflects ``OPEN`` before this
              callback runs.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify subscribers that a downstream call succeeded.

        Guarantees:
            - ``context`` is the exact immutable ``CallContext`` supplied by the
              caller.
            - ``context.caller_state`` is passed through unchanged.
            - ``current_state`` is the breaker's internal state after any success
              mutation, not the context's ``caller_state``.
            - This callback is not emitted for invalid negative-duration input.
            - If the breaker was not already open when success was recorded, its
              failure count has already been reset to zero before this callback
              runs.
            - If the breaker was already open when success was recorded, its
              failure count is not reset.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify subscribers that a breaker transitioned to ``OPEN``.

        Guarantees:
            - ``context`` is the exact immutable ``CallContext`` associated with
              the failure that caused the transition.
            - ``context.caller_state`` is passed through unchanged.
            - The breaker's internal state already reflects ``BreakerState.OPEN``
              before this callback runs.
            - This callback fires at most once per transition from a non-open
              state to ``OPEN``.
            - This callback is not emitted for an already-open breaker.
        """
        ...

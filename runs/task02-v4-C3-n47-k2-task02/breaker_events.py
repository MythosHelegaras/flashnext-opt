"""Subscriber contract for circuit breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """
    Contract for the module-level ``NOTIFIER`` object.

    The concrete notifier is provided by the service. This module defines only
    the callback signatures and their guarantees; it does not implement the
    notifier.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Emit a failure notification.

        Guarantees:
        - Called exactly once for each accepted failure recorded by a breaker.
        - ``context`` is the original ``CallContext`` supplied to the breaker;
          its ``caller_state`` is unchanged and must not be filtered, remapped,
          or reinterpreted.
        - ``failure_count`` is the breaker's internal failure count after the
          failure has been recorded.
        - ``threshold`` is the breaker's configured failure threshold.
        - If the failure caused a transition to OPEN, the breaker's internal
          state is already OPEN before this callback is invoked.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Emit a success notification.

        Guarantees:
        - Called exactly once for each accepted success recorded by a breaker.
        - ``context`` is the original ``CallContext`` supplied to the breaker;
          its ``caller_state`` is unchanged and must not be filtered, remapped,
          or reinterpreted.
        - ``current_state`` is the breaker's internal state at notification
          time; it is not ``context.caller_state``.
        - If the breaker was not OPEN, the internal failure count has already
          been reset to zero before this callback is invoked.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """
        Emit a transition-to-OPEN notification.

        Guarantees:
        - Called exactly once for each transition into OPEN.
        - Called only when the failure count reaches the configured threshold.
        - Never called again while the breaker is already OPEN.
        - ``context`` is the original ``CallContext`` supplied to the breaker;
          its ``caller_state`` is unchanged and must not be filtered, remapped,
          or reinterpreted.
        - The breaker's internal state is already OPEN before this callback is
          invoked.
        """
        ...


# The concrete notifier is installed by the service as ``NOTIFIER``. This
# module intentionally declares only the contract and does not implement it.
NOTIFIER: Notifier


__all__ = ["Notifier"]

# breaker_events.py
"""Subscriber contract for circuit breaker events."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """
    Protocol for the module-level `NOTIFIER` object.

    The concrete notifier is supplied by the surrounding system. This module
    intentionally does not implement it. The notifier must preserve each
    `CallContext` unchanged and must not filter, remap, or reinterpret
    `context.caller_state`.
    """

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
        - Called only after the breaker has incremented its failure count.
        - `context` is the original caller-provided context, unchanged.
        - `failure_count` is the post-increment failure count.
        - `threshold` is the breaker's configured failure threshold.
        - Not called for invalid contexts or for failures recorded while the
          breaker is already OPEN.
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
        - Called after any failure-count reset has already been applied.
        - `context` is the original caller-provided context, unchanged.
        - `current_state` is the breaker's state after that mutation: CLOSED if
          the success reset the failure count, or OPEN if the breaker was already
          open.
        - Called even when the breaker is OPEN.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """
        Emit a transition to OPEN.

        Guarantees:
        - Called exactly once for each transition from not-open to OPEN.
        - Called only after the breaker's internal state is already OPEN.
        - Never called again while the breaker is already OPEN.
        - `context` is the original caller-provided context, unchanged.
        - For the failure that opens the breaker, this event is emitted after
          the corresponding call_failed notification.
        """
        ...


NOTIFIER: Notifier

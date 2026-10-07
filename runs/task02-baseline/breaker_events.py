# breaker_events.py
"""Subscriber contract for circuit breaker notifications.

This module defines the callback signatures a notifier must support. It does
not implement a notifier. The application must provide a module-level
``NOTIFIER`` object that satisfies :class:`Notifier`.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """The notifier interface used by the circuit breaker."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify subscribers that a valid failed call was recorded.

        Guarantees:
        - The call context was valid; negative-duration contexts are dropped
          before this callback.
        - ``context`` is the original caller-supplied context, unchanged.
        - ``failure_count`` is the breaker's internal failure count after the
          failure has been incremented.
        - ``threshold`` is the configured failure threshold.
        - This callback may be emitted for the failure that causes the breaker
          to transition to OPEN.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify subscribers that a valid successful call was recorded.

        Guarantees:
        - The call context was valid; negative-duration contexts are dropped
          before this callback.
        - ``context`` is the original caller-supplied context, unchanged.
        - ``current_state`` is the breaker state after any success-triggered
          failure-count reset has been applied.
        - If the breaker was not OPEN, the failure count has already been reset
          to zero before this callback.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify subscribers that the breaker transitioned to OPEN.

        Guarantees:
        - Emitted exactly once per transition to OPEN.
        - Never emitted while the breaker is already OPEN.
        - The breaker state is OPEN before this callback is invoked.
        - ``context`` is the original caller-supplied context, unchanged.
        """
        ...


# The application-provided notifier instance. Intentionally unassigned here.
NOTIFIER: Notifier

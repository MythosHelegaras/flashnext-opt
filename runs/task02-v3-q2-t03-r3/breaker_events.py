"""Subscriber contract for circuit breaker events.

This module defines the callback signatures that a notifier must support. It
does not implement a notifier. Production code is expected to provide a
module-level object named ``NOTIFIER`` that satisfies :class:`Notifier`.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CallFailedCallback(Protocol):
    """Callback signature for :meth:`Notifier.emit_call_failed`."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Called after a failure has been recorded.

        Guarantees:
        - ``context`` is the original :class:`CallContext` supplied to the
          breaker. ``context.caller_state`` is delivered unchanged.
        - ``failure_count`` is the breaker's internal failure count after the
          increment performed by ``record_failure``.
        - ``threshold`` is the configured failure threshold.
        - The callback is not invoked for invalid contexts or for failures
          ignored because the breaker is already open.
        - If the failure caused a transition to OPEN, the breaker state is
          already OPEN before this callback runs.
        """


class CallSucceededCallback(Protocol):
    """Callback signature for :meth:`Notifier.emit_call_succeeded`."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Called after a success has been recorded.

        Guarantees:
        - ``context`` is the original :class:`CallContext` supplied to the
          breaker. ``context.caller_state`` is delivered unchanged.
        - ``current_state`` is the breaker's state after any mutation caused by
          ``record_success``.
        - If the breaker was not open, its failure count has already been reset
          to zero before this callback runs.
        - If the breaker was open, no failure count reset occurs.
        - The callback is not invoked for invalid contexts.
        """


class BreakerOpenedCallback(Protocol):
    """Callback signature for :meth:`Notifier.emit_breaker_opened`."""

    def __call__(self, breaker_name: str, context: CallContext) -> None:
        """Called when a breaker transitions to OPEN.

        Guarantees:
        - The callback fires exactly once per transition to OPEN.
        - It is not invoked for failures recorded while the breaker is already
          open.
        - ``context`` is the original :class:`CallContext` supplied to the
          breaker. ``context.caller_state`` is delivered unchanged.
        - The breaker state is already OPEN before this callback runs.
        - After ``reset()``, a later transition to OPEN may fire this callback
          again.
        """


class Notifier(Protocol):
    """Notifier contract expected by :class:`CircuitBreaker`."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Emit a call failure event. See :class:`CallFailedCallback`."""

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Emit a call success event. See :class:`CallSucceededCallback`."""

    def emit_breaker_opened(self, breaker_name: str, context: CallContext) -> None:
        """Emit a breaker-opened event. See :class:`BreakerOpenedCallback`."""


NOTIFIER: Notifier

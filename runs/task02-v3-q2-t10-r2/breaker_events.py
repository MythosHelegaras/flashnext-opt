"""Subscriber contract for circuit-breaker notifications.

The notifier itself is intentionally not implemented here. A deployment must
bind a module-level object named ``NOTIFIER`` that exposes the methods below.
This module declares the callback signatures and documents the exact guarantees
carried by those notifications.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CallFailedSubscriber(Protocol):
    """Callback contract for an accepted failed downstream call."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Receive the failed-call event.

        Guarantees:
            - This callback is called exactly once for a failure event that the
              breaker accepts.
            - ``context`` is the original :class:`CallContext` instance supplied
              to :meth:`CircuitBreaker.record_failure`; the breaker passes it
              unchanged and does not inspect or rewrite ``caller_state``.
            - ``failure_count`` is the breaker's internal failure count after
              accepting this failure. If this failure reaches ``threshold``,
              ``failure_count`` equals ``threshold``.
            - ``threshold`` is the breaker's configured failure threshold.
            - This callback is not invoked when the breaker was already OPEN on
              entry, nor when invalid input such as a negative
              ``duration_ms`` is dropped.
        """
        ...


class CallSucceededSubscriber(Protocol):
    """Callback contract for an accepted successful downstream call."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Receive the successful-call event.

        Guarantees:
            - This callback is called exactly once for a success event that the
              breaker accepts.
            - ``context`` is the original :class:`CallContext` instance supplied
              to :meth:`CircuitBreaker.record_success`; the breaker passes it
              unchanged and does not inspect or rewrite ``caller_state``.
            - ``current_state`` is the breaker's state after the success has
              been accepted and any count mutation has already happened. If the
              breaker was not OPEN, its failure count has been reset to zero
              before this callback is invoked.
            - This callback is not invoked when invalid input such as a negative
              ``duration_ms`` is dropped.
        """
        ...


class BreakerOpenedSubscriber(Protocol):
    """Callback contract for the breaker transitioning into OPEN."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Receive the breaker-opened event.

        Guarantees:
            - This callback is called exactly once for a transition into OPEN.
            - ``context`` is the original :class:`CallContext` instance supplied
              to :meth:`CircuitBreaker.record_failure` for the failure that
              reached ``failure_threshold``; the breaker passes it unchanged.
            - This callback is not invoked for failures ignored because the
              breaker was already OPEN, for successes, or for
              :meth:`CircuitBreaker.reset`.
        """
        ...


class Notifier(Protocol):
    """Protocol for the assumed module-level ``NOTIFIER`` object."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Emit a failed-call event.

        The implementation must invoke the configured call-failed subscriber
        contract with the supplied arguments. It must preserve the full
        :class:`CallContext`, including ``caller_state``, unchanged.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Emit a successful-call event.

        The implementation must invoke the configured call-succeeded subscriber
        contract with the supplied arguments. It must preserve the full
        :class:`CallContext`, including ``caller_state``, unchanged.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Emit a breaker-opened event.

        The implementation must invoke the configured breaker-opened subscriber
        contract with the supplied arguments. It must preserve the full
        :class:`CallContext`, including ``caller_state``, unchanged.
        """
        ...


# Deployment supplies this object. This module declares the contract only; it
# does not implement NOTIFIER.
NOTIFIER: Notifier

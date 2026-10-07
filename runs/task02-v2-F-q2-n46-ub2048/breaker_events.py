"""Subscriber contract for circuit breaker events.

This module declares the callback signatures a notifier must support. It does
not implement a notifier. The host application is expected to assign a
module-level ``NOTIFIER`` object before the breaker emits events.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CallFailedCallback(Protocol):
    """Callback signature for a recorded call failure."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Receive a failure event.

        Guarantees:
        - The event is emitted only after the breaker's internal failure count
          has been incremented.
        - If the failure caused the breaker to transition to OPEN, the internal
          state is already OPEN before this callback is invoked.
        - ``context`` is the exact ``CallContext`` object passed to
          ``CircuitBreaker.record_failure``. Its ``caller_state`` is unchanged.
        - ``failure_count`` is the post-increment failure count.
        - ``threshold`` is the configured failure threshold.
        """
        ...


class CallSucceededCallback(Protocol):
    """Callback signature for a recorded call success."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Receive a success event.

        Guarantees:
        - The event is emitted after any state mutation caused by the success.
        - If the breaker was not OPEN, the failure count has already been reset
          to zero before this callback is invoked.
        - If the breaker was OPEN, no failure-count mutation occurs.
        - ``context`` is the exact ``CallContext`` object passed to
          ``CircuitBreaker.record_success``. Its ``caller_state`` is unchanged.
        - ``current_state`` is the breaker's internal state after the success
          mutation.
        """
        ...


class BreakerOpenedCallback(Protocol):
    """Callback signature for a breaker transition to OPEN."""

    def __call__(self, breaker_name: str, context: CallContext) -> None:
        """Receive a breaker-opened event.

        Guarantees:
        - The event is emitted exactly once per transition to OPEN.
        - The event is emitted after the breaker's internal state is already
          OPEN.
        - The event is not emitted if the breaker was already OPEN before the
          failure was recorded.
        - ``context`` is the exact ``CallContext`` object passed to
          ``CircuitBreaker.record_failure``. Its ``caller_state`` is unchanged.
        """
        ...


class Notifier(Protocol):
    """Notifier object contract used by ``CircuitBreaker``."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Emit a call failure event.

        Guarantees are documented on ``CallFailedCallback``.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Emit a call success event.

        Guarantees are documented on ``CallSucceededCallback``.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Emit a breaker-opened event.

        Guarantees are documented on ``BreakerOpenedCallback``.
        """
        ...


# The host application assigns this module-level object. It is intentionally
# not implemented here.
NOTIFIER: Notifier

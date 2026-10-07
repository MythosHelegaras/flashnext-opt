"""Subscriber contract for circuit breaker notifications.

The notifier itself is not implemented here. The runtime is assumed to provide
a module-level ``NOTIFIER`` object conforming to :class:`Notifier`.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Callback signatures required of the notifier.

    Callbacks may be invoked synchronously from breaker methods and may
    reenter those methods.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify subscribers that a call failed.

        Guarantees:
        - Called only from ``CircuitBreaker.record_failure`` after the failure
          count has been incremented.
        - ``context`` is the original immutable ``CallContext``; its
          ``caller_state`` is unchanged.
        - ``failure_count`` is the post-increment failure count for the breaker.
        - ``threshold`` is the configured failure threshold.
        - If this failure caused a transition to OPEN, ``emit_breaker_opened``
          is emitted after this callback returns.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify subscribers that a call succeeded.

        Guarantees:
        - Called only from ``CircuitBreaker.record_success`` after any
          success-side mutation has occurred.
        - If the breaker was not open, the failure count has already been reset
          to zero.
        - If the breaker was open, the failure count has not been reset.
        - ``context`` is the original immutable ``CallContext``; its
          ``caller_state`` is unchanged.
        - ``current_state`` is the breaker's state after mutation.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify subscribers that the breaker transitioned to OPEN.

        Guarantees:
        - Called exactly once per transition to OPEN.
        - Not called for subsequent failures while the breaker remains OPEN.
        - Called after the corresponding ``emit_call_failed`` notification for
          the failure that caused the transition.
        - ``context`` is the original immutable ``CallContext``; its
          ``caller_state`` is unchanged.
        """
        ...


NOTIFIER: Notifier  # Provided externally; this module does not implement it.

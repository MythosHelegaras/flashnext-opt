"""Subscriber contracts for circuit breaker notifications.

The production environment supplies a module-level `NOTIFIER` object. This
module defines the required method signatures and the guarantees attached to
them. The notifier itself is not implemented here.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Notifier contract required by `CircuitBreaker`.

    A `NOTIFIER` is the sole point of contact between the breaker and
    subscribers. It must expose the methods below.

    Callbacks receive `context` exactly as it was supplied to the breaker.
    The breaker does not filter, remap, or reinterpret `context.caller_state`.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Report one valid failure to subscribers.

        Guarantees:
            - `context` is unchanged.
            - `failure_count` is the post-mutation failure count.
            - `threshold` is the configured failure threshold.
            - If the failure reaches the threshold, the breaker's internal
              state has already transitioned to `OPEN` before this callback is
              invoked.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Report one valid success to subscribers.

        Guarantees:
            - `context` is unchanged.
            - `current_state` is the breaker's internal state after any
              non-open success mutation. It is `CLOSED` for a closed breaker
              and `OPEN` for an open breaker; it is not copied from
              `context.caller_state`.
            - If the breaker was not open, its failure count has already been
              reset to zero before this callback is invoked.
            - If the breaker was open, its failure count is not reset.
        """
        ...

    def emit_breaker_opened(
        self, breaker_name: str, context: CallContext
    ) -> None:
        """Report a transition to `OPEN`.

        Guarantees:
            - `context` is the call context whose failure caused the
              transition.
            - The callback fires exactly once per closed-to-open transition.
            - It does not fire again while the breaker is already open.
        """
        ...

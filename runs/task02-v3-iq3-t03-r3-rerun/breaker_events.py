"""Subscriber contract for circuit breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Callback contract that the module-level NOTIFIER must satisfy."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify subscribers that an accepted failure has been recorded.

        Guarantees:
        - Called only after the breaker's failure count has been incremented.
        - `context` is the exact CallContext passed to record_failure. The
          breaker does not mutate, filter, remap, or reinterpret
          `context.caller_state`.
        - `failure_count` is the post-mutation failure count for this failure.
        - `threshold` is the breaker's configured failure threshold.
        - Not called for invalid contexts with negative duration_ms.
        - Not called for failures received while the breaker is already open.
        - May be called for the failure that causes the breaker to transition
          to open. In that case, the open guard is already in its
          post-mutation state before this callback runs.
        - For a failure that causes the transition, this callback is emitted
          before emit_breaker_opened.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify subscribers that an accepted success has been recorded.

        Guarantees:
        - Called after any success mutation. If the breaker is not open, the
          failure count has already been reset to zero before this callback
          runs.
        - If the breaker is open, the failure count is not reset.
        - `context` is the exact CallContext passed to record_success,
          unchanged.
        - `current_state` is `context.caller_state`, unchanged. It is the
          caller's state, not a breaker-derived state.
        - Not called for invalid contexts with negative duration_ms.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify subscribers that the breaker has transitioned to open.

        Guarantees:
        - Called exactly once per transition from not-open to open.
        - Not called while the breaker is already open.
        - Called after the open guard is set, so reentrant record_failure calls
          are ignored.
        - `context` is the CallContext of the failure that caused the
          transition, unchanged.
        - Called after emit_call_failed for the same failure.
        """
        ...


# The concrete notifier object must be assigned to this module-level name
# before CircuitBreaker emits events.
NOTIFIER: Notifier

# breaker_events.py
"""Subscriber contract for breaker event notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class BreakerNotifier(Protocol):
    """Protocol required by the production-provided `NOTIFIER` object.

    Production code must bind a module-level object named `NOTIFIER`
    implementing this protocol before breaker methods perform notifications:

        breaker_events.NOTIFIER = MyNotifier()
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify that an accepted downstream call failed.

        Guarantees:
          - The breaker has already incremented its internal failure count.
          - If the failure crossed the threshold, the breaker has already
            transitioned to `BreakerState.OPEN` before this notification is
            prepared.
          - `context` is the caller-provided `CallContext`, passed unchanged.
          - `failure_count` is the breaker's count after mutation.
          - `threshold` is the configured failure threshold.
          - This event does not, by itself, indicate whether the breaker is
            now open; the threshold crossing is observable through
            `failure_count` and `threshold`.
        """

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify that an accepted downstream call succeeded.

        Guarantees:
          - If the breaker was not open before the success was accepted, its
            failure count has already been reset to zero before this
            notification is prepared.
          - If the breaker was open, its failure count has not been reset.
          - `context` is the caller-provided `CallContext`, passed unchanged.
          - `current_state` is the breaker state after mutation and before
            emission.
        """

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify that the breaker transitioned to `OPEN`.

        Guarantees:
          - It is prepared only after a mutation from a non-open state to
            `BreakerState.OPEN`.
          - It fires exactly once for each such transition.
          - It is never prepared for a failure while the breaker was already
            open.
          - It is not emitted by `reset()`.
          - `context` is the failure context that caused the transition,
            passed unchanged.
        """


NOTIFIER: BreakerNotifier

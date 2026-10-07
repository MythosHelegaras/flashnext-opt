"""Subscriber contract for circuit breaker notifications.

The runtime environment must provide a module-level ``NOTIFIER`` object that
satisfies ``CircuitBreakerNotifier``. This module intentionally does not
implement the notifier.

Production injection example:

    import breaker_events
    breaker_events.NOTIFIER = production_notifier
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreakerNotifier(Protocol):
    """Callback contract implemented by the external NOTIFIER object."""

    def emit_call_failed(
        self: "CircuitBreakerNotifier",
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify that a failure was accepted by the breaker.

        Guarantees:
        - Called synchronously exactly once for each valid failure accepted by
          ``CircuitBreaker.record_failure``.
        - The breaker has already incremented its failure count before this
          callback begins.
        - If this accepted failure transitions the breaker to OPEN, the state
          mutation has already happened before the first notification for the
          failure. Subscriber reentry after this callback may further mutate
          state before ``emit_breaker_opened``.
        - ``context`` is the exact object passed to ``record_failure``. Its
          ``caller_state`` is unchanged and is not filtered, remapped, or
          reinterpreted.
        - ``failure_count`` is the post-increment failure count for this
          accepted failure.
        - ``threshold`` is the breaker's configured failure threshold.
        - This callback does not by itself indicate whether
          ``emit_breaker_opened`` will be emitted; that event is emitted only
          for a new transition to OPEN.
        """
        ...

    def emit_call_succeeded(
        self: "CircuitBreakerNotifier",
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify that a success was accepted by the breaker.

        Guarantees:
        - Called synchronously exactly once for each valid success accepted by
          ``CircuitBreaker.record_success``.
        - If the breaker was not open when ``record_success`` began, its failure
          count has already been reset to zero before this callback begins.
        - If the breaker was open when ``record_success`` began, no failure
          count or breaker state mutation occurs.
        - ``current_state`` is the breaker's internal state after any mutation
          performed by ``record_success`` and before this callback begins. For
          ``CircuitBreaker``, this is ``BreakerState.CLOSED`` when not open and
          ``BreakerState.OPEN`` when open.
        - ``context`` is the exact object passed to ``record_success``. Its
          ``caller_state`` is unchanged and is not filtered, remapped, or
          reinterpreted.
        """
        ...

    def emit_breaker_opened(
        self: "CircuitBreakerNotifier",
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify that the breaker transitioned to OPEN.

        Guarantees:
        - Called synchronously exactly once for each new transition from not
          open to OPEN caused by an accepted failure reaching the threshold.
        - Never called for failures that occur while the breaker is already
          open.
        - In ``CircuitBreaker.record_failure``, it is emitted after
          ``emit_call_failed`` for the same failure and before
          ``record_failure`` returns.
        - The event records the transition caused by that
          ``record_failure`` call. If a subscriber re-enters after the preceding
          callback, the current breaker state may have changed before this
          callback, but the transition itself occurred once.
        - ``context`` is the exact object passed to ``record_failure``. Its
          ``caller_state`` is unchanged and is not filtered, remapped, or
          reinterpreted.
        """
        ...


NOTIFIER: CircuitBreakerNotifier

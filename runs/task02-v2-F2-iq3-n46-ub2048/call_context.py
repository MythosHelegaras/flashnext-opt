"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one downstream call attempt.

    The fields are exactly:
        duration_ms: elapsed call duration in milliseconds.
        endpoint: target endpoint, or None for anonymous calls.
        caller_state: caller-authored breaker state at call issue.

    CallContext.caller_state is a load-bearing product requirement.
    CircuitBreaker passes the original context to subscribers unchanged and
    never filters, remaps, or reinterprets caller_state.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

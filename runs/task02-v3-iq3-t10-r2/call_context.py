"""Immutable per-call context used by circuit breaker subscribers."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of a single downstream call attempt.

    Attributes:
        duration_ms: How long the call took, in milliseconds.
        endpoint: Target of the call, or `None` for anonymous calls.
        caller_state: The caller's view of breaker state when the call was
            issued. This value is load-bearing and must reach every subscriber
            unchanged.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

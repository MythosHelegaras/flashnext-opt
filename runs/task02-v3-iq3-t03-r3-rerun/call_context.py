"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one downstream call attempt.

    Attributes:
        duration_ms: How long the call took, in milliseconds.
        endpoint: Target endpoint, or None for anonymous calls.
        caller_state: Caller's view of breaker state when the call was issued.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

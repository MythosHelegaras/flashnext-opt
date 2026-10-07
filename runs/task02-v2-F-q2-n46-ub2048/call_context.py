"""Immutable description of a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable context for one downstream call attempt.

    Attributes:
        duration_ms: How long the call took, in milliseconds.
        endpoint: The target endpoint, or None for anonymous calls.
        caller_state: The caller's view of breaker state when the call was issued.
    """

    duration_ms: int
    """How long the call took, in milliseconds."""

    endpoint: str | None
    """The target endpoint, or None for anonymous calls."""

    caller_state: BreakerState
    """The caller's view of breaker state when the call was issued."""

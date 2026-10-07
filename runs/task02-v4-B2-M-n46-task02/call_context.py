"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one downstream call attempt.

    ``caller_state`` is the caller's view of breaker state when the call was
    issued. It must reach every subscriber unchanged.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

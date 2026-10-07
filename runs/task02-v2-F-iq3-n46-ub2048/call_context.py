# call_context.py
"""
Immutable context for a single downstream call attempt.

CallContext carries exactly three fields. Its caller_state field is the
caller's view of breaker state at the moment the call was issued. That value
is load-bearing and must reach every subscriber unchanged.
"""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one call attempt."""

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

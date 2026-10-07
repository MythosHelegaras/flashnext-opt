"""Immutable description of a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """
    Immutable context for one downstream call attempt.

    caller_state is caller-authored and must be delivered to subscribers
    unchanged. The breaker does not filter, remap, or reinterpret it.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

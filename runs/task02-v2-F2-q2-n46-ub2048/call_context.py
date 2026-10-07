# call_context.py
"""Immutable context describing a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """
    Immutable description of one downstream call attempt.

    `caller_state` is a load-bearing product requirement. It must reach every
    subscriber unchanged; the breaker must not filter, remap, or reinterpret it.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

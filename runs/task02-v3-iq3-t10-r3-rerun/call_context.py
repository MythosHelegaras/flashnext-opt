# call_context.py
"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable record of one downstream call attempt.

    `CallContext` instances are passed to subscribers unchanged. The breaker
    must not filter, remap, or reinterpret `caller_state`.
    """

    duration_ms: int
    """How long the call took, in milliseconds.

    Negative values are invalid input and are dropped by breaker methods
    with a warning rather than raising an exception.
    """

    endpoint: str | None
    """The target endpoint, or `None` for anonymous calls."""

    caller_state: BreakerState
    """The caller's view of breaker state when the call was issued.

    This is load-bearing product data and must reach every subscriber
    unchanged.
    """

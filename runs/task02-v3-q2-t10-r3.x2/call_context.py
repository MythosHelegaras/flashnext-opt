"""
Immutable description of a single downstream call attempt.
"""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """
    Immutable value object describing one downstream call attempt.

    Fields:
        duration_ms:
            Duration of the call in milliseconds.
        endpoint:
            Target endpoint, or `None` for anonymous calls.
        caller_state:
            Caller-authored view of breaker state at the moment the call was
            issued.

    `caller_state` is load-bearing. It must reach every subscriber unchanged.
    The breaker must not filter, remap, or reinterpret it.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState


CallContext.__init__.__doc__ = (
    "Initialize a CallContext with duration_ms, endpoint, and caller_state."
)

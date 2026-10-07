"""Authoritative enumeration of breaker states authored by caller policy.

The members describe how the caller's policy layer views a breaker when
issuing a downstream call. They are data values supplied by the caller; the
breaker itself does not choose them from its failure/success path except to
model its own OPEN/CLOSED transitions.
"""

from enum import Enum, auto


class BreakerState(Enum):
    """Caller-authored view of a circuit breaker."""

    CLOSED = auto()
    """The caller sees the breaker as admitting calls and tracking failures."""

    OPEN = auto()
    """The caller sees the breaker as rejecting calls or treating them as failed."""

    HALF_OPEN = auto()
    """The caller sees the breaker as allowing probe calls to assess recovery."""


BreakerState.CLOSED.__doc__ = (
    "The caller sees the breaker as admitting calls and tracking failures."
)
BreakerState.OPEN.__doc__ = (
    "The caller sees the breaker as rejecting calls or treating them as failed."
)
BreakerState.HALF_OPEN.__doc__ = (
    "The caller sees the breaker as allowing probe calls to assess recovery."
)

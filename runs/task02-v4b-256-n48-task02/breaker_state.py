"""Breaker states authored by caller policy layers."""

from enum import Enum, auto


class BreakerState(Enum):
    """
    The three breaker states used by callers and subscribers.

    These values are authored by the caller's policy layer and carried through
    CallContext. The breaker's failure path does not decide them.
    """

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


BreakerState.CLOSED.__doc__ = (
    "The caller's policy considers the breaker closed. Calls are allowed and "
    "failures may accumulate."
)
BreakerState.OPEN.__doc__ = (
    "The caller's policy considers the breaker open. Calls are expected to be "
    "rejected or bypassed."
)
BreakerState.HALF_OPEN.__doc__ = (
    "The caller's policy considers the breaker half-open. Trial calls are being "
    "allowed to probe recovery."
)

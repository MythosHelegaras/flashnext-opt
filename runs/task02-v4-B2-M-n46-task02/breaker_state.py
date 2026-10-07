"""Breaker states authored by caller policy."""

from enum import Enum, auto


class BreakerState(Enum):
    """Breaker state supplied by the caller's policy layer.

    These values describe the caller's view at the moment a call is issued.
    They are never decided inside the breaker's failure path.
    """

    CLOSED = auto()
    """Caller policy considers the breaker closed and normal calls allowed."""

    OPEN = auto()
    """Caller policy considers the breaker open; the breaker failure path does not set this value."""

    HALF_OPEN = auto()
    """Caller policy considers the breaker half-open; the breaker failure path does not set this value."""


BreakerState.CLOSED.__doc__ = (
    "Caller policy considers the breaker closed and normal calls allowed."
)
BreakerState.OPEN.__doc__ = (
    "Caller policy considers the breaker open; the breaker failure path does not set this value."
)
BreakerState.HALF_OPEN.__doc__ = (
    "Caller policy considers the breaker half-open; the breaker failure path does not set this value."
)

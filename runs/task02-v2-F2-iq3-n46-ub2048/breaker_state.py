"""Breaker state enum for caller-authored policy states."""

from enum import Enum


class BreakerState(Enum):
    """Policy states supplied by the caller's policy layer.

    These values describe the caller's view of a circuit breaker at the time
    a call was issued. They are authored by the caller and are not inferred,
    filtered, remapped, or rewritten by CircuitBreaker.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


BreakerState.CLOSED.__doc__ = (
    "Caller policy state: the breaker is closed and calls are allowed."
)
BreakerState.OPEN.__doc__ = (
    "Caller policy state: the breaker is open and calls are not allowed."
)
BreakerState.HALF_OPEN.__doc__ = (
    "Caller policy state: the breaker is half-open and probing with limited calls."
)

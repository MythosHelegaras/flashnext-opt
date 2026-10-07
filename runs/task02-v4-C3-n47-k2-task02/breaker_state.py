"""Breaker state values authored by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """
    State values supplied by the caller's policy layer.

    These values describe the caller's view of a breaker at the moment a call
    was issued. The circuit breaker's failure path does not decide or
    reinterpret the ``caller_state`` value carried by ``CallContext``.
    """

    CLOSED = auto()
    """The caller's policy layer considers the breaker closed."""

    OPEN = auto()
    """The caller's policy layer considers the breaker open."""

    HALF_OPEN = auto()
    """The caller's policy layer considers the breaker half-open."""


__all__ = ["BreakerState"]

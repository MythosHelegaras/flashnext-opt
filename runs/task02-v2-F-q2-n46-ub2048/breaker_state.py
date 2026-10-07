"""Enumeration of breaker states authored by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """The caller's view of circuit breaker state.

    These values are authored by the caller's policy layer. The breaker does
    not decide or reinterpret them in its failure path.
    """

    CLOSED = auto()
    """The caller considers the breaker closed and calls are permitted."""

    OPEN = auto()
    """The caller considers the breaker open and calls are not permitted."""

    HALF_OPEN = auto()
    """The caller considers the breaker half-open and trial calls are permitted."""

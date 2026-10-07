# breaker_state.py
"""Breaker states authored by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """The three states a caller may report for a circuit breaker."""

    CLOSED = auto()
    """The breaker is closed and calls are permitted."""

    OPEN = auto()
    """The breaker is open and calls are expected to be rejected."""

    HALF_OPEN = auto()
    """The breaker is half-open and is probing with limited calls."""

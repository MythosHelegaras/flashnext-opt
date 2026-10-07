# breaker_state.py
"""
Breaker state enum.

The values in this enum are authored by the caller's policy layer. The
circuit breaker's failure path does not decide which caller_state a call
context carries; it only records its own internal open/closed state.
"""

from enum import Enum


class BreakerState(Enum):
    """Breaker states visible to callers and subscribers."""

    CLOSED = "closed"
    """Closed: calls are allowed and failures are counted normally."""

    OPEN = "open"
    """Open: the breaker is not accepting new failure recording."""

    HALF_OPEN = "half_open"
    """Half-open: caller policy may probe with limited calls."""

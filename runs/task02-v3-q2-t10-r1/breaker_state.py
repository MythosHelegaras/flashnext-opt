"""States selected by caller policy for circuit-breaker interactions.

These values are authored outside the circuit breaker. CircuitBreaker never
decides to enter HALF_OPEN; that choice belongs to the caller's policy layer.
"""

from enum import Enum, auto


class BreakerState(Enum):
    """Authoritative breaker state carried by CallContext."""

    CLOSED = auto()
    """The circuit is closed and calls are expected to succeed."""

    OPEN = auto()
    """The circuit is open and additional failures must not be recorded."""

    HALF_OPEN = auto()
    """The circuit is probing and is selected only by caller policy."""

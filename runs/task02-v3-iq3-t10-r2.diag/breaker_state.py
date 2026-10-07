"""Breaker state values authored by the caller's policy layer."""

from enum import Enum


class BreakerState(Enum):
    """States of a circuit breaker as understood by the caller's policy layer.

    These values are authored externally. The breaker failure path never
    decides, filters, remaps, or reinterprets them.
    """

    CLOSED = "closed"
    """Caller-authored state indicating that calls are allowed."""

    OPEN = "open"
    """Caller-authored state indicating that calls are blocked."""

    HALF_OPEN = "half_open"
    """Caller-authored state indicating a trial or probing window."""

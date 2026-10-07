"""Breaker state values supplied by caller policy layers."""

from enum import Enum, auto


class BreakerState(Enum):
    """Breaker state enum authored by the caller's policy layer.

    The values used in ``CallContext.caller_state`` are supplied by the caller.
    The circuit breaker passes them through unchanged and does not filter,
    remap, or reinterpret them.
    """

    CLOSED = auto()
    """Caller policy view indicating normal operation: calls may be issued."""

    OPEN = auto()
    """Caller policy view indicating calls should not be issued."""

    HALF_OPEN = auto()
    """Caller policy view indicating limited trial calls may be issued."""

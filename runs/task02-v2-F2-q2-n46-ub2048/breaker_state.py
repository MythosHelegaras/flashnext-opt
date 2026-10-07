# breaker_state.py
"""Breaker state values authored by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """
    Breaker state as seen by the caller's policy layer.

    These values are authored outside the breaker's failure path. The breaker
    must pass them through unchanged and must not reinterpret them.
    """

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


BreakerState.CLOSED.__doc__ = """
The caller believes the breaker is closed and calls are expected to be allowed.
"""
BreakerState.OPEN.__doc__ = """
The caller believes the breaker is open and calls are expected to be blocked.
"""
BreakerState.HALF_OPEN.__doc__ = """
The caller believes the breaker is half-open and trial calls are expected.
"""

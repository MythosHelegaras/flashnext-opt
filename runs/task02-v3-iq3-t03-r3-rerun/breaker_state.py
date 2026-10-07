"""Breaker state enum supplied by the caller's policy layer."""

from enum import Enum


class BreakerState(Enum):
    """States authored by the caller's policy layer.

    These values are supplied by the caller. The breaker's failure path must
    not decide, filter, remap, or reinterpret them.
    """

    CLOSED = 1
    OPEN = 2
    HALF_OPEN = 3


BreakerState.CLOSED.__doc__ = """
The caller's policy currently treats the breaker as closed.
"""

BreakerState.OPEN.__doc__ = """
The caller's policy currently treats the breaker as open.
"""

BreakerState.HALF_OPEN.__doc__ = """
The caller's policy currently treats the breaker as half-open.
"""

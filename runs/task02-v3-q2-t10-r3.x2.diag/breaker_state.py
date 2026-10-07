"""
Breaker state enum authored by the caller's policy layer.

This enum is intentionally external to breaker failure logic. It describes the
state the caller believes the breaker is in when a call is issued.
"""

from enum import Enum, auto


class BreakerState(Enum):
    """
    Caller-authored breaker state.

    This value is descriptive only. It must be supplied by the caller's policy
    layer and must never be decided, derived, filtered, remapped, or
    reinterpreted inside the breaker's failure path.
    """

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


BreakerState.CLOSED.__doc__ = """
Caller-side view: the caller believes no breaker restriction is active.
"""

BreakerState.OPEN.__doc__ = """
Caller-side view: the caller believes the breaker is blocking calls.
"""

BreakerState.HALF_OPEN.__doc__ = """
Caller-side view: the caller believes the breaker is allowing a trial call to
test whether recovery is possible.
"""

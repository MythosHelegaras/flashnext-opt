# breaker_state.py
"""Breaker state enum supplied by caller policy."""

from enum import Enum, auto


class BreakerState(Enum):
    """States authored by the caller policy layer.

    These values are used by the caller to describe its own view of breaker
    state in `CallContext.caller_state`. The breaker does not infer, filter,
    remap, or reinterpret that carried value.
    """

    CLOSED = auto()
    """Caller-policy state indicating normal call eligibility.

    A breaker instance begins in this state and returns to it after
    `reset()`.
    """

    OPEN = auto()
    """Caller-policy state indicating that calls are being treated as open.

    The breaker may enter this state after its own failure threshold is
    reached. While a breaker instance is internally open, further failure
    recording is ignored.
    """

    HALF_OPEN = auto()
    """Caller-policy probing state.

    This member exists for the caller policy layer to describe a trial or
    half-open call. The breaker never selects this state in its failure path.
    """

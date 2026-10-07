"""Breaker state values authored by the caller's policy layer."""

from enum import Enum


class BreakerState(Enum):
    """The three breaker states used by callers and subscribers.

    These values are authored by the caller's policy layer. The circuit
    breaker's failure path does not decide what ``caller_state`` means; it
    passes the value through unchanged.
    """

    CLOSED = (
        "closed",
        "The breaker is closed; calls are permitted and failures are counted.",
    )
    OPEN = (
        "open",
        "The breaker is open; the caller's policy treats calls as unavailable.",
    )
    HALF_OPEN = (
        "half_open",
        "The breaker is half-open; the caller's policy is probing recovery.",
    )

    def __init__(self, value: str, doc: str) -> None:
        """Initialize a breaker state value and attach its member documentation."""
        self._value_ = value
        self.__doc__ = doc

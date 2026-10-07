"""Immutable description of a single downstream call attempt.

This type is intentionally small. It is passed by reference to subscribers and
must not be altered by the breaker.
"""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True, init=False)
class CallContext:
    """Immutable record for a single downstream call attempt.

    Fields
    -----
    duration_ms: int
        How long the call took, in milliseconds.

    endpoint: str | None
        The endpoint being called, or ``None`` for anonymous calls.

    caller_state: BreakerState
        The caller's view of breaker state when the call was issued.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

    def __init__(
        self,
        duration_ms: int,
        endpoint: str | None,
        caller_state: BreakerState,
    ) -> None:
        """Create a CallContext.

        Args:
            duration_ms: Duration of the call in milliseconds.
            endpoint: Target endpoint, or ``None`` for anonymous calls.
            caller_state: Caller's breaker state view at call issue time.
        """
        object.__setattr__(self, "duration_ms", duration_ms)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "caller_state", caller_state)

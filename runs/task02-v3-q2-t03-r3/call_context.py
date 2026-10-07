"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True, init=False)
class CallContext:
    """Immutable description of one downstream call attempt.

    ``caller_state`` is authored by the caller's policy layer. It must reach
    every subscriber unchanged. The circuit breaker must not filter, remap, or
    reinterpret it.
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
        """Initialize a call context.

        Args:
            duration_ms: How long the call took, in milliseconds.
            endpoint: The target endpoint, or ``None`` for anonymous calls.
            caller_state: The caller's view of breaker state when the call was
                issued.
        """
        object.__setattr__(self, "duration_ms", duration_ms)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "caller_state", caller_state)

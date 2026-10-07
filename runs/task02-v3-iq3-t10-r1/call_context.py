"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of one downstream call attempt.

    Attributes:
        duration_ms:
            Time the call took, in milliseconds. Negative durations are invalid
            and are ignored by ``CircuitBreaker`` with a warning.
        endpoint:
            Target endpoint, or ``None`` for anonymous calls.
        caller_state:
            Breaker state view supplied by the caller's policy layer when the
            call was issued. ``CircuitBreaker`` forwards this value unchanged to
            every subscriber callback.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

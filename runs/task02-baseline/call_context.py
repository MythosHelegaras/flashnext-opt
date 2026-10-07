# call_context.py
"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """An immutable description of one downstream call attempt.

    ``caller_state`` is supplied by the caller's policy layer. It is
    load-bearing: the circuit breaker must pass the whole context to
    subscribers unchanged.
    """

    duration_ms: int
    """How long the call took, in milliseconds."""

    endpoint: str | None
    """The target endpoint, or ``None`` for anonymous calls."""

    caller_state: BreakerState
    """The caller's view of breaker state when the call was issued."""

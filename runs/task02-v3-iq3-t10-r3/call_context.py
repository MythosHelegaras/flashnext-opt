"""Immutable context describing one downstream call attempt."""

from breaker_state import BreakerState


class CallContext:
    """Immutable context for a single downstream call attempt.

    Exactly three fields are present:
    ``duration_ms``, ``endpoint``, and ``caller_state``.

    The context is intended to reach every subscriber unchanged. In particular,
    ``caller_state`` is the caller policy layer's view at call issue time and
    must not be filtered, remapped, or reinterpreted by the breaker.
    """

    __slots__ = ("duration_ms", "endpoint", "caller_state")

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState

    def __init__(
        self: "CallContext",
        duration_ms: int,
        endpoint: str | None,
        caller_state: BreakerState,
    ) -> None:
        """Create an immutable call context.

        Args:
            duration_ms: Call duration in milliseconds.
            endpoint: Target endpoint, or None for anonymous calls.
            caller_state: Caller policy view of breaker state at call issue time.
        """
        object.__setattr__(self, "duration_ms", duration_ms)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "caller_state", caller_state)

    def __setattr__(self: "CallContext", name: str, value: object) -> None:
        """Reject mutation attempts to preserve immutability."""
        raise AttributeError(f"CallContext is immutable: cannot set {name!r}")

    def __delattr__(self: "CallContext", name: str) -> None:
        """Reject deletion attempts to preserve immutability."""
        raise AttributeError(f"CallContext is immutable: cannot delete {name!r}")

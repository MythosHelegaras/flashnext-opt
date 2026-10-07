"""Immutable metadata for one downstream call attempt."""

from breaker_state import BreakerState


class CallContext:
    """Immutable metadata describing one downstream call attempt.

    Negative duration_ms values are not rejected when constructing a context.
    CircuitBreaker treats them as invalid event input and drops them with a
    warning instead of raising an exception.
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

        The context carries the caller-authored breaker state unchanged. A
        breaker must pass this object through to subscribers without filtering,
        remapping, or otherwise interpreting caller_state.
        """
        object.__setattr__(self, "duration_ms", duration_ms)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "caller_state", caller_state)

    def __setattr__(self: "CallContext", name: str, value: object) -> None:
        """Reject any mutation of a CallContext field."""
        raise AttributeError("CallContext is immutable")

    def __delattr__(self: "CallContext", name: str) -> None:
        """Reject deletion of any CallContext field."""
        raise AttributeError("CallContext is immutable")

    def __repr__(self: "CallContext") -> str:
        """Return a debug representation of the call context."""
        return (
            f"CallContext(duration_ms={self.duration_ms!r}, "
            f"endpoint={self.endpoint!r}, "
            f"caller_state={self.caller_state!r})"
        )

    def __eq__(self: "CallContext", other: object) -> bool:
        """Compare field values with another CallContext."""
        if not isinstance(other, CallContext):
            return NotImplemented

        return (
            self.duration_ms == other.duration_ms
            and self.endpoint == other.endpoint
            and self.caller_state is other.caller_state
        )

    def __hash__(self: "CallContext") -> int:
        """Return a hash consistent with __eq__."""
        return hash((self.duration_ms, self.endpoint, self.caller_state))

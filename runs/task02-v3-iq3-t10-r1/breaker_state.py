"""Authoritative breaker state values supplied by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """Breaker states authored by the caller policy layer.

    Each member describes a policy view carried by ``CallContext.caller_state``.
    ``CircuitBreaker`` may maintain an internal state using these member names,
    but it must not filter, remap, or reinterpret a context's ``caller_state``.
    """

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


BreakerState.CLOSED.__doc__ = """
Caller-authored state for normal operation.

The policy layer considers downstream calls acceptable. A circuit breaker may
internally use this member for its own non-open state, but a context's
``caller_state`` is never chosen or rewritten by the breaker failure path.
"""

BreakerState.OPEN.__doc__ = """
Caller-authored state for rejection.

The policy layer considers new downstream attempts not acceptable. A circuit
breaker may transition its internal state to this member when its failure
threshold is reached; however, a context's ``caller_state`` must remain unchanged
when passed to subscribers.
"""

BreakerState.HALF_OPEN.__doc__ = """
Caller-authored state for probing or limited admission.

The policy layer considers the path neither fully normal nor fully rejected.
``CircuitBreaker`` must not reinterpret this value when forwarding contexts to
subscriber callbacks.
"""

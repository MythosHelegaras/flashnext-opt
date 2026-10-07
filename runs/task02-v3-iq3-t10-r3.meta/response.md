Below are the four files.

## `breaker_state.py`

```python
"""Breaker state values supplied by caller policy layers."""

from enum import Enum, auto


class BreakerState(Enum):
    """Breaker state enum authored by the caller's policy layer.

    The values used in ``CallContext.caller_state`` are supplied by the caller.
    The circuit breaker passes them through unchanged and does not filter,
    remap, or reinterpret them.
    """

    CLOSED = auto()
    """Caller policy view indicating normal operation: calls may be issued."""

    OPEN = auto()
    """Caller policy view indicating calls should not be issued."""

    HALF_OPEN = auto()
    """Caller policy view indicating limited trial calls may be issued."""
```

## `call_context.py`

```python
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
```

## `breaker_events.py`

```python
"""Subscriber contract for circuit breaker notifications.

The runtime environment must provide a module-level ``NOTIFIER`` object that
satisfies ``CircuitBreakerNotifier``. This module intentionally does not
implement the notifier.

Production injection example:

    import breaker_events
    breaker_events.NOTIFIER = production_notifier
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreakerNotifier(Protocol):
    """Callback contract implemented by the external NOTIFIER object."""

    def emit_call_failed(
        self: "CircuitBreakerNotifier",
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify that a failure was accepted by the breaker.

        Guarantees:
        - Called synchronously exactly once for each valid failure accepted by
          ``CircuitBreaker.record_failure``.
        - The breaker has already incremented its failure count before this
          callback begins.
        - If this accepted failure transitions the breaker to OPEN, the state
          mutation has already happened before the first notification for the
          failure. Subscriber reentry after this callback may further mutate
          state before ``emit_breaker_opened``.
        - ``context`` is the exact object passed to ``record_failure``. Its
          ``caller_state`` is unchanged and is not filtered, remapped, or
          reinterpreted.
        - ``failure_count`` is the post-increment failure count for this
          accepted failure.
        - ``threshold`` is the breaker's configured failure threshold.
        - This callback does not by itself indicate whether
          ``emit_breaker_opened`` will be emitted; that event is emitted only
          for a new transition to OPEN.
        """
        ...

    def emit_call_succeeded(
        self: "CircuitBreakerNotifier",
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify that a success was accepted by the breaker.

        Guarantees:
        - Called synchronously exactly once for each valid success accepted by
          ``CircuitBreaker.record_success``.
        - If the breaker was not open when ``record_success`` began, its failure
          count has already been reset to zero before this callback begins.
        - If the breaker was open when ``record_success`` began, no failure
          count or breaker state mutation occurs.
        - ``current_state`` is the breaker's internal state after any mutation
          performed by ``record_success`` and before this callback begins. For
          ``CircuitBreaker``, this is ``BreakerState.CLOSED`` when not open and
          ``BreakerState.OPEN`` when open.
        - ``context`` is the exact object passed to ``record_success``. Its
          ``caller_state`` is unchanged and is not filtered, remapped, or
          reinterpreted.
        """
        ...

    def emit_breaker_opened(
        self: "CircuitBreakerNotifier",
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify that the breaker transitioned to OPEN.

        Guarantees:
        - Called synchronously exactly once for each new transition from not
          open to OPEN caused by an accepted failure reaching the threshold.
        - Never called for failures that occur while the breaker is already
          open.
        - In ``CircuitBreaker.record_failure``, it is emitted after
          ``emit_call_failed`` for the same failure and before
          ``record_failure`` returns.
        - The event records the transition caused by that
          ``record_failure`` call. If a subscriber re-enters after the preceding
          callback, the current breaker state may have changed before this
          callback, but the transition itself occurred once.
        - ``context`` is the exact object passed to ``record_failure``. Its
          ``caller_state`` is unchanged and is not filtered, remapped, or
          reinterpreted.
        """
        ...


NOTIFIER: CircuitBreakerNotifier
```

## `circuit_breaker.py`

```python
"""A failure-count circuit breaker that communicates only through NOTIFIER."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """Failure-count circuit breaker.

    The breaker's only external contact is ``breaker_events.NOTIFIER``. It does
    not store or interpret ``CallContext.caller_state``; it passes context
    objects to NOTIFIER unchanged. Internal state is used only to decide whether
    failures are ignored and whether a transition to OPEN has occurred.
    """

    def __init__(
        self: "CircuitBreaker",
        name: str,
        failure_threshold: int = 5,
    ) -> None:
        """Initialize a CLOSED breaker with a zero failure count.

        Args:
            name: Breaker name supplied to every NOTIFIER callback.
            failure_threshold: Count at which ``record_failure`` transitions the
                breaker to OPEN.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self: "CircuitBreaker", context: CallContext) -> None:
        """Record a downstream failure.

        A negative ``context.duration_ms`` is dropped with a warning and causes
        no state mutation or notification.

        If the breaker is already OPEN, the failure is ignored entirely.

        Otherwise, the failure count is incremented, and if the count reaches
        ``failure_threshold`` the breaker state is mutated to OPEN before any
        subscriber notification fires. The accepted failure then causes:
        - exactly one ``emit_call_failed`` notification with the unchanged
          context, post-increment failure count, and threshold;
        - if this call caused the transition to OPEN, exactly one
          ``emit_breaker_opened
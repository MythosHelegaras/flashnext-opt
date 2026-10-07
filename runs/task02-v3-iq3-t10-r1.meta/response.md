## 1. `breaker_state.py`

```python
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
```

## 2. `call_context.py`

```python
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
```

## 3. `breaker_events.py`

```python
"""Subscriber callback contract for circuit breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreakerNotifier(Protocol):
    """Required notifier interface for ``CircuitBreaker``.

    A module-level object named ``NOTIFIER`` must satisfy this contract. It is
    intentionally not defined here.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify subscribers that a downstream call failed.

        Guarantees:
            - ``context`` is the exact immutable ``CallContext`` supplied by the
              caller.
            - ``context.caller_state`` is passed through unchanged.
            - ``failure_count`` is the breaker's failure count after the accepted
              failure mutation.
            - ``threshold`` is the breaker's configured failure threshold at
              notification time.
            - This callback is not emitted for invalid negative-duration input.
            - This callback is not emitted when the breaker was already open and
              therefore ignored the failure.
            - If this failure caused a transition to ``BreakerState.OPEN``, the
              breaker's internal state already reflects ``OPEN`` before this
              callback runs.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify subscribers that a downstream call succeeded.

        Guarantees:
            - ``context`` is the exact immutable ``CallContext`` supplied by the
              caller.
            - ``context.caller_state`` is passed through unchanged.
            - ``current_state`` is the breaker's internal state after any success
              mutation, not the context's ``caller_state``.
            - This callback is not emitted for invalid negative-duration input.
            - If the breaker was not already open when success was recorded, its
              failure count has already been reset to zero before this callback
              runs.
            - If the breaker was already open when success was recorded, its
              failure count is not reset.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify subscribers that a breaker transitioned to ``OPEN``.

        Guarantees:
            - ``context`` is the exact immutable ``CallContext`` associated with
              the failure that caused the transition.
            - ``context.caller_state`` is passed through unchanged.
            - The breaker's internal state already reflects ``BreakerState.OPEN``
              before this callback runs.
            - This callback fires at most once per transition from a non-open
              state to ``OPEN``.
            - This callback is not emitted for an already-open breaker.
        """
        ...
```

## 4. `circuit_breaker.py`

```python
"""Failure-threshold circuit breaker that reports through module-level NOTIFIER."""

import warnings

from breaker_state import BreakerState
from breaker_events import CircuitBreakerNotifier
from call_context import CallContext

# The service installs this module-level object before invoking breaker methods.
# It is intentionally not implemented here.
NOTIFIER: CircuitBreakerNotifier


class CircuitBreaker:
    """A small failure-threshold circuit breaker.

    The breaker holds no references to any external system. ``NOTIFIER`` is its
    sole point of contact with subscribers.

    Internal state is updated before notifications so synchronous callbacks may
    observe the post-mutation state, including a reentrant failure seeing an
    already-open breaker and being ignored.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Create a breaker.

        Args:
            name:
                Identifier passed to every ``NOTIFIER`` callback.
            failure_threshold:
                Number of accepted failures that causes a transition to
                ``BreakerState.OPEN``.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED
        self._open_transition: int = 0

    def _warn_invalid_duration(self, context: CallContext) -> bool:
        """Warn and drop a call result with a negative duration.

        Args:
            context:
                Candidate immutable call context.

        Returns:
            ``True`` if the context should be dropped, otherwise ``False``.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CallContext duration_ms="
                f"{context.duration_ms} is negative; "
                f"ignoring call result for breaker {self._name!r}.",
                UserWarning,
                stacklevel=3,
            )
            return True

        return False

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call attempt.

        Invalid negative-duration contexts are dropped with a warning.

        If the breaker is already open, the failure is ignored entirely.

        Otherwise, the failure count is incremented first. If the count reaches
        the configured threshold, the breaker transitions to
        ``BreakerState.OPEN`` before any notification is emitted. The breaker
        then emits ``emit_call_failed`` with the unchanged context, and then,
        if still in the same transition to ``OPEN``, emits
        ``emit_breaker_opened``.

        Args:
            context:
                Immutable description of the failed call attempt.
        """
        if self._warn_invalid_duration(context):
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1

        opening_transition = False
        transition_token = 0

        if self._failure_count >= self._failure_threshold:
            self._open_transition += 1
            transition_token = self._open_transition
            self._state = BreakerState.OPEN
            opening_transition = True

        NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if (
            opening_transition
            and self._state is BreakerState.OPEN
            and self._open_transition == transition_token
        ):
            NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call attempt.

        Invalid negative-duration contexts are dropped with a warning.

        If the breaker is not open, the failure count is reset to zero before
        notification. The breaker state is not otherwise changed.

        If the breaker is already open, the failure count is not reset.

        The unchanged context is passed to ``NOTIFIER.emit_call_succeeded`` along
        with the breaker's current state.

        Args:
            context:
                Immutable description of the successful call attempt.
        """
        if self._warn_invalid_duration(context):
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """Return the breaker to closed state with zero failures.

        No notifier event is emitted.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED
```
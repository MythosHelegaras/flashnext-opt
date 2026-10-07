```python
# breaker_state.py
"""Breaker state values authored by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """
    Breaker state as seen by the caller's policy layer.

    These values are authored outside the breaker's failure path. The breaker
    must pass them through unchanged and must not reinterpret them.
    """

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


BreakerState.CLOSED.__doc__ = """
The caller believes the breaker is closed and calls are expected to be allowed.
"""
BreakerState.OPEN.__doc__ = """
The caller believes the breaker is open and calls are expected to be blocked.
"""
BreakerState.HALF_OPEN.__doc__ = """
The caller believes the breaker is half-open and trial calls are expected.
"""
```

```python
# call_context.py
"""Immutable context describing a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """
    Immutable description of one downstream call attempt.

    `caller_state` is a load-bearing product requirement. It must reach every
    subscriber unchanged; the breaker must not filter, remap, or reinterpret it.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState
```

```python
# breaker_events.py
"""Subscriber contract for circuit breaker events."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """
    Protocol for the module-level `NOTIFIER` object.

    The concrete notifier is supplied by the surrounding system. This module
    intentionally does not implement it. The notifier must preserve each
    `CallContext` unchanged and must not filter, remap, or reinterpret
    `context.caller_state`.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Emit an accepted call failure.

        Guarantees:
        - Called only after the breaker has incremented its failure count.
        - `context` is the original caller-provided context, unchanged.
        - `failure_count` is the post-increment failure count.
        - `threshold` is the breaker's configured failure threshold.
        - Not called for invalid contexts or for failures recorded while the
          breaker is already OPEN.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Emit an accepted call success.

        Guarantees:
        - Called after any failure-count reset has already been applied.
        - `context` is the original caller-provided context, unchanged.
        - `current_state` is the breaker's state after that mutation: CLOSED if
          the success reset the failure count, or OPEN if the breaker was already
          open.
        - Called even when the breaker is OPEN.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """
        Emit a transition to OPEN.

        Guarantees:
        - Called exactly once for each transition from not-open to OPEN.
        - Called only after the breaker's internal state is already OPEN.
        - Never called again while the breaker is already OPEN.
        - `context` is the original caller-provided context, unchanged.
        - For the failure that opens the breaker, this event is emitted after
          the corresponding call_failed notification.
        """
        ...


NOTIFIER: Notifier
```

```python
# circuit_breaker.py
"""Circuit breaker that records call outcomes and emits events via NOTIFIER."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """
    A small reusable circuit breaker.

    The breaker holds no references to any other system. Its sole point of
    contact is the module-level `NOTIFIER` object defined by `breaker_events`.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a closed breaker.

        Args:
            name: Name passed to notifier events.
            failure_threshold: Number of accepted failures that opens the breaker.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record an accepted call failure.

        Invalid contexts with negative `duration_ms` are dropped with a warning.
        Failures recorded while the breaker is already OPEN are ignored entirely.
        Otherwise the failure count is incremented, and if it reaches the
        configured threshold the breaker transitions to OPEN before any
        notification is emitted.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        transitioned_to_open: bool = False
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            transitioned_to_open = True

        breaker_events.NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if transitioned_to_open:
            breaker_events.NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record an accepted call success.

        Invalid contexts with negative `duration_ms` are dropped with a warning.
        Otherwise the breaker emits a success event. If the breaker is not OPEN,
        the failure count is reset to zero before the notification is emitted.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        breaker_events.NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """
        Return the breaker to CLOSED with a zero failure count.

        This method emits nothing.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0
```
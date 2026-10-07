### breaker_state.py
```python
"""Breaker state values authored by the caller's policy layer."""

from enum import Enum


class BreakerState(Enum):
    """The three breaker states used by callers and subscribers.

    These values are authored by the caller's policy layer. The circuit
    breaker's failure path does not decide what ``caller_state`` means; it
    passes the value through unchanged.
    """

    CLOSED = (
        "closed",
        "The breaker is closed; calls are permitted and failures are counted.",
    )
    OPEN = (
        "open",
        "The breaker is open; the caller's policy treats calls as unavailable.",
    )
    HALF_OPEN = (
        "half_open",
        "The breaker is half-open; the caller's policy is probing recovery.",
    )

    def __init__(self, value: str, doc: str) -> None:
        """Initialize a breaker state value and attach its member documentation."""
        self._value_ = value
        self.__doc__ = doc
```

### call_context.py
```python
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
```

### breaker_events.py
```python
"""Subscriber contract for circuit breaker events.

This module defines the callback signatures that a notifier must support. It
does not implement a notifier. Production code is expected to provide a
module-level object named ``NOTIFIER`` that satisfies :class:`Notifier`.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CallFailedCallback(Protocol):
    """Callback signature for :meth:`Notifier.emit_call_failed`."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Called after a failure has been recorded.

        Guarantees:
        - ``context`` is the original :class:`CallContext` supplied to the
          breaker. ``context.caller_state`` is delivered unchanged.
        - ``failure_count`` is the breaker's internal failure count after the
          increment performed by ``record_failure``.
        - ``threshold`` is the configured failure threshold.
        - The callback is not invoked for invalid contexts or for failures
          ignored because the breaker is already open.
        - If the failure caused a transition to OPEN, the breaker state is
          already OPEN before this callback runs.
        """


class CallSucceededCallback(Protocol):
    """Callback signature for :meth:`Notifier.emit_call_succeeded`."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Called after a success has been recorded.

        Guarantees:
        - ``context`` is the original :class:`CallContext` supplied to the
          breaker. ``context.caller_state`` is delivered unchanged.
        - ``current_state`` is the breaker's state after any mutation caused by
          ``record_success``.
        - If the breaker was not open, its failure count has already been reset
          to zero before this callback runs.
        - If the breaker was open, no failure count reset occurs.
        - The callback is not invoked for invalid contexts.
        """


class BreakerOpenedCallback(Protocol):
    """Callback signature for :meth:`Notifier.emit_breaker_opened`."""

    def __call__(self, breaker_name: str, context: CallContext) -> None:
        """Called when a breaker transitions to OPEN.

        Guarantees:
        - The callback fires exactly once per transition to OPEN.
        - It is not invoked for failures recorded while the breaker is already
          open.
        - ``context`` is the original :class:`CallContext` supplied to the
          breaker. ``context.caller_state`` is delivered unchanged.
        - The breaker state is already OPEN before this callback runs.
        - After ``reset()``, a later transition to OPEN may fire this callback
          again.
        """


class Notifier(Protocol):
    """Notifier contract expected by :class:`CircuitBreaker`."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Emit a call failure event. See :class:`CallFailedCallback`."""

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Emit a call success event. See :class:`CallSucceededCallback`."""

    def emit_breaker_opened(self, breaker_name: str, context: CallContext) -> None:
        """Emit a breaker-opened event. See :class:`BreakerOpenedCallback`."""


NOTIFIER: Notifier
```

### circuit_breaker.py
```python
"""Circuit breaker that notifies subscribers through ``NOTIFIER``."""

import warnings

import breaker_events
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """A small circuit breaker that reports events through ``NOTIFIER``.

    The breaker holds no references to any other system. ``NOTIFIER`` is its
    sole point of contact.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize a closed circuit breaker.

        Args:
            name: Name reported to subscribers.
            failure_threshold: Number of recorded failures that opens the
                breaker.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. Failures recorded while the breaker is already OPEN are
        ignored. Otherwise, the internal failure count is incremented first. If
        the count reaches ``failure_threshold``, the breaker state is set to
        OPEN before any notification fires. The method then emits
        ``call_failed`` and, if this call transitioned the breaker to OPEN,
        emits ``breaker_opened`` exactly once.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}. "
                "Failure event dropped.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        transitioned_to_open = False
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            transitioned_to_open = True

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if transitioned_to_open:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. If the breaker is not OPEN, the failure count is reset to zero
        before notification. The method then emits ``call_succeeded`` with the
        breaker's current state after any mutation.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"CallContext.duration_ms must be non-negative; got {context.duration_ms}. "
                "Success event dropped.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier = breaker_events.NOTIFIER
        notifier.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """Return the breaker to CLOSED with a zero failure count.

        This method emits nothing.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0
```
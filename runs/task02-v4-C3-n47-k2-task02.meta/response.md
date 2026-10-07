Below are the four requested files. The service composition root is expected to install a concrete notifier object as `breaker_events.NOTIFIER` before the breaker emits notifications.

### breaker_state.py

```python
"""Breaker state values authored by the caller's policy layer."""

from enum import Enum, auto


class BreakerState(Enum):
    """
    State values supplied by the caller's policy layer.

    These values describe the caller's view of a breaker at the moment a call
    was issued. The circuit breaker's failure path does not decide or
    reinterpret the ``caller_state`` value carried by ``CallContext``.
    """

    CLOSED = auto()
    """The caller's policy layer considers the breaker closed."""

    OPEN = auto()
    """The caller's policy layer considers the breaker open."""

    HALF_OPEN = auto()
    """The caller's policy layer considers the breaker half-open."""


__all__ = ["BreakerState"]
```

### call_context.py

```python
"""Immutable description of a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """
    Immutable context for one downstream call attempt.

    ``caller_state`` is load-bearing: it must reach every subscriber unchanged.
    The circuit breaker must not filter, remap, or reinterpret it.
    """

    duration_ms: int  # How long the call took, in milliseconds.
    endpoint: str | None  # The target endpoint, or ``None`` for anonymous calls.
    caller_state: BreakerState  # The caller's view of breaker state when issued.


__all__ = ["CallContext"]
```

### breaker_events.py

```python
"""Subscriber contract for circuit breaker notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """
    Contract for the module-level ``NOTIFIER`` object.

    The concrete notifier is provided by the service. This module defines only
    the callback signatures and their guarantees; it does not implement the
    notifier.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Emit a failure notification.

        Guarantees:
        - Called exactly once for each accepted failure recorded by a breaker.
        - ``context`` is the original ``CallContext`` supplied to the breaker;
          its ``caller_state`` is unchanged and must not be filtered, remapped,
          or reinterpreted.
        - ``failure_count`` is the breaker's internal failure count after the
          failure has been recorded.
        - ``threshold`` is the breaker's configured failure threshold.
        - If the failure caused a transition to OPEN, the breaker's internal
          state is already OPEN before this callback is invoked.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Emit a success notification.

        Guarantees:
        - Called exactly once for each accepted success recorded by a breaker.
        - ``context`` is the original ``CallContext`` supplied to the breaker;
          its ``caller_state`` is unchanged and must not be filtered, remapped,
          or reinterpreted.
        - ``current_state`` is the breaker's internal state at notification
          time; it is not ``context.caller_state``.
        - If the breaker was not OPEN, the internal failure count has already
          been reset to zero before this callback is invoked.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """
        Emit a transition-to-OPEN notification.

        Guarantees:
        - Called exactly once for each transition into OPEN.
        - Called only when the failure count reaches the configured threshold.
        - Never called again while the breaker is already OPEN.
        - ``context`` is the original ``CallContext`` supplied to the breaker;
          its ``caller_state`` is unchanged and must not be filtered, remapped,
          or reinterpreted.
        - The breaker's internal state is already OPEN before this callback is
          invoked.
        """
        ...


# The concrete notifier is installed by the service as ``NOTIFIER``. This
# module intentionally declares only the contract and does not implement it.
NOTIFIER: Notifier


__all__ = ["Notifier"]
```

### circuit_breaker.py

```python
"""Production circuit breaker that notifies subscribers through NOTIFIER."""

import warnings

import breaker_events
from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext


class CircuitBreaker:
    """
    A small circuit breaker that reports calls through ``NOTIFIER``.

    The breaker holds no references to any other system. ``NOTIFIER`` is its
    sole point of contact. Internal state is mutated before subscriber
    notifications so synchronous callbacks observe the post-mutation state.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a circuit breaker.

        Args:
            name: Name reported to subscribers.
            failure_threshold: Failure count that opens the breaker.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record a failed call.

        Negative ``duration_ms`` values are dropped with a warning. A failure
        on an already-open breaker is ignored. Otherwise the failure count is
        incremented, and if the threshold is reached the internal state is set
        to OPEN before any notification is emitted. When a transition occurs,
        ``call_failed`` is emitted before ``breaker_opened``.
        """
        duration_ms: int = context.duration_ms
        if duration_ms < 0:
            warnings.warn(
                f"Circuit breaker {self._name!r} ignored a failure with negative duration_ms={duration_ms}.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        notifier: Notifier = breaker_events.NOTIFIER

        self._failure_count += 1
        opened: bool = False
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
            opened = True

        # The state is already OPEN before the first notification, so a
        # synchronous callback into record_failure sees the post-mutation guard.
        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record a successful call.

        Negative ``duration_ms`` values are dropped with a warning. If the
        breaker is not OPEN, the failure count is reset to zero before
        ``call_succeeded`` is emitted.
        """
        duration_ms: int = context.duration_ms
        if duration_ms < 0:
            warnings.warn(
                f"Circuit breaker {self._name!r} ignored a success with negative duration_ms={duration_ms}.",
                UserWarning,
                stacklevel=2,
            )
            return

        notifier: Notifier = breaker_events.NOTIFIER

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        # The failure count is already reset before notification.
        notifier.emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """
        Return the breaker to CLOSED with a zero failure count.

        No notifications are emitted.
        """
        self._state = BreakerState.CLOSED
        self._failure_count = 0


__all__ = ["CircuitBreaker"]
```
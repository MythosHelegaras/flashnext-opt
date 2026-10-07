Below are the four requested files.

A small integration note for production use: `circuit_breaker.py` intentionally does **not** create or implement `NOTIFIER`. The application is expected to provide a module-level `circuit_breaker.NOTIFIER` before any breaker records a call, for example:

```python
import circuit_breaker

circuit_breaker.NOTIFIER = some_notifier
```

---

## breaker_state.py

```python
"""
Breaker state enum authored by the caller's policy layer.

This enum is intentionally external to breaker failure logic. It describes the
state the caller believes the breaker is in when a call is issued.
"""

from enum import Enum, auto


class BreakerState(Enum):
    """
    Caller-authored breaker state.

    This value is descriptive only. It must be supplied by the caller's policy
    layer and must never be decided, derived, filtered, remapped, or
    reinterpreted inside the breaker's failure path.
    """

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


BreakerState.CLOSED.__doc__ = """
Caller-side view: the caller believes no breaker restriction is active.
"""

BreakerState.OPEN.__doc__ = """
Caller-side view: the caller believes the breaker is blocking calls.
"""

BreakerState.HALF_OPEN.__doc__ = """
Caller-side view: the caller believes the breaker is allowing a trial call to
test whether recovery is possible.
"""
```

---

## call_context.py

```python
"""
Immutable description of a single downstream call attempt.
"""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """
    Immutable value object describing one downstream call attempt.

    Fields:
        duration_ms:
            Duration of the call in milliseconds.
        endpoint:
            Target endpoint, or `None` for anonymous calls.
        caller_state:
            Caller-authored view of breaker state at the moment the call was
            issued.

    `caller_state` is load-bearing. It must reach every subscriber unchanged.
    The breaker must not filter, remap, or reinterpret it.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState


CallContext.__init__.__doc__ = (
    "Initialize a CallContext with duration_ms, endpoint, and caller_state."
)
```

---

## breaker_events.py

```python
"""
Subscriber contract for circuit breaker notifications.

This module defines the notification protocol only. It does not implement or
define a notifier object.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class BreakerNotifier(Protocol):
    """
    Notification protocol required by `CircuitBreaker`.

    The application is expected to provide a module-level `NOTIFIER` object whose
    structure satisfies this protocol.

    Callbacks are invoked synchronously by the breaker. If a callback raises an
    exception, the breaker does not catch it. Any internal state mutations
    already performed before the first callback remain in effect. Events after
    the exception may not be delivered.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """
        Called once for every accepted failure after the breaker's internal
        failure count has been incremented.

        Guarantees:
            - Fires for every accepted `CircuitBreaker.record_failure()` call.
            - Does not fire for already-open breaker failures.
            - Does not fire for invalid negative-duration contexts.
            - `context` is the exact caller-supplied `CallContext`, unchanged.
            - `failure_count` is the breaker's failure count after incrementing
              for this failure.
            - `threshold` is the breaker's configured failure threshold.
            - When this failure reaches `threshold`, the breaker state has
              already been mutated to `BreakerState.OPEN` before this callback
              begins.
            - In that same outer `record_failure()` call, `emit_breaker_opened`
              follows this callback.
            - Callbacks may reenter the breaker synchronously. The breaker's
              guard state is already post-mutation before this callback starts.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """
        Called once for every accepted success after any corresponding internal
        success processing has already happened.

        Guarantees:
            - Fires for every accepted `CircuitBreaker.record_success()` call.
            - Does not fire for invalid negative-duration contexts.
            - `context` is the exact caller-supplied `CallContext`, unchanged.
            - `current_state` is the breaker's internal state after the success
              was processed.
            - If the breaker was not open, the internal failure count has
              already been reset to zero before this callback begins.
            - If the breaker was open, no state or failure-count mutation was
              performed for success.
            - This event may fire while the breaker is open.
            - Callbacks may reenter the breaker synchronously.
        """
        ...

    def emit_breaker_opened(self, breaker_name: str, context: CallContext) -> None:
        """
        Called once when the breaker transitions into `BreakerState.OPEN`.

        Guarantees:
            - Fires exactly once per transition into OPEN.
            - Never fires again while the breaker is already open.
            - Fires after the breaker state has already been mutated to OPEN.
            - Fires after `emit_call_failed` for the same failure that caused
              the transition.
            - `context` is the exact caller-supplied failure context that caused
              the transition, unchanged.
            - Callbacks may reenter the breaker synchronously, and the breaker's
              open guard is already active before this callback starts.
        """
        ...
```

---

## circuit_breaker.py

```python
"""
Synchronous circuit breaker that communicates exclusively through NOTIFIER.

The breaker holds no references to any other system. The global `NOTIFIER`
object is its sole point of contact.
"""

import warnings

from breaker_state import BreakerState
from call_context import CallContext
from breaker_events import BreakerNotifier

# The application is expected to provide this module-level object before any
# breaker records a call. No notifier is defined or imported here.
NOTIFIER: BreakerNotifier


def _notifier() -> BreakerNotifier:
    """
    Return the application-provided global notifier object.
    """
    return NOTIFIER


class CircuitBreaker:
    """
    A synchronous failure-count circuit breaker.

    The breaker tracks only:
        - its configured failure threshold
        - a non-negative failure count
        - a breaker state

    It notifies subscribers through `NOTIFIER` only.
    """

    __slots__ = (
        "_name",
        "_failure_threshold",
        "_failure_count",
        "_state",
    )

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """
        Create a new breaker.

        Args:
            name:
                Breaker name passed through to every notification.
            failure_threshold:
                Number of accepted failures required before the breaker
                transitions to OPEN.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """
        Record a failed call attempt.

        Behavior:
            - Negative `duration_ms` is dropped with a warning.
            - If the breaker is already OPEN, the call is ignored entirely.
            - Otherwise, the internal failure count is incremented first.
            - If the incremented count reaches the threshold, the state is
              mutated to OPEN before any notification is emitted.
            - `emit_call_failed` is always emitted for accepted failures.
            - If this failure opened the breaker, `emit_breaker_opened` is then
              emitted once.

        The caller-supplied `context.caller_state` is passed through unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CallContext.duration_ms must be non-negative; dropping "
                f"failure event for breaker {self._name!r}.",
                UserWarning,
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        notifier = _notifier()

        self._failure_count += 1

        transition_to_open = self._failure_count >= self._failure_threshold
        if transition_to_open:
            self._state = BreakerState.OPEN

        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if transition_to_open:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """
        Record a successful call attempt.

        Behavior:
            - Negative `duration_ms` is dropped with a warning.
            - If the breaker is not OPEN, the internal failure count is reset
              to zero before notification.
            - If the breaker is OPEN, success does not reset the failure count
              and does not close the breaker.
            - `emit_call_succeeded` is emitted after any corresponding
              internal mutation.
            - The notifier receives the breaker's current state after
              success processing.

        The caller-supplied `context.caller_state` is passed through unchanged.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CallContext.duration_ms must be non-negative; dropping "
                f"success event for breaker {self._name!r}.",
                UserWarning,
                stacklevel=2,
            )
            return

        notifier = _notifier()

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """
        Reset the breaker to CLOSED with a zero failure count.

        This method emits no notifications.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED
```
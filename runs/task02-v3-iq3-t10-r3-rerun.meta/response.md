```python
# breaker_state.py
"""Breaker state enum supplied by caller policy."""

from enum import Enum, auto


class BreakerState(Enum):
    """States authored by the caller policy layer.

    These values are used by the caller to describe its own view of breaker
    state in `CallContext.caller_state`. The breaker does not infer, filter,
    remap, or reinterpret that carried value.
    """

    CLOSED = auto()
    """Caller-policy state indicating normal call eligibility.

    A breaker instance begins in this state and returns to it after
    `reset()`.
    """

    OPEN = auto()
    """Caller-policy state indicating that calls are being treated as open.

    The breaker may enter this state after its own failure threshold is
    reached. While a breaker instance is internally open, further failure
    recording is ignored.
    """

    HALF_OPEN = auto()
    """Caller-policy probing state.

    This member exists for the caller policy layer to describe a trial or
    half-open call. The breaker never selects this state in its failure path.
    """
```

```python
# call_context.py
"""Immutable context for a single downstream call attempt."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable record of one downstream call attempt.

    `CallContext` instances are passed to subscribers unchanged. The breaker
    must not filter, remap, or reinterpret `caller_state`.
    """

    duration_ms: int
    """How long the call took, in milliseconds.

    Negative values are invalid input and are dropped by breaker methods
    with a warning rather than raising an exception.
    """

    endpoint: str | None
    """The target endpoint, or `None` for anonymous calls."""

    caller_state: BreakerState
    """The caller's view of breaker state when the call was issued.

    This is load-bearing product data and must reach every subscriber
    unchanged.
    """
```

```python
# breaker_events.py
"""Subscriber contract for breaker event notifications."""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class BreakerNotifier(Protocol):
    """Protocol required by the production-provided `NOTIFIER` object.

    Production code must bind a module-level object named `NOTIFIER`
    implementing this protocol before breaker methods perform notifications:

        breaker_events.NOTIFIER = MyNotifier()
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Notify that an accepted downstream call failed.

        Guarantees:
          - The breaker has already incremented its internal failure count.
          - If the failure crossed the threshold, the breaker has already
            transitioned to `BreakerState.OPEN` before this notification is
            prepared.
          - `context` is the caller-provided `CallContext`, passed unchanged.
          - `failure_count` is the breaker's count after mutation.
          - `threshold` is the configured failure threshold.
          - This event does not, by itself, indicate whether the breaker is
            now open; the threshold crossing is observable through
            `failure_count` and `threshold`.
        """

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Notify that an accepted downstream call succeeded.

        Guarantees:
          - If the breaker was not open before the success was accepted, its
            failure count has already been reset to zero before this
            notification is prepared.
          - If the breaker was open, its failure count has not been reset.
          - `context` is the caller-provided `CallContext`, passed unchanged.
          - `current_state` is the breaker state after mutation and before
            emission.
        """

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Notify that the breaker transitioned to `OPEN`.

        Guarantees:
          - It is prepared only after a mutation from a non-open state to
            `BreakerState.OPEN`.
          - It fires exactly once for each such transition.
          - It is never prepared for a failure while the breaker was already
            open.
          - It is not emitted by `reset()`.
          - `context` is the failure context that caused the transition,
            passed unchanged.
        """


NOTIFIER: BreakerNotifier
```

```python
# circuit_breaker.py
"""Named circuit breaker recorder and notifier adapter."""

import warnings

import breaker_events
from breaker_events import BreakerNotifier
from call_context import CallContext
from breaker_state import BreakerState


class CircuitBreaker:
    """Failure recorder for one named circuit breaker.

    State mutations complete before notifications are prepared and emitted.
    The production-provided `NOTIFIER` object is the breaker's sole external
    point of contact.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize a breaker in `CLOSED` state with zero recorded failures.

        Args:
            name: Logical name used in notifications.
            failure_threshold: Number of accepted failures that causes an
                internal transition to `OPEN`.
        """
        self._name: str = name
        self._failure_threshold: int = failure_threshold
        self._failure_count: int = 0
        self._state: BreakerState = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call.

        Guarantees:
          - A negative `context.duration_ms` is dropped with a warning and
            causes no state mutation or notification.
          - If the breaker is already internally `OPEN`, the call is ignored
            entirely.
          - Otherwise, the internal failure count is incremented first.
          - If that increment reaches the threshold, the breaker state is set
            to `OPEN` before any notification fires, so synchronous reentrancy
            sees the open guard already in its post-mutation state.
          - The full immutable context is passed unchanged to
            `NOTIFIER.emit_call_failed`.
          - If this failure is the one that opened the breaker,
            `NOTIFIER.emit_breaker_opened` is emitted exactly once for this
            transition.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CircuitBreaker.record_failure dropped invalid context: "
                f"breaker={self._name!r}, duration_ms={context.duration_ms!r}",
                stacklevel=2,
            )
            return

        if self._state is BreakerState.OPEN:
            return

        notifier: BreakerNotifier = breaker_events.NOTIFIER

        self._failure_count += 1

        opened_now = False
        if self._failure_count >= self._failure_threshold:
            if self._state is not BreakerState.OPEN:
                self._state = BreakerState.OPEN
                opened_now = True

        notifier.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened_now:
            notifier.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call.

        Guarantees:
          - A negative `context.duration_ms` is dropped with a warning and
            causes no state mutation or notification.
          - If the breaker is not internally `OPEN`, its failure count is
            reset to zero before notification.
          - If the breaker is internally `OPEN`, the failure count is not
            reset.
          - The full immutable context is passed unchanged to
            `NOTIFIER.emit_call_succeeded`.
          - `NOTIFIER.emit_call_succeeded` receives the breaker state after
            mutation and before emission.
        """
        if context.duration_ms < 0:
            warnings.warn(
                "CircuitBreaker.record_success dropped invalid context: "
                f"breaker={self._name!r}, duration_ms={context.duration_ms!r}",
                stacklevel=2,
            )
            return

        notifier: BreakerNotifier = breaker_events.NOTIFIER

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        notifier.emit_call_succeeded(
            self._name,
            context,
            self._state,
        )

    def reset(self) -> None:
        """Return the breaker to `CLOSED` with a zero failure count.

        Guarantees:
          - Internal state becomes `BreakerState.CLOSED`.
          - The internal failure count becomes zero.
          - No notification is emitted.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED
```
### `breaker_state.py`

```python
"""Breaker state values authored by the caller's policy layer."""

from enum import Enum


class BreakerState(Enum):
    """States of a circuit breaker as understood by the caller's policy layer.

    These values are authored externally. The breaker failure path never
    decides, filters, remaps, or reinterprets them.
    """

    CLOSED = "closed"
    """Caller-authored state indicating that calls are allowed."""

    OPEN = "open"
    """Caller-authored state indicating that calls are blocked."""

    HALF_OPEN = "half_open"
    """Caller-authored state indicating a trial or probing window."""
```


### `call_context.py`

```python
"""Immutable per-call context used by circuit breaker subscribers."""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class CallContext:
    """Immutable description of a single downstream call attempt.

    Attributes:
        duration_ms: How long the call took, in milliseconds.
        endpoint: Target of the call, or `None` for anonymous calls.
        caller_state: The caller's view of breaker state when the call was
            issued. This value is load-bearing and must reach every subscriber
            unchanged.
    """

    duration_ms: int
    endpoint: str | None
    caller_state: BreakerState
```


### `breaker_events.py`

```python
"""Subscriber contracts for circuit breaker notifications.

The production environment supplies a module-level `NOTIFIER` object. This
module defines the required method signatures and the guarantees attached to
them. The notifier itself is not implemented here.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class Notifier(Protocol):
    """Notifier contract required by `CircuitBreaker`.

    A `NOTIFIER` is the sole point of contact between the breaker and
    subscribers. It must expose the methods below.

    Callbacks receive `context` exactly as it was supplied to the breaker.
    The breaker does not filter, remap, or reinterpret `context.caller_state`.
    """

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Report one valid failure to subscribers.

        Guarantees:
            - `context` is unchanged.
            - `failure_count` is the post-mutation failure count.
            - `threshold` is the configured failure threshold.
            - If the failure reaches the threshold, the breaker's internal
              state has already transitioned to `OPEN` before this callback is
              invoked.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Report one valid success to subscribers.

        Guarantees:
            - `context` is unchanged.
            - `current_state` is the breaker's internal state after any
              non-open success mutation. It is `CLOSED` for a closed breaker
              and `OPEN` for an open breaker; it is not copied from
              `context.caller_state`.
            - If the breaker was not open, its failure count has already been
              reset to zero before this callback is invoked.
            - If the breaker was open, its failure count is not reset.
        """
        ...

    def emit_breaker_opened(
        self, breaker_name: str, context: CallContext
    ) -> None:
        """Report a transition to `OPEN`.

        Guarantees:
            - `context` is the call context whose failure caused the
              transition.
            - The callback fires exactly once per closed-to-open transition.
            - It does not fire again while the breaker is already open.
        """
        ...
```


### `circuit_breaker.py`

```python
"""Failure-count circuit breaker for production use."""

import warnings

from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext

NOTIFIER: Notifier


class CircuitBreaker:
    """Tracks downstream-call failures and notifies `NOTIFIER`.

    The breaker holds no references to other systems. `NOTIFIER` is its only
    point of contact.

    Mutations are completed before notifications so that reentrant callbacks
    observe the post-mutation state.
    """

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Initialize an instance.

        Args:
            name: Breaker name used in every notification.
            failure_threshold: Number of failures required to open the breaker.
                Defaults to 5.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._is_open = False

    def record_failure(self, context: CallContext) -> None:
        """Record a failure.

        If `context.duration_ms` is negative, the call is dropped with a
        warning and no state mutation or notification occurs.

        Otherwise, if the breaker is already open, the call is ignored entirely.

        For a valid failure on a non-open breaker, state is mutated before any
        notification:

        - The failure count is incremented.
        - If the failure count reaches `failure_threshold`, the breaker is
          transitioned to `OPEN` before the first notification.
        - `NOTIFIER.emit_call_failed` is emitted.
        - If this failure caused the transition, `NOTIFIER.emit_breaker_opened`
          is emitted exactly once for that transition.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"invalid CallContext for breaker {self._name!r}: "
                f"duration_ms={context.duration_ms} is negative",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if self._is_open:
            return

        self._failure_count += 1
        opened_now = self._failure_count >= self._failure_threshold
        if opened_now:
            self._is_open = True

        NOTIFIER.emit_call_failed(
            self._name,
            context,
            self._failure_count,
            self._failure_threshold,
        )

        if opened_now:
            NOTIFIER.emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a success.

        If `context.duration_ms` is negative, the call is dropped with a
        warning and no state mutation or notification occurs.

        Otherwise, state mutation happens before notification:

        - If the breaker is not open, its failure count is reset to zero.
        - If the breaker is open, its failure count is not reset.
        - `NOTIFIER.emit_call_succeeded` is emitted with the current internal
          breaker state.
        """
        if context.duration_ms < 0:
            warnings.warn(
                f"invalid CallContext for breaker {self._name!r}: "
                f"duration_ms={context.duration_ms} is negative",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if not self._is_open:
            self._failure_count = 0

        current_state: BreakerState = (
            BreakerState.OPEN if self._is_open else BreakerState.CLOSED
        )
        NOTIFIER.emit_call_succeeded(
            self._name,
            context,
            current_state,
        )

    def reset(self) -> None:
        """Return the breaker to `CLOSED` with a zero failure count.

        This emits no notifications.
        """
        self._is_open = False
        self._failure_count = 0
```
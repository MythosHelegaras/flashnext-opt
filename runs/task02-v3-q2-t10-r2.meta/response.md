### breaker_state.py

```python
"""Authoritative enumeration of breaker states authored by caller policy.

The members describe how the caller's policy layer views a breaker when
issuing a downstream call. They are data values supplied by the caller; the
breaker itself does not choose them from its failure/success path except to
model its own OPEN/CLOSED transitions.
"""

from enum import Enum, auto


class BreakerState(Enum):
    """Caller-authored view of a circuit breaker."""

    CLOSED = auto()
    """The caller sees the breaker as admitting calls and tracking failures."""

    OPEN = auto()
    """The caller sees the breaker as rejecting calls or treating them as failed."""

    HALF_OPEN = auto()
    """The caller sees the breaker as allowing probe calls to assess recovery."""


BreakerState.CLOSED.__doc__ = (
    "The caller sees the breaker as admitting calls and tracking failures."
)
BreakerState.OPEN.__doc__ = (
    "The caller sees the breaker as rejecting calls or treating them as failed."
)
BreakerState.HALF_OPEN.__doc__ = (
    "The caller sees the breaker as allowing probe calls to assess recovery."
)
```

### call_context.py

```python
"""Immutable description of a single downstream call attempt.

This type is intentionally small. It is passed by reference to subscribers and
must not be altered by the breaker.
"""

from dataclasses import dataclass

from breaker_state import BreakerState


@dataclass(frozen=True, slots=True, init=False)
class CallContext:
    """Immutable record for a single downstream call attempt.

    Fields
    -----
    duration_ms: int
        How long the call took, in milliseconds.

    endpoint: str | None
        The endpoint being called, or ``None`` for anonymous calls.

    caller_state: BreakerState
        The caller's view of breaker state when the call was issued.
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
        """Create a CallContext.

        Args:
            duration_ms: Duration of the call in milliseconds.
            endpoint: Target endpoint, or ``None`` for anonymous calls.
            caller_state: Caller's breaker state view at call issue time.
        """
        object.__setattr__(self, "duration_ms", duration_ms)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "caller_state", caller_state)
```

### breaker_events.py

```python
"""Subscriber contract for circuit-breaker notifications.

The notifier itself is intentionally not implemented here. A deployment must
bind a module-level object named ``NOTIFIER`` that exposes the methods below.
This module declares the callback signatures and documents the exact guarantees
carried by those notifications.
"""

from typing import Protocol

from breaker_state import BreakerState
from call_context import CallContext


class CallFailedSubscriber(Protocol):
    """Callback contract for an accepted failed downstream call."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Receive the failed-call event.

        Guarantees:
            - This callback is called exactly once for a failure event that the
              breaker accepts.
            - ``context`` is the original :class:`CallContext` instance supplied
              to :meth:`CircuitBreaker.record_failure`; the breaker passes it
              unchanged and does not inspect or rewrite ``caller_state``.
            - ``failure_count`` is the breaker's internal failure count after
              accepting this failure. If this failure reaches ``threshold``,
              ``failure_count`` equals ``threshold``.
            - ``threshold`` is the breaker's configured failure threshold.
            - This callback is not invoked when the breaker was already OPEN on
              entry, nor when invalid input such as a negative
              ``duration_ms`` is dropped.
        """
        ...


class CallSucceededSubscriber(Protocol):
    """Callback contract for an accepted successful downstream call."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Receive the successful-call event.

        Guarantees:
            - This callback is called exactly once for a success event that the
              breaker accepts.
            - ``context`` is the original :class:`CallContext` instance supplied
              to :meth:`CircuitBreaker.record_success`; the breaker passes it
              unchanged and does not inspect or rewrite ``caller_state``.
            - ``current_state`` is the breaker's state after the success has
              been accepted and any count mutation has already happened. If the
              breaker was not OPEN, its failure count has been reset to zero
              before this callback is invoked.
            - This callback is not invoked when invalid input such as a negative
              ``duration_ms`` is dropped.
        """
        ...


class BreakerOpenedSubscriber(Protocol):
    """Callback contract for the breaker transitioning into OPEN."""

    def __call__(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Receive the breaker-opened event.

        Guarantees:
            - This callback is called exactly once for a transition into OPEN.
            - ``context`` is the original :class:`CallContext` instance supplied
              to :meth:`CircuitBreaker.record_failure` for the failure that
              reached ``failure_threshold``; the breaker passes it unchanged.
            - This callback is not invoked for failures ignored because the
              breaker was already OPEN, for successes, or for
              :meth:`CircuitBreaker.reset`.
        """
        ...


class Notifier(Protocol):
    """Protocol for the assumed module-level ``NOTIFIER`` object."""

    def emit_call_failed(
        self,
        breaker_name: str,
        context: CallContext,
        failure_count: int,
        threshold: int,
    ) -> None:
        """Emit a failed-call event.

        The implementation must invoke the configured call-failed subscriber
        contract with the supplied arguments. It must preserve the full
        :class:`CallContext`, including ``caller_state``, unchanged.
        """
        ...

    def emit_call_succeeded(
        self,
        breaker_name: str,
        context: CallContext,
        current_state: BreakerState,
    ) -> None:
        """Emit a successful-call event.

        The implementation must invoke the configured call-succeeded subscriber
        contract with the supplied arguments. It must preserve the full
        :class:`CallContext`, including ``caller_state``, unchanged.
        """
        ...

    def emit_breaker_opened(
        self,
        breaker_name: str,
        context: CallContext,
    ) -> None:
        """Emit a breaker-opened event.

        The implementation must invoke the configured breaker-opened subscriber
        contract with the supplied arguments. It must preserve the full
        :class:`CallContext`, including ``caller_state``, unchanged.
        """
        ...


# Deployment supplies this object. This module declares the contract only; it
# does not implement NOTIFIER.
NOTIFIER: Notifier
```

### circuit_breaker.py

```python
"""A small reusable circuit breaker.

The breaker communicates only through the module-level ``NOTIFIER`` contract
declared in ``breaker_events``. It keeps no references to subscribers or other
systems.
"""

import warnings

import breaker_events as _breaker_events
from breaker_events import Notifier
from breaker_state import BreakerState
from call_context import CallContext

# The assumed notifier may be supplied on this module or on breaker_events.
# This declaration does not implement NOTIFIER.
NOTIFIER: Notifier | None


def _get_notifier() -> Notifier | None:
    """Return the assumed module-level NOTIFIER object, if any is bound."""
    notifier: Notifier | None = getattr(_breaker_events, "NOTIFIER", None)
    if notifier is None:
        notifier = globals().get("NOTIFIER", None)
    return notifier


def _emit_call_failed(
    breaker_name: str,
    context: CallContext,
    failure_count: int,
    threshold: int,
) -> None:
    """Forward a failed-call event to NOTIFIER when available."""
    notifier = _get_notifier()
    if notifier is None:
        return
    notifier.emit_call_failed(breaker_name, context, failure_count, threshold)


def _emit_call_succeeded(
    breaker_name: str,
    context: CallContext,
    current_state: BreakerState,
) -> None:
    """Forward a succeeded-call event to NOTIFIER when available."""
    notifier = _get_notifier()
    if notifier is None:
        return
    notifier.emit_call_succeeded(breaker_name, context, current_state)


def _emit_breaker_opened(breaker_name: str, context: CallContext) -> None:
    """Forward a breaker-opened event to NOTIFIER when available."""
    notifier = _get_notifier()
    if notifier is None:
        return
    notifier.emit_breaker_opened(breaker_name, context)


def _warn_negative_duration(context: CallContext) -> None:
    """Drop a negative-duration call context with a warning."""
    try:
        warnings.warn(
            (
                f"CallContext has negative duration_ms={context.duration_ms}; "
                "call event dropped."
            ),
            UserWarning,
            stacklevel=3,
        )
    except Warning:
        pass


class CircuitBreaker:
    """A threshold-based circuit breaker with no outbound dependencies."""

    __slots__ = ("_name", "_failure_threshold", "_failure_count", "_state")

    def __init__(self, name: str, failure_threshold: int = 5) -> None:
        """Create a CLOSED breaker with a zero failure count.

        Args:
            name: Identifier for this breaker passed to notifier events.
            failure_threshold: Failure count at which CLOSED becomes OPEN.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self, context: CallContext) -> None:
        """Record a failed downstream call and notify accepted failures.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. When the breaker is already OPEN, a failure is ignored
        entirely. When the failure count reaches ``failure_threshold``, the
        internal state is changed to OPEN before notifications are emitted.

        Args:
            context: The immutable call context to pass unchanged to subscribers.
        """
        if context.duration_ms < 0:
            _warn_negative_duration(context)
            return

        if self._state is BreakerState.OPEN:
            return

        self._failure_count += 1
        failure_count = self._failure_count
        tripped = failure_count >= self._failure_threshold
        if tripped:
            self._state = BreakerState.OPEN

        _emit_call_failed(self._name, context, failure_count, self._failure_threshold)
        if tripped:
            _emit_breaker_opened(self._name, context)

    def record_success(self, context: CallContext) -> None:
        """Record a successful downstream call and emit success.

        Invalid contexts with negative ``duration_ms`` are dropped with a
        warning. When the breaker is not OPEN, the failure count is reset to
        zero before the success notification.

        Args:
            context: The immutable call context to pass unchanged to subscribers.
        """
        if context.duration_ms < 0:
            _warn_negative_duration(context)
            return

        if self._state is not BreakerState.OPEN:
            self._failure_count = 0

        _emit_call_succeeded(self._name, context, self._state)

    def reset(self) -> None:
        """Reset the breaker to CLOSED with a zero failure count.

        This method emits no events.
        """
        self._failure_count = 0
        self._state = BreakerState.CLOSED
```
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator


_ACTIVE_REQUEST_CONTEXT: ContextVar[object | None] = ContextVar(
    "active_request_context",
    default=None,
)


class RequestLifecycleContext:
    """Own request-local lifecycle state without owning metrics."""

    def __init__(self, value: object) -> None:
        self.value = value
        self._token: Token[object | None] | None = None

    def begin(self) -> Token[object | None]:
        self._token = _ACTIVE_REQUEST_CONTEXT.set(self.value)
        return self._token

    def reset(self) -> None:
        if self._token is not None:
            _ACTIVE_REQUEST_CONTEXT.reset(self._token)
            self._token = None


@contextmanager
def request_lifecycle(value: object) -> Iterator[object]:
    """Temporarily bind request state and always restore previous state."""

    token = _ACTIVE_REQUEST_CONTEXT.set(value)
    try:
        yield value
    finally:
        _ACTIVE_REQUEST_CONTEXT.reset(token)


def active_request_context() -> object | None:
    return _ACTIVE_REQUEST_CONTEXT.get()


__all__ = [
    "RequestLifecycleContext",
    "active_request_context",
    "request_lifecycle",
]

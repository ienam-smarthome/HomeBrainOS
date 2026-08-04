from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass(slots=True)
class RequestContext:
    """Request-scoped cancellation state shared by transport layers."""

    trace_id: str
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self) -> None:
        self.cancelled.set()

    def is_cancelled(self) -> bool:
        return self.cancelled.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise asyncio.CancelledError

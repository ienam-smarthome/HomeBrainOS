from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp_state_broker import MCPStateBroker


InvalidationCallback = Callable[[str], Awaitable[None] | None]


class IndexedMCPStateBroker(MCPStateBroker):
    """MCP state broker that notifies dependent indexes after invalidation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._invalidation_callbacks: list[InvalidationCallback] = []

    def register_invalidator(self, callback: InvalidationCallback) -> None:
        if callback not in self._invalidation_callbacks:
            self._invalidation_callbacks.append(callback)

    async def invalidate(self, category: str = "all") -> int:
        count = await super().invalidate(category)
        for callback in tuple(self._invalidation_callbacks):
            try:
                result = callback(category)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                # Cache invalidation must never make a successful Hubitat command fail.
                continue
        return count


__all__ = ["IndexedMCPStateBroker"]

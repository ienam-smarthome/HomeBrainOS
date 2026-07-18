from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp_state_broker import MCPStateBroker


InvalidationCallback = Callable[[str], Awaitable[None] | None]


class IndexedMCPStateBroker(MCPStateBroker):
    """MCP state broker that notifies dependent indexes after invalidation."""

    _RULE_WRITE_ACTION_PREFIXES = (
        "create_",
        "update_",
        "delete_",
        "pause_",
        "resume_",
        "enable_",
        "disable_",
        "run_",
        "test_",
        "call_",
        "set_",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._invalidation_callbacks: list[InvalidationCallback] = []

    def register_invalidator(self, callback: InvalidationCallback) -> None:
        if callback not in self._invalidation_callbacks:
            self._invalidation_callbacks.append(callback)

    async def _invalidate_for_write(self, name: str) -> None:
        # Current MCP releases use create_rule/update_rule/test_rule, while older
        # releases use hub_create_visual_rule and other hub_* names. Strip the
        # optional namespace before classifying the write so both refresh the rule
        # catalogue immediately after a successful operation.
        lowered = str(name or "").lower()
        unprefixed = lowered[4:] if lowered.startswith("hub_") else lowered
        if "rule" in unprefixed and unprefixed.startswith(self._RULE_WRITE_ACTION_PREFIXES):
            await self.invalidate("catalog")
            return
        await super()._invalidate_for_write(name)

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

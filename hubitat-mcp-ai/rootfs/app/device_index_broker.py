from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp_state_broker import MCPStateBroker


InvalidationCallback = Callable[[str], Awaitable[None] | None]


class IndexedMCPStateBroker(MCPStateBroker):
    """MCP state broker that notifies dependent indexes after invalidation."""

    _RULE_WRITE_ACTION_PREFIXES = (
        "hub_create_",
        "hub_update_",
        "hub_delete_",
        "hub_pause_",
        "hub_resume_",
        "hub_enable_",
        "hub_disable_",
        "hub_run_",
        "hub_call_",
        "hub_set_",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._invalidation_callbacks: list[InvalidationCallback] = []

    def register_invalidator(self, callback: InvalidationCallback) -> None:
        if callback not in self._invalidation_callbacks:
            self._invalidation_callbacks.append(callback)

    async def _invalidate_for_write(self, name: str) -> None:
        # Gateway-hidden tools may be called hub_create_visual_rule,
        # hub_run_visual_rule, etc. The base broker's legacy rule prefixes only
        # cover hub_create_rule*. Treat any write-shaped Hubitat tool containing
        # "rule" as a catalogue write so list/duplicate checks refresh immediately.
        lowered = str(name or "").lower()
        if "rule" in lowered and lowered.startswith(self._RULE_WRITE_ACTION_PREFIXES):
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

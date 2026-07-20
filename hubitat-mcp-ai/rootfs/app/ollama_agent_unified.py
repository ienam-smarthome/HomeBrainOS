from __future__ import annotations

import time
from typing import Any

from mcp_client import MCPTool
from ollama_agent_adaptive import AdaptiveFinalAnswerAgent
from ollama_agent_claude import ClaudeStyleOllamaAgent
from ollama_agent_fast import OllamaUnavailable


_TARGETED_DEVICE_SEARCH = "homebrain_search_devices"
_DISCOVERY_TOOLS = {
    _TARGETED_DEVICE_SEARCH,
    "hub_search_tools",
    "hub_get_tool_guide",
    "hub_list_devices",
    "hub_read_devices",
}


class UnifiedAdaptiveMCPAgent(AdaptiveFinalAnswerAgent):
    """AI-first Hubitat agent with targeted structured device resolution."""

    def __init__(self, *args: Any, unified_tool_limit: int = 48, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.unified_tool_limit = max(16, min(96, int(unified_tool_limit)))

    def _select_compact_tools(self, query: str, tools: list[MCPTool]) -> list[MCPTool]:
        unique: dict[str, MCPTool] = {}
        for tool in tools:
            name = str(getattr(tool, "name", "") or "").strip()
            if name:
                unique.setdefault(name, tool)

        def priority(tool: MCPTool) -> tuple[int, str]:
            name = str(tool.name)
            if name == _TARGETED_DEVICE_SEARCH:
                return -1, name
            if name in _DISCOVERY_TOOLS:
                return 0, name
            if name.startswith("hub_read_"):
                return 1, name
            if name.startswith("hub_manage_"):
                return 2, name
            if name.startswith("hub_"):
                return 3, name
            return 4, name

        ordered = sorted(unique.values(), key=priority)
        return ordered[: self.unified_tool_limit]

    def _planner_prompt(self) -> str:
        return (
            super()._planner_prompt()
            + "\n\nUnified-agent rules: for any request that names, describes, locates "
            "or asks about a device, call homebrain_search_devices first with the user's "
            "natural description. It searches the complete structured Hubitat MCP device "
            "inventory without character truncation and returns exact IDs, labels, rooms, "
            "capabilities and current states. Use hub_read_devices after that when additional "
            "live detail is required. Do not use hub_search_tools to search for a physical "
            "device, and do not ask the response model to search a truncated whole-home list. "
            "Tool-catalogue discovery is never authoritative home data."
        )

    @staticmethod
    def _should_recover_with_inventory(error: Exception | str) -> bool:
        text = str(error or "").lower()
        return any(
            marker in text
            for marker in (
                "without authoritative home data",
                "did not execute an mcp tool for a live-home question",
                "tool request that could not be parsed",
            )
        )

    async def answer_with_planner(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        try:
            return await ClaudeStyleOllamaAgent.answer(self, query, history or [])
        except OllamaUnavailable as exc:
            if not self._should_recover_with_inventory(exc):
                raise
            return await self._answer_from_targeted_device_search(query, history or [], exc)

    async def _answer_from_targeted_device_search(
        self,
        query: str,
        history: list[dict[str, str]],
        planner_error: Exception,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = await self.client.call_tool(
            _TARGETED_DEVICE_SEARCH,
            {"query": query, "limit": 8},
        )
        if result.is_error:
            raise OllamaUnavailable(
                f"Planner ended without data and targeted device search failed: {result.text}"
            ) from planner_error

        tool_text = self._compact_tool_result(result)
        planner_messages: list[dict[str, Any]] = [
            {
                "role": "tool",
                "tool_name": _TARGETED_DEVICE_SEARCH,
                "content": tool_text,
            }
        ]
        body = await self._chat(
            model=self.model,
            messages=self._synthesis_messages(
                query=query,
                history=history,
                planner_messages=planner_messages,
            ),
            tools=None,
            timeout_seconds=self.response_timeout_seconds,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise OllamaUnavailable("Targeted device recovery returned no user-facing answer")

        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "unified-targeted-device-recovery",
            "message": content,
            "model": self.model,
            "planner_model": self._last_agent_status.get("planner_model"),
            "tools_used": [
                {
                    "name": _TARGETED_DEVICE_SEARCH,
                    "arguments": {"query": query, "limit": 8},
                    "success": True,
                    "preview": tool_text[:700],
                }
            ],
            "selected_tools": [_TARGETED_DEVICE_SEARCH],
            "planner_error": str(planner_error),
            "authoritative_recovery": True,
            "targeted_device_search": True,
            "elapsed_ms": elapsed,
        }


__all__ = ["UnifiedAdaptiveMCPAgent"]

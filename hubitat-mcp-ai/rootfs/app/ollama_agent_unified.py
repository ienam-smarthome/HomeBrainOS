from __future__ import annotations

import time
from typing import Any

from mcp_client import MCPTool
from ollama_agent_adaptive import AdaptiveFinalAnswerAgent
from ollama_agent_claude import ClaudeStyleOllamaAgent
from ollama_agent_fast import OllamaUnavailable


_DISCOVERY_TOOLS = {
    "hub_search_tools",
    "hub_get_tool_guide",
    "hub_list_devices",
    "hub_read_devices",
}


class UnifiedAdaptiveMCPAgent(AdaptiveFinalAnswerAgent):
    """AI-first Hubitat agent with the full visible MCP surface.

    The model sees the complete visible MCP catalogue and can discover hidden tools
    through category gateways. Tool execution still passes through the existing
    confirmation, capability and MCP safety checks.
    """

    def __init__(self, *args: Any, unified_tool_limit: int = 48, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.unified_tool_limit = max(16, min(96, int(unified_tool_limit)))

    def _select_compact_tools(self, query: str, tools: list[MCPTool]) -> list[MCPTool]:
        """Return a stable catalogue instead of selecting tools from query words."""

        unique: dict[str, MCPTool] = {}
        for tool in tools:
            name = str(getattr(tool, "name", "") or "").strip()
            if name:
                unique.setdefault(name, tool)

        def priority(tool: MCPTool) -> tuple[int, str]:
            name = str(tool.name)
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
            + "\n\nUnified-agent rules: discovery is never the final step. After "
            "hub_search_tools or hub_get_tool_guide, immediately call a non-discovery "
            "tool that returns live Hubitat data. For device identity, matching, state "
            "or capability questions, call hub_list_devices or hub_read_devices directly; "
            "do not repeatedly search the tool catalogue. A successful discovery result "
            "describes how to obtain evidence but is not itself authoritative home data."
        )

    @staticmethod
    def _should_recover_with_inventory(error: Exception | str) -> bool:
        """Recognise planner-control failures that still permit a direct live read.

        These failures mean the model did not advance from planning/discovery to a
        data-bearing call. They are not transport, authentication or MCP execution
        failures, so an authoritative inventory read remains safe and useful.
        """

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
        """Run the multi-round MCP loop and recover from planner-control exits.

        The recovery is generic rather than phrase based: when a planner discovers
        tools but does not advance to authoritative data—or emits no usable tool call—
        HomeBrain performs a live device inventory read and synthesises from it.
        """

        try:
            return await ClaudeStyleOllamaAgent.answer(self, query, history or [])
        except OllamaUnavailable as exc:
            if not self._should_recover_with_inventory(exc):
                raise
            return await self._answer_from_authoritative_inventory(query, history or [], exc)

    async def _answer_from_authoritative_inventory(
        self,
        query: str,
        history: list[dict[str, str]],
        planner_error: Exception,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = await self.client.call_tool("hub_list_devices", {})
        if result.is_error:
            raise OllamaUnavailable(
                f"Planner ended without data and hub_list_devices failed: {result.text}"
            ) from planner_error

        tool_text = self._compact_tool_result(result)
        planner_messages: list[dict[str, Any]] = [
            {
                "role": "tool",
                "tool_name": "hub_list_devices",
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
            raise OllamaUnavailable("Inventory recovery returned no user-facing answer")

        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "unified-authoritative-inventory-recovery",
            "message": content,
            "model": self.model,
            "planner_model": self._last_agent_status.get("planner_model"),
            "tools_used": [
                {
                    "name": "hub_list_devices",
                    "arguments": {},
                    "success": True,
                    "preview": tool_text[:700],
                }
            ],
            "selected_tools": ["hub_list_devices"],
            "planner_error": str(planner_error),
            "authoritative_recovery": True,
            "elapsed_ms": elapsed,
        }


__all__ = ["UnifiedAdaptiveMCPAgent"]

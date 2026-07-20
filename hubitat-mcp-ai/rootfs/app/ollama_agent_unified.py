from __future__ import annotations

from typing import Any

from mcp_client import MCPTool
from ollama_agent_adaptive import AdaptiveFinalAnswerAgent
from ollama_agent_claude import ClaudeStyleOllamaAgent


_DISCOVERY_TOOLS = {
    "hub_search_tools",
    "hub_get_tool_guide",
    "hub_list_devices",
    "hub_read_devices",
}


class UnifiedAdaptiveMCPAgent(AdaptiveFinalAnswerAgent):
    """AI-first Hubitat agent with the full visible MCP surface.

    The previous agent reduced the live MCP catalogue to a tiny keyword-selected
    subset before the model saw the request. That made natural language depend on
    HomeBrain's parser vocabulary. This agent exposes the complete visible MCP
    catalogue (core tools plus category gateways), lets the model discover hidden
    tools through the server, and uses the existing multi-round Claude-style loop.

    Tool execution still passes through the existing confirmation, capability and
    MCP safety checks. This class changes planning authority, not safety authority.
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

    async def answer_with_planner(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Run the genuine multi-round MCP loop for every orchestrated request."""

        return await ClaudeStyleOllamaAgent.answer(self, query, history or [])


__all__ = ["UnifiedAdaptiveMCPAgent"]

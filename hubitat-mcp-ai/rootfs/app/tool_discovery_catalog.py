"""Bounded structured tool discovery for the Hubitat MCP agent.

The catalog owns available/declared registry state and schema expansion from
successful ``hub_search_tools`` results. It never inspects user prompt text and
does not decide when discovery, confirmation, or execution should occur.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from mcp_client import MCPTool, MCPToolResult
from tool_registry import (
    LOCAL_ACTIVE_LIGHTS_TOOL,
    LOCAL_ACTIVE_ROOMS_TOOL,
    LOCAL_ACTIVE_SWITCHES_TOOL,
    LOCAL_CONTROL_TOOL,
    LOCAL_FILTER_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL,
    LOCAL_HUB_INFO_TOOL,
    LOCAL_QUERY_TOOL,
    LOCAL_WEATHER_TOOL,
)


SEARCH_TOOL = "hub_search_tools"

INITIAL_TOOL_ORDER = (
    SEARCH_TOOL,
    "hub_read_diagnostics",
    LOCAL_FILTER_TOOL,
    LOCAL_QUERY_TOOL,
    LOCAL_ACTIVE_LIGHTS_TOOL,
    LOCAL_ACTIVE_ROOMS_TOOL,
    LOCAL_ACTIVE_SWITCHES_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL,
    LOCAL_HUB_INFO_TOOL,
    LOCAL_WEATHER_TOOL,
    LOCAL_CONTROL_TOOL,
)


class ToolDiscoveryCatalog:
    """Track the bounded tool registry visible to one agent request."""

    def __init__(
        self,
        available_tools: Iterable[MCPTool],
        *,
        initial_order: Iterable[str] = INITIAL_TOOL_ORDER,
    ) -> None:
        self._available: dict[str, MCPTool] = {}
        for tool in available_tools:
            if tool.name:
                self._available[tool.name] = tool
        self._declared: dict[str, MCPTool] = {}
        self.replace_declared(initial_order)

    @staticmethod
    def tool_schema(tool: MCPTool) -> dict[str, Any]:
        """Render one MCP declaration in native function-calling format."""

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": tool.input_schema
                or {"type": "object", "properties": {}},
            },
        }

    @classmethod
    def initial_tools(cls, tools: Iterable[MCPTool]) -> list[MCPTool]:
        """Compatibility helper returning the fixed prompt-independent set."""

        return cls(tools).declared_tools

    @staticmethod
    def _match_items(data: Any) -> list[dict[str, Any]]:
        """Read only recognised structured search-result envelopes."""

        if not isinstance(data, dict):
            return []
        containers = [data]
        containers.extend(
            nested
            for envelope in ("result", "data", "output")
            if isinstance((nested := data.get(envelope)), dict)
        )
        for container in containers:
            # ``results`` is the upstream Hubitat MCP wire contract. ``matches``
            # remains accepted for compatibility with older/proxied servers.
            for field in ("results", "matches"):
                candidates: Any = container.get(field)
                if isinstance(candidates, list):
                    return [
                        item for item in candidates if isinstance(item, dict)
                    ]
        return []

    @classmethod
    def discovered_tools(
        cls,
        result: MCPToolResult,
        available: dict[str, MCPTool],
    ) -> list[MCPTool]:
        """Resolve explicit search-hit gateway names against known tools."""

        if result.is_error:
            return []
        names: list[str] = []
        seen: set[str] = set()
        for item in cls._match_items(result.data):
            gateway = item.get("gateway")
            if not isinstance(gateway, str):
                continue
            name = gateway.strip()
            if name == SEARCH_TOOL or name in seen or name not in available:
                continue
            seen.add(name)
            names.append(name)
        return [available[name] for name in names]

    @property
    def available_names(self) -> frozenset[str]:
        return frozenset(self._available)

    @property
    def declared_names(self) -> tuple[str, ...]:
        return tuple(self._declared)

    @property
    def declared_tools(self) -> list[MCPTool]:
        return list(self._declared.values())

    def declared_tool(self, name: str) -> MCPTool | None:
        """Return a tool only when it is currently visible to the model."""

        return self._declared.get(name)

    def available_tool(self, name: str) -> MCPTool | None:
        """Return a known tool regardless of current model visibility."""

        return self._available.get(name)

    def replace_declared(self, names: Iterable[str]) -> list[str]:
        """Replace visible tools and return unavailable requested names."""

        requested = list(dict.fromkeys(str(name) for name in names if str(name)))
        self._declared = {
            name: self._available[name]
            for name in requested
            if name in self._available
        }
        return [name for name in requested if name not in self._available]

    def expand(self, result: MCPToolResult) -> list[MCPTool]:
        """Add newly discovered known gateways, preserving result order."""

        additions = [
            tool
            for tool in self.discovered_tools(result, self._available)
            if tool.name not in self._declared
        ]
        self._declared.update({tool.name: tool for tool in additions})
        return additions

    def schemas(self) -> list[dict[str, Any]]:
        return [self.tool_schema(tool) for tool in self._declared.values()]


__all__ = ["INITIAL_TOOL_ORDER", "SEARCH_TOOL", "ToolDiscoveryCatalog"]

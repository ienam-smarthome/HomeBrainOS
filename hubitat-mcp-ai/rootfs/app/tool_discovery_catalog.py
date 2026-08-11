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
    LOCAL_DEVICE_HISTORY_TOOL,
    LOCAL_FILTER_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL,
    LOCAL_HUB_INFO_TOOL,
    LOCAL_LOCATION_EVENTS_TOOL,
    LOCAL_QUERY_TOOL,
    LOCAL_RESOLVE_TOOL,
    LOCAL_WEATHER_TOOL,
)


SEARCH_TOOL = "hub_search_tools"

INITIAL_TOOL_ORDER = (
    SEARCH_TOOL,
    "hub_get_tool_guide",
    "hub_read_diagnostics",
    LOCAL_FILTER_TOOL,
    LOCAL_QUERY_TOOL,
    LOCAL_RESOLVE_TOOL,
    LOCAL_DEVICE_HISTORY_TOOL,
    LOCAL_LOCATION_EVENTS_TOOL,
    LOCAL_ACTIVE_LIGHTS_TOOL,
    LOCAL_ACTIVE_ROOMS_TOOL,
    LOCAL_ACTIVE_SWITCHES_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL,
    LOCAL_HUB_INFO_TOOL,
    LOCAL_WEATHER_TOOL,
    LOCAL_CONTROL_TOOL,
)

# Structured upstream operations covered by stricter local adapters. Discovery
# may return the broad gateway that hosts one of these operations, but exposing
# that gateway would let the model bypass the adapter's resolution, bounds, and
# evidence contract. Keep this mapping operation-based rather than prompt-based.
LOCAL_OPERATION_WRAPPERS = {
    "hub_list_device_events": LOCAL_DEVICE_HISTORY_TOOL,
}

# The orchestrator seeds discovery with the raw, unfiltered original-request
# text (e.g. "living room light"), and the upstream hub_search_tools search is
# a fuzzy match over tool names/descriptions on the live Hubitat MCP server --
# not something this app controls. A word like "room" can legitimately rank a
# handful of unrelated multi-op gateways (hub_read_rooms, hub_manage_rooms)
# alongside the one the request actually needs, since upstream returns
# already-ranked, most-relevant-first hits. Previously every ranked gateway
# hit expanded the declared registry unconditionally.
#
# Live evidence: two successful same-session requests each got exactly one
# discovery addition (hub_manage_rule_machine -- apparently a broad, mostly
# harmless top hit regardless of query) for a total of 15 declared tools, and
# both completed normally. A third, near-identical "living room light"
# request additionally matched hub_read_rooms and hub_manage_rooms -- two
# unrelated room-admin gateways -- pushing the same request to 17 declared
# tools, and the model answered across two rounds without calling any tool at
# all (a live "Refused" grounding failure, zero evidence gathered).
#
# A cap of 1 would fully reproduce the known-good shape for that specific
# case, but a genuine multi-gateway need exists too (e.g. "create a Rule
# Machine rule" legitimately wants both hub_manage_rule_machine and
# hub_read_rules declared together). Capping at 2 keeps that documented case
# intact while still dropping the long incidental tail beyond upstream's top
# two ranked hits, bounding what was previously unbounded growth.
MAX_DISCOVERED_GATEWAYS = 2


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
            operation = item.get("tool")
            wrapper = (
                LOCAL_OPERATION_WRAPPERS.get(operation)
                if isinstance(operation, str)
                else None
            )
            if wrapper is not None and wrapper in available:
                continue
            gateway = item.get("gateway")
            if not isinstance(gateway, str):
                continue
            name = gateway.strip()
            if name == SEARCH_TOOL or name in seen or name not in available:
                continue
            seen.add(name)
            names.append(name)
            if len(names) >= MAX_DISCOVERED_GATEWAYS:
                break
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


__all__ = [
    "INITIAL_TOOL_ORDER",
    "LOCAL_OPERATION_WRAPPERS",
    "SEARCH_TOOL",
    "ToolDiscoveryCatalog",
]

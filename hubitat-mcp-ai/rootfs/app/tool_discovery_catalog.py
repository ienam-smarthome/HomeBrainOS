"""Bounded structured tool discovery for the Hubitat MCP agent.

The catalog owns available/declared registry state and schema expansion from
successful ``hub_search_tools`` results. It never inspects user prompt text and
does not decide when discovery, confirmation, or execution should occur.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

from gateway_argument_view import gateway_operation
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
        self._operation_gateways: dict[str, set[str]] = {}
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
    def _result_operation_gateways(
        cls,
        result: MCPToolResult,
    ) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}
        if result.is_error:
            return mapping
        for item in cls._match_items(result.data):
            operation = item.get("tool")
            gateway = item.get("gateway")
            if not isinstance(operation, str) or not isinstance(gateway, str):
                continue
            op = operation.strip()
            gw = gateway.strip()
            if op and gw:
                mapping.setdefault(op, set()).add(gw)
        return mapping

    @staticmethod
    def _schema_operations(tool: MCPTool) -> set[str]:
        schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
        props = schema.get("properties")
        if not isinstance(props, dict):
            return set()
        tool_prop = props.get("tool")
        if not isinstance(tool_prop, dict):
            return set()
        values = tool_prop.get("enum")
        if not isinstance(values, list):
            return set()
        return {str(value).strip() for value in values if str(value).strip()}

    @staticmethod
    def _description_operations(tool: MCPTool) -> set[str]:
        # Upstream gateway descriptions commonly list operation names verbatim.
        # Treat them as a compatibility catalog only when at least two distinct
        # sub-operations are present, avoiding false constraints from incidental
        # examples in ordinary non-gateway tool descriptions.
        names = set(re.findall(r"\bhub_[a-z0-9_]+\b", tool.description or ""))
        names.discard(tool.name)
        return names if len(names) >= 2 else set()

    def gateway_operation_error(
        self,
        gateway: str,
        arguments: dict[str, Any],
    ) -> str | None:
        """Reject a sub-operation that is provably incompatible with a gateway.

        Compatibility comes from the live tool schema/description and successful
        hub_search_tools mappings learned in this request. Unknown combinations
        are left alone rather than guessed.
        """

        operation = gateway_operation(arguments)
        if not operation:
            return None
        tool = self.available_tool(gateway)
        if tool is None:
            return None

        schema_ops = self._schema_operations(tool)
        if schema_ops and operation not in schema_ops:
            return (
                f"Operation {operation!r} is not allowed by gateway {gateway!r}; "
                f"allowed operations include {sorted(schema_ops)}."
            )

        description_ops = self._description_operations(tool)
        if description_ops and operation not in description_ops:
            known = self._operation_gateways.get(operation)
            if known and gateway not in known:
                return (
                    f"Operation {operation!r} belongs to discovered gateway(s) "
                    f"{sorted(known)}, not {gateway!r}."
                )
            return (
                f"Operation {operation!r} is not listed by gateway {gateway!r}. "
                "Use hub_search_tools for that operation before calling a gateway."
            )

        known = self._operation_gateways.get(operation)
        if known and gateway not in known:
            return (
                f"Operation {operation!r} belongs to discovered gateway(s) "
                f"{sorted(known)}, not {gateway!r}."
            )
        return None

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

        learned = self._result_operation_gateways(result)
        for operation, gateways in learned.items():
            self._operation_gateways.setdefault(operation, set()).update(gateways)

        additions = [
            tool
            for tool in self.discovered_tools(result, self._available)
            if tool.name not in self._declared
        ]
        self._declared.update({tool.name: tool for tool in additions})
        return additions

    @staticmethod
    def _causal_provenance_read_tool(tool: MCPTool) -> bool:
        """Return True for read-only gateways useful for command provenance."""

        name = str(tool.name or "").casefold()
        if name == SEARCH_TOOL:
            return True
        # Completion must never reopen device/sensor exploration or expose
        # mutating Rule Machine gateways. Upstream read gateways consistently use
        # hub_read_*; keep the allow-list semantic rather than tied to one install.
        if not name.startswith("hub_read_"):
            return False

        schema_text = str(tool.input_schema or {}).casefold()
        haystack = " ".join((name, str(tool.description or "").casefold(), schema_text))
        return any(
            token in haystack
            for token in (
                "app",
                "rule",
                "log",
                "diagnostic",
            )
        )

    def causal_provenance_names(self) -> tuple[str, ...]:
        """Known read tools allowed during bounded causal completion.

        Completion is already a narrow evidence phase, so it can use the schemas
        returned by MCP list_tools directly instead of paying for fuzzy discovery
        merely to expose an app/rule/log gateway that HomeBrain already knows is
        installed. Keep the view small and read-only.
        """

        names: list[str] = []
        search = self._available.get(SEARCH_TOOL)
        if search is not None:
            names.append(SEARCH_TOOL)

        candidates = [
            (name, tool)
            for name, tool in self._available.items()
            if name != SEARCH_TOOL and self._causal_provenance_read_tool(tool)
        ]
        # Prefer explicit provenance gateway names, then preserve MCP registry
        # order as the tiebreaker. Four read gateways plus search is a deliberately
        # small completion registry.
        priorities = {
            "hub_read_diagnostics": 0,
            "hub_read_apps_code": 1,
            "hub_read_rules": 2,
        }
        indexed = {name: index for index, (name, _tool) in enumerate(candidates)}
        candidates.sort(
            key=lambda item: (
                priorities.get(item[0], 10),
                indexed.get(item[0], 0),
            )
        )
        names.extend(name for name, _tool in candidates[:4])
        return tuple(names)

    def activate_causal_provenance_view(self) -> tuple[str, ...]:
        """Replace the declared registry with the bounded provenance view."""

        names = self.causal_provenance_names()
        self.replace_declared(names)
        return names

    def causal_provenance_schemas(self) -> list[dict[str, Any]]:
        return [
            self.tool_schema(self._available[name])
            for name in self.causal_provenance_names()
            if name in self._available
        ]

    def schemas(self) -> list[dict[str, Any]]:
        return [self.tool_schema(tool) for tool in self._declared.values()]


__all__ = [
    "INITIAL_TOOL_ORDER",
    "LOCAL_OPERATION_WRAPPERS",
    "SEARCH_TOOL",
    "ToolDiscoveryCatalog",
]

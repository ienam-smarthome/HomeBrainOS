from __future__ import annotations

import asyncio
import json
import math
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any

from device_intelligence_index import (
    _attributes,
    _device_id,
    _device_rows,
    _label,
    _normalise,
    _room_name,
)
from mcp_client import MCPError, MCPTool, MCPToolResult
from mcp_state_broker_adaptive import AdaptiveGatewayMCPStateBroker


InvalidationCallback = Callable[[str], Awaitable[None] | None]

_SEARCH_TOOL = "homebrain_search_devices"
_SEARCH_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "capabilities",
    "currentStates",
    "attributes",
    "disabled",
    "lastActivity",
]
_STOP_WORDS = {
    "a", "an", "and", "are", "can", "device", "devices", "do", "does",
    "find", "for", "from", "get", "give", "i", "in", "is", "it",
    "locate", "me", "my", "of", "on", "please", "show", "the", "to",
    "used", "what", "which", "with",
}


class IndexedMCPStateBroker(AdaptiveGatewayMCPStateBroker):
    """MCP broker with invalidation and schema-safe structured device search.

    ``homebrain_search_devices`` is model-visible, but its source of truth remains
    Hubitat MCP's ``hub_list_devices`` result. The complete structured inventory is
    ranked locally, so the model never searches a character-truncated device list.
    """

    SEARCH_FIELDS = tuple(_SEARCH_FIELDS)

    _RULE_WRITE_ACTION_PREFIXES = (
        "create_", "update_", "delete_", "pause_", "resume_", "enable_",
        "disable_", "run_", "test_", "call_", "set_",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._invalidation_callbacks: list[InvalidationCallback] = []

    async def list_tools(self, refresh: bool = False) -> list[MCPTool]:
        tools = list(await self.client.list_tools(refresh=refresh))
        if not any(tool.name == _SEARCH_TOOL for tool in tools):
            tools.insert(
                0,
                MCPTool(
                    name=_SEARCH_TOOL,
                    description=(
                        "Search the complete selected Hubitat device inventory by natural "
                        "description. Returns ranked candidates with exact device IDs, labels, "
                        "rooms, capabilities and current states. Use this before "
                        "hub_read_devices or any device command when a device is described."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The user's device name or natural description.",
                            },
                            "limit": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 12,
                                "default": 6,
                            },
                        },
                        "required": ["query"],
                    },
                ),
            )
        return tools

    async def get_tool(self, name: str) -> MCPTool | None:
        for tool in await self.list_tools():
            if tool.name == name:
                return tool
        return None

    @staticmethod
    def _schema_supported_fields(tool: Any, desired: list[str]) -> list[str]:
        """Intersect a field projection with the live MCP tool schema when exposed."""
        schema = getattr(tool, "input_schema", None)
        if not isinstance(schema, dict):
            return list(desired)
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return list(desired)
        fields_schema = properties.get("fields")
        if not isinstance(fields_schema, dict):
            return list(desired)
        items = fields_schema.get("items")
        if not isinstance(items, dict):
            return list(desired)
        allowed = items.get("enum")
        if not isinstance(allowed, list) or not allowed:
            return list(desired)
        allowed_names = {str(value) for value in allowed}
        return [field for field in desired if field in allowed_names]

    async def _inventory_arguments(self) -> dict[str, Any]:
        desired = list(self.SEARCH_FIELDS)
        upstream = await self.client.get_tool("hub_list_devices")
        fields = self._schema_supported_fields(upstream, desired)
        args: dict[str, Any] = {
            "detailed": False,
            "format": "summary",
        }
        if fields:
            args["fields"] = fields
        return await self.client.supported_arguments("hub_list_devices", args)

    async def _load_search_inventory(self) -> MCPToolResult:
        args = await self._inventory_arguments()
        try:
            return await super().call_tool("hub_list_devices", args)
        except MCPError as exc:
            text = str(exc).lower()
            if "unknown fields" not in text and "invalid params" not in text:
                raise
            fallback = dict(args)
            fallback.pop("fields", None)
            return await super().call_tool("hub_list_devices", fallback)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        arguments = arguments if isinstance(arguments, dict) else {}
        if name != _SEARCH_TOOL:
            return await super().call_tool(name, arguments)

        query = str(arguments.get("query") or "").strip()
        try:
            limit = max(1, min(12, int(arguments.get("limit") or 6)))
        except (TypeError, ValueError):
            limit = 6
        if not query:
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={"isError": True},
                text="A non-empty device search query is required.",
                data={"query": query, "matches": []},
                is_error=True,
            )

        inventory = await self._load_search_inventory()
        if inventory.is_error:
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={"upstream": inventory.raw},
                text=inventory.text,
                data=inventory.data,
                is_error=True,
            )

        rows = _device_rows(inventory.data)
        matches = self._rank_device_matches(query, rows, limit)
        payload = {
            "query": query,
            "source_tool": "hub_list_devices",
            "inventory_count": len(rows),
            "match_count": len(matches),
            "matches": matches,
        }
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={"structuredContent": payload, "sourceTool": "hub_list_devices"},
            text=text,
            data=payload,
            is_error=False,
        )

    @staticmethod
    def _tokens(value: Any) -> list[str]:
        return [
            token for token in _normalise(value).split()
            if token and token not in _STOP_WORDS
        ]

    @classmethod
    def _rank_device_matches(
        cls,
        query: str,
        devices: list[dict[str, Any]],
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        query_normal = _normalise(query)
        query_tokens = cls._tokens(query) or query_normal.split()

        searchable: list[tuple[dict[str, Any], list[str], list[str], list[str]]] = []
        document_frequency: Counter[str] = Counter()
        for item in devices:
            label_tokens = cls._tokens(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("label", "name", "displayName")
                )
            )
            room_tokens = cls._tokens(_room_name(item))
            metadata_tokens = cls._tokens(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("capabilities", "commands")
                )
            )
            document_frequency.update(set(label_tokens + room_tokens + metadata_tokens))
            searchable.append((item, label_tokens, room_tokens, metadata_tokens))

        total = max(1, len(searchable))
        scored: list[tuple[float, dict[str, Any]]] = []
        for item, label_tokens, room_tokens, metadata_tokens in searchable:
            label = _label(item)
            label_normal = _normalise(label)
            score = 0.0
            if label_normal and label_normal == query_normal:
                score += 30.0
            elif label_normal and label_normal in query_normal:
                score += 18.0
            elif query_normal and query_normal in label_normal:
                score += 14.0

            for token in query_tokens:
                rarity = 1.0 + math.log(
                    (total + 1) / (document_frequency.get(token, 0) + 1)
                )
                for field_tokens, weight in (
                    (label_tokens, 4.0),
                    (room_tokens, 1.5),
                    (metadata_tokens, 1.25),
                ):
                    if token in field_tokens:
                        score += weight * rarity
                        break

            useful_phrase = " ".join(query_tokens)
            if useful_phrase and useful_phrase in " ".join(label_tokens):
                score += 10.0

            if score <= 0:
                continue
            attrs = _attributes(item)
            capabilities = item.get("capabilities")
            scored.append(
                (
                    score,
                    {
                        "id": _device_id(item),
                        "label": label,
                        "name": str(item.get("name") or ""),
                        "room": _room_name(item),
                        "capabilities": capabilities if capabilities is not None else [],
                        "currentStates": attrs,
                        "lastActivity": item.get("lastActivity"),
                        "disabled": bool(item.get("disabled") is True),
                        "match_score": round(score, 3),
                    },
                )
            )

        scored.sort(
            key=lambda entry: (
                -entry[0],
                str(entry[1].get("label") or "").lower(),
                str(entry[1].get("id") or ""),
            )
        )
        return [
            item for _, item in scored[: max(1, min(12, int(limit or 6)))]
        ]

    def register_invalidator(self, callback: InvalidationCallback) -> None:
        if callback not in self._invalidation_callbacks:
            self._invalidation_callbacks.append(callback)

    async def _invalidate_for_write(self, name: str) -> None:
        lowered = str(name or "").lower()
        unprefixed = lowered[4:] if lowered.startswith("hub_") else lowered
        if "rule" in unprefixed and unprefixed.startswith(
            self._RULE_WRITE_ACTION_PREFIXES
        ):
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
                continue
        return count


__all__ = ["IndexedMCPStateBroker"]

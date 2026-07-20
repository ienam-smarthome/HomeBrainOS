from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any

from device_intelligence_index import _attributes, _device_id, _device_rows, _label, _room_name
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
_GENERIC_DEVICE_QUERY_WORDS = {
    "all",
    "any",
    "available",
    "device",
    "devices",
    "discover",
    "find",
    "get",
    "inventory",
    "list",
    "my",
    "please",
    "selected",
    "show",
    "the",
}
_TARGETED_DEVICE_LOOKUP = re.compile(
    r"^(?:please\s+)?(?:find|search(?:\s+for)?|locate|look\s+(?:up|for)|"
    r"show\s+(?:me\s+)?(?:matches\s+for\s+)?)(?:the\s+)?(?:device\s+)?(.+?)[.!?]*$",
    re.IGNORECASE,
)


def _normalise_words(value: str) -> list[str]:
    return [item for item in re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split() if item]


class UnifiedAdaptiveMCPAgent(AdaptiveFinalAnswerAgent):
    """AI-first Hubitat agent with structured device resolution."""

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
            + "\n\nUnified-agent rules: when the user names or describes a particular "
            "physical device, call homebrain_search_devices first with only the current "
            "request's natural description. Use hub_read_devices afterwards when more live "
            "detail is required. When the user asks broadly to list, find or show devices "
            "without a distinguishing name, room or capability, call hub_list_devices rather "
            "than hub_read_devices. Do not reuse an entity from conversation history unless "
            "the current request explicitly refers to it. Do not use hub_search_tools to find "
            "physical devices. Tool-catalogue discovery is never authoritative home data."
        )

    def _is_broad_device_inventory_request(self, query: str) -> bool:
        words = _normalise_words(query)
        if not words or not any(word in {"device", "devices", "inventory"} for word in words):
            return False
        distinguishing = [word for word in words if word not in _GENERIC_DEVICE_QUERY_WORDS]
        return not distinguishing

    @staticmethod
    def _targeted_device_lookup(query: str) -> str | None:
        """Return the requested device description for an explicit lookup request."""

        match = _TARGETED_DEVICE_LOOKUP.fullmatch(str(query or "").strip())
        if not match:
            return None
        requested = " ".join(match.group(1).strip(" .!?").split())
        requested = re.sub(
            r"^(?:the\s+)?(?:device\s+)?",
            "",
            requested,
            flags=re.IGNORECASE,
        ).strip()
        if not requested:
            return None
        words = _normalise_words(requested)
        if not words or all(word in _GENERIC_DEVICE_QUERY_WORDS for word in words):
            return None
        return requested

    async def _execute_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        query: str,
    ) -> tuple[dict[str, Any], str]:
        """Repair a planner inventory call when the user requested one device.

        Small planning models occasionally choose ``hub_list_devices`` for requests such
        as "find front door". That tool is the authoritative inventory source but does not
        perform entity resolution. Redirect the call through HomeBrain's structured search
        broker before synthesis, keeping the model in the same multi-step agent loop.
        """

        requested = self._targeted_device_lookup(query)
        if name == "hub_list_devices" and requested:
            return await super()._execute_tool_call(
                _TARGETED_DEVICE_SEARCH,
                {"query": requested, "limit": 8},
                query,
            )
        return await super()._execute_tool_call(name, arguments, query)

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
        safe_history = history or []
        if self._is_broad_device_inventory_request(query):
            return await self._answer_from_device_inventory(query, safe_history)
        try:
            return await ClaudeStyleOllamaAgent.answer(self, query, safe_history)
        except OllamaUnavailable as exc:
            if not self._should_recover_with_inventory(exc):
                raise
            return await self._answer_from_targeted_device_search(query, safe_history, exc)

    async def _answer_from_device_inventory(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = await self.client.call_tool("hub_list_devices", {})
        if result.is_error:
            raise OllamaUnavailable(f"Device inventory failed: {result.text}")

        rows = _device_rows(result.data)
        room_counts: Counter[str] = Counter()
        devices: list[dict[str, Any]] = []
        for item in rows[:160]:
            room = _room_name(item) or "No room assigned"
            room_counts[room] += 1
            devices.append(
                {
                    "id": _device_id(item),
                    "label": _label(item),
                    "room": room,
                    "capabilities": item.get("capabilities") or [],
                    "currentStates": _attributes(item),
                    "disabled": bool(item.get("disabled") is True),
                }
            )

        payload = {
            "device_count": len(rows),
            "room_counts": dict(sorted(room_counts.items())),
            "devices": devices,
        }
        tool_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
        planner_messages = [
            {"role": "tool", "tool_name": "hub_list_devices", "content": tool_text}
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
            content = f"I found {len(rows)} selected Hubitat devices."
        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "device-inventory",
            "message": content,
            "model": self.model,
            "tools_used": [
                {
                    "name": "hub_list_devices",
                    "arguments": {},
                    "success": True,
                    "preview": tool_text[:700],
                    "evidence": {"device_count": len(rows)},
                }
            ],
            "selected_tools": ["hub_list_devices"],
            "device_count": len(rows),
            "elapsed_ms": elapsed,
        }

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
        evidence = self._tool_evidence(result.data)
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
                    **({"evidence": evidence} if evidence else {}),
                }
            ],
            "selected_tools": [_TARGETED_DEVICE_SEARCH],
            "planner_error": str(planner_error),
            "authoritative_recovery": True,
            "targeted_device_search": True,
            "elapsed_ms": elapsed,
        }


__all__ = ["UnifiedAdaptiveMCPAgent"]

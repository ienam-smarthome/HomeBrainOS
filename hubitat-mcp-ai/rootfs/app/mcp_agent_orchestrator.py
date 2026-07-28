from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult

logger = logging.getLogger("HomeBrainOS.Orchestrator")

_CONFIRM_WORDS = {"confirm", "confirmed", "proceed", "yes", "yes proceed", "do it"}
_SENSITIVE_TERMS = {
    "backup", "delete", "disable", "enable", "factory_reset", "firmware",
    "garage", "lock", "reboot", "restart", "rule", "security", "shutdown", "unlock",
}
_MUTATION_TERMS = {
    "close", "create", "delete", "disable", "enable", "lock", "off", "on",
    "open", "pause", "reboot", "remove", "restart", "resume", "set", "start",
    "stop", "toggle", "unlock", "update", "write",
}
_READ_ONLY_TERMS = {
    "capabilities", "details", "devices", "find", "get", "health", "inventory",
    "list", "read", "rooms", "search", "state", "status",
}
_APP_TERMS = {
    "app", "apps", "automation", "automations", "pause", "paused", "resume",
    "rule", "rules",
}
_DEVICE_TERMS = {
    "battery", "batteries", "device", "devices", "door", "light", "lights",
    "lock", "motion", "sensor", "switch", "temperature", "thermostat",
}


@dataclass(slots=True)
class PendingConfirmation:
    expires_at: float
    tool_name: str
    arguments: dict[str, Any]
    messages: list[dict[str, Any]]
    assistant_message: dict[str, Any]


class UnifiedMCPAgent:
    """Ollama Online agent that executes live Hubitat MCP function calls."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        api_key: str,
        model_name: str = "gemma4:31b",
        *,
        base_url: str = "https://ollama.com",
        timeout_seconds: float = 60,
        tool_limit: int = 48,
        max_tool_rounds: int = 6,
        require_sensitive_confirmation: bool = True,
        confirmation_ttl_seconds: float = 120,
        ai_client: Any | None = None,
    ) -> None:
        self.mcp = mcp_client
        self.api_key = str(api_key or "").strip()
        self.model_name = str(model_name or "").strip()
        if self.model_name.lower().endswith("-cloud"):
            self.model_name = self.model_name[:-6]
        self.base_url = str(base_url or "https://ollama.com").rstrip("/")
        self.timeout_seconds = max(3.0, float(timeout_seconds))
        self.tool_limit = max(1, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self.confirmation_ttl_seconds = max(10.0, float(confirmation_ttl_seconds))
        self._pending: dict[str, PendingConfirmation] = {}
        self._app_manifest: list[dict[str, Any]] = []
        self._app_manifest_at = 0.0
        self.ai_client = ai_client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model_name and self.base_url)

    async def close(self) -> None:
        close = getattr(self.ai_client, "aclose", None)
        if callable(close):
            await close()

    @staticmethod
    def _matches(prompt: str, terms: set[str]) -> bool:
        value = prompt.lower()
        return any(
            re.search(rf"\b{re.escape(term.lower())}\b", value) is not None
            for term in terms
        )

    @staticmethod
    def _requests_mutation(prompt: str) -> bool:
        tokens = set(re.findall(r"[a-z0-9]+", prompt.lower()))
        return bool(tokens & _MUTATION_TERMS)

    @classmethod
    def _call_is_mutation(
        cls, tool: MCPTool | None, arguments: dict[str, Any]
    ) -> bool:
        if not tool or (tool.annotations or {}).get("readOnlyHint") is True:
            return False
        name = tool.name.lower().replace("-", "_")
        tokens = set(re.findall(r"[a-z0-9]+", str(arguments).lower()))
        return (
            bool(tokens & _MUTATION_TERMS)
            or name.startswith(("set_", "create_", "delete_", "update_"))
            or "_manage_" in name
        )

    @staticmethod
    def _tool_succeeded(result: MCPToolResult) -> bool:
        if result.is_error:
            return False
        data = result.data
        if isinstance(data, dict):
            if data.get("success") is False or data.get("error"):
                return False
            for key in ("result", "data", "output"):
                nested = data.get(key)
                if isinstance(nested, dict) and (
                    nested.get("success") is False or nested.get("error")
                ):
                    return False
        return True

    @classmethod
    def _select_tools(cls, prompt: str, tools: list[MCPTool]) -> list[MCPTool]:
        names: set[str] | None = None
        if cls._matches(prompt, _APP_TERMS):
            names = {
                "hub_read_apps_code", "hub_read_rules",
                "hub_manage_native_rules_and_apps", "hub_manage_rules",
                "hub_search_tools",
            }
        elif cls._matches(prompt, _DEVICE_TERMS):
            names = {
                "hub_read_devices", "hub_manage_devices",
                "hub_get_info", "hub_search_tools",
            }
        if names is None:
            return tools
        selected = [tool for tool in tools if tool.name in names]
        return selected or tools

    async def _cached_app_manifest(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self._app_manifest and now - self._app_manifest_at < 300:
            return list(self._app_manifest)
        names = {tool.name for tool in await self.mcp.list_tools()}
        if "hub_read_apps_code" not in names:
            return []
        try:
            result = await self.mcp.call_tool(
                "hub_read_apps_code",
                {"tool": "hub_list_apps", "args": {"scope": "instances"}},
            )
            candidates = HubitatMCPClient._find_device_list(result.data) or []
            self._app_manifest = [
                item for item in candidates if isinstance(item, dict)
            ]
            self._app_manifest_at = now
        except Exception as exc:
            logger.warning("Could not build app manifest: %s", exc)
        return list(self._app_manifest)

    async def _system_prompt(self, user_prompt: str = "") -> str:
        rows: list[str] = []
        if not self._matches(user_prompt, _APP_TERMS):
            try:
                for device in await self.mcp.get_cached_devices():
                    label = device.get("label") or device.get("name") or "Unknown device"
                    device_id = device.get("id") or device.get("deviceId")
                    room = device.get("room") or device.get("roomName") or "Unassigned"
                    capabilities = device.get("capabilities") or []
                    if isinstance(capabilities, dict):
                        capabilities = list(capabilities)
                    if not isinstance(capabilities, list):
                        capabilities = [capabilities]
                    rows.append(
                        f"- {label!r} | ID: {device_id} | Room: {room} | "
                        f"Capabilities: {', '.join(map(str, capabilities)) or 'unknown'}"
                    )
            except Exception as exc:
                logger.warning("Could not build live device manifest: %s", exc)
        manifest = "\n".join(rows) or "Device manifest omitted or unavailable."
        app_section = ""
        if self._matches(user_prompt, _APP_TERMS):
            apps = await self._cached_app_manifest()
            app_rows = []
            for app in apps:
                app_id = app.get("id") or app.get("appId")
                label = app.get("label") or app.get("name") or app.get("displayName")
                if app_id is not None and label:
                    app_rows.append(f"- {label!r} | appId: {app_id}")
            app_section = (
                "\n\nLIVE APP MANIFEST\n"
                + ("\n".join(app_rows) if app_rows else "No live app manifest available.")
                + "\nPause/resume Rule Machine apps through "
                "hub_manage_native_rules_and_apps with tool='hub_set_rule_paused' "
                "and args={'appId': <id>, 'value': true to pause or false to resume}."
            )
        return (
            "You are HomeBrainOS, a concise smart-home assistant. Use Hubitat MCP tools "
            "for every live state claim and action. Match informal names against the live "
            "manifest and use exact IDs whenever possible. Never invent devices, states, "
            "tool results, or successful actions. Ask one short clarification only when "
            "needed. Sensitive actions are confirmed by the host. This MCP server uses "
            "category gateways: call a gateway with tool='<sub-tool name>' and "
            "args={<sub-tool arguments>}. For device questions, use hub_read_devices "
            "with tool='hub_list_devices' or tool='hub_get_device'; do not call the "
            "gateway with empty arguments.\n\n"
            f"LIVE DEVICE MANIFEST\n{manifest}{app_section}"
        )

    @staticmethod
    def _tool_schema(tool: MCPTool) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        }

    @staticmethod
    def _history(history: Any) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for item in list(history or [])[-20:]:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            role = "assistant" if item.get("role") in {"assistant", "model"} else "user"
            content = item.get("content") or item.get("text")
            if content:
                messages.append({"role": role, "content": str(content)})
        return messages

    @staticmethod
    def _result_payload(result: MCPToolResult) -> str:
        payload = (
            {"error": result.text or "MCP tool failed"}
            if result.is_error
            else {"result": result.data if result.data is not None else result.text}
        )
        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _is_sensitive(tool: MCPTool, arguments: dict[str, Any]) -> bool:
        annotations = tool.annotations or {}
        if annotations.get("readOnlyHint") is True:
            return False
        name = tool.name.lower().replace("-", "_")
        argument_text = str(arguments).lower().replace("-", "_")
        tokens = set(re.findall(r"[a-z0-9]+", argument_text))
        if name == "hub_manage_devices":
            if tokens & _MUTATION_TERMS:
                return True
            if tokens & _READ_ONLY_TERMS:
                return False
        if annotations.get("destructiveHint") is True:
            return True
        return any(term in f"{name} {argument_text}" for term in _SENSITIVE_TERMS)

    async def _chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Ollama Online API key is not configured")
        response = await self.ai_client.post(
            f"{self.base_url}/api/chat",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model_name,
                "messages": messages,
                "tools": tools or None,
                "stream": False,
                "options": {"temperature": 0.1},
            },
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama returned no assistant message")
        return message

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        final_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "Answer the original request now using only the MCP results already "
                    "provided. Do not request another tool. Be concise and factual."
                ),
            },
        ]
        response = await self._chat(final_messages, [])
        return str(response.get("content") or "The MCP request completed without a written answer.")

    def _take_confirmation(
        self, session_id: str, prompt: str
    ) -> PendingConfirmation | None:
        pending = self._pending.get(session_id)
        if not pending:
            return None
        if pending.expires_at <= time.monotonic():
            self._pending.pop(session_id, None)
            return None
        if " ".join(prompt.strip().lower().split()) not in _CONFIRM_WORDS:
            return None
        self._pending.pop(session_id, None)
        return pending

    async def _resume_confirmation(
        self, pending: PendingConfirmation, tools: list[dict[str, Any]]
    ) -> str:
        try:
            result = await self.mcp.call_tool(pending.tool_name, pending.arguments)
            content = self._result_payload(result)
        except Exception as exc:
            content = json.dumps({"error": str(exc)})
        messages = [
            *pending.messages,
            pending.assistant_message,
            {"role": "tool", "tool_name": pending.tool_name, "content": content},
        ]
        response = await self._chat(messages, tools)
        return str(response.get("content") or "Confirmed command completed.")

    async def process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        all_tools = (await self.mcp.list_tools())[: self.tool_limit]
        pending = self._take_confirmation(session_id, user_prompt)
        if pending:
            declared = [
                tool for tool in all_tools if tool.name == pending.tool_name
            ] or all_tools
        else:
            declared = self._select_tools(user_prompt, all_tools)
        by_name = {tool.name: tool for tool in declared}
        tools = [self._tool_schema(tool) for tool in declared]
        if pending:
            return await self._resume_confirmation(pending, tools)
        messages = [
            {"role": "system", "content": await self._system_prompt(user_prompt)},
            *self._history(conversation_history),
            {"role": "user", "content": str(user_prompt).strip()},
        ]
        completed_calls: set[str] = set()
        mutation_requested = self._requests_mutation(user_prompt)
        successful_mutations = 0
        failed_mutation = ""
        for _ in range(self.max_tool_rounds):
            assistant = await self._chat(messages, tools)
            calls = assistant.get("tool_calls") or []
            if not calls:
                if mutation_requested and successful_mutations == 0:
                    if failed_mutation:
                        return f"The Hubitat action failed: {failed_mutation}"
                    return (
                        "I did not execute a Hubitat control tool, so no device state "
                        "was changed. Please try again with the exact device name."
                    )
                return str(assistant.get("content") or "Done.")
            sensitive: list[tuple[str, dict[str, Any]]] = []
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                arguments = dict(arguments)
                tool = by_name.get(name)
                if (
                    tool
                    and self.require_sensitive_confirmation
                    and self._is_sensitive(tool, arguments)
                ):
                    sensitive.append((name, arguments))
            if sensitive:
                if session_id == "default":
                    return "A unique session_id is required before I can queue a sensitive Hubitat action."
                if len(sensitive) > 1:
                    return "This request proposed multiple sensitive actions. Please request and confirm them one at a time."
                name, arguments = sensitive[0]
                self._pending[session_id] = PendingConfirmation(
                    time.monotonic() + self.confirmation_ttl_seconds,
                    name,
                    arguments,
                    list(messages),
                    assistant,
                )
                return f"Please confirm before I run the sensitive Hubitat action `{name}`."
            messages.append(assistant)
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                signature = json.dumps(
                    [name, arguments], sort_keys=True, ensure_ascii=False, default=str
                )
                if signature in completed_calls:
                    return await self._final_answer(messages)
                completed_calls.add(signature)
                try:
                    tool = by_name.get(name)
                    if not tool:
                        content = json.dumps({"error": f"Undeclared MCP tool: {name}"})
                    else:
                        result = await self.mcp.call_tool(name, dict(arguments))
                        content = self._result_payload(result)
                        if self._call_is_mutation(tool, dict(arguments)):
                            if self._tool_succeeded(result):
                                successful_mutations += 1
                            else:
                                failed_mutation = result.text or "MCP reported an error"
                except Exception as exc:
                    logger.exception("MCP tool %s failed", name)
                    content = json.dumps({"error": str(exc)})
                    if self._call_is_mutation(by_name.get(name), dict(arguments)):
                        failed_mutation = str(exc)
                messages.append({"role": "tool", "tool_name": name, "content": content})
        return await self._final_answer(messages)


__all__ = ["UnifiedMCPAgent"]

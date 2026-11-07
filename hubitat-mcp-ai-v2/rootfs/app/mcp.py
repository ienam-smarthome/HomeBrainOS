"""Minimal Streamable HTTP MCP transport for the v2 read-only pilot.

No v1 orchestration, device-specific routing or answer publication policy.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


class MCPError(RuntimeError):
    pass


# Frozen upstream read surface, reviewed at 98bc7ca2d0f1bd2e2857962292b33d83683bc2b0.
# Unknown names fail closed even if their names or annotations claim to be reads.
READ_GATEWAYS = {
    "hub_read_apps_code": [
        "hub_list_apps",
        "hub_list_drivers",
        "hub_get_source",
        "hub_list_libraries",
        "hub_list_bundles",
        "hub_list_backups",
        "hub_get_backup",
        "hub_list_device_dependents",
        "hub_get_app_config",
        "hub_list_hpm_packages"
    ],
    "hub_read_diagnostics": [
        "hub_get_logs",
        "hub_get_metrics",
        "hub_get_memory_history",
        "hub_get_device_health",
        "hub_get_radio_details",
        "hub_list_captured_states"
    ],
    "hub_read_rules": [
        "hub_get_custom_rule",
        "hub_list_rules",
        "hub_get_rule_health",
        "hub_list_rule_local_variables",
        "hub_get_visual_rule"
    ],
    "hub_read_devices": [
        "hub_list_devices",
        "hub_get_device",
        "hub_get_device_attribute",
        "hub_list_device_events",
        "hub_get_compatible_devices",
        "hub_get_hub_mesh"
    ],
    "hub_read_rooms": [
        "hub_list_rooms",
        "hub_get_room"
    ],
    "hub_read_files": [
        "hub_list_files",
        "hub_read_file"
    ],
    "hub_read_variables": [
        "hub_list_variables",
        "hub_get_variable",
        "hub_list_variable_changes"
    ],
    "hub_read_dashboards": [
        "hub_list_dashboards",
        "hub_get_dashboard"
    ]
}
READ_TOOLS = frozenset({
    "hub_search_tools", "hub_get_tool_guide", "hub_get_info",
    "hub_list_modes", "hub_get_hsm_status",
}).union(*(set(names) for names in READ_GATEWAYS.values()))


def is_read_tool(name: str) -> bool:
    return name in READ_TOOLS or name in READ_GATEWAYS


_SECRET_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|credential)",
    re.IGNORECASE,
)
_SECRET_TEXT = re.compile(
    r'(?i)((?:"?)(?:access_token|api_key|password|secret|token)(?:"?)\s*[:=]\s*"?)([^\s&"\',}]+)'
)
_BEARER = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/-]{8,}")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): ("[REDACTED]" if _SECRET_KEY.search(str(key)) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _BEARER.sub("Bearer [REDACTED]", _SECRET_TEXT.sub(r"\1[REDACTED]", value))
    return value


class ReadOnlyMCP:
    def __init__(self, url: str, token: str = "", timeout: int = 25):
        url = (url or "").strip()
        parts = urlsplit(url)
        if (parts.scheme not in ("http", "https") or not parts.netloc or parts.fragment
                or parts.username or parts.password):
            raise MCPError("Configure a valid HTTP(S) Hubitat MCP endpoint URL")
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if token.strip() and "access_token" not in query:
            query["access_token"] = token.strip()
        self.url = urlunsplit((
            parts.scheme, parts.netloc, parts.path, urlencode(query), ""
        ))
        self._session: str | None = None
        self._id = 0
        self._initialized = False
        self._lock = asyncio.Lock()
        self._tools: dict[str, dict] = {}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(timeout)),
            follow_redirects=False,
            trust_env=False,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "User-Agent": "Hubitat-MCP-AI-v2/2.0",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _next(self) -> int:
        self._id += 1
        return self._id

    async def _post(self, request: dict, empty_ok: bool = False) -> dict:
        headers = {"Mcp-Session-Id": self._session} if self._session else {}
        try:
            response = await self._client.post(self.url, json=request, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MCPError(f"MCP HTTP {exc.response.status_code}") from None
        except httpx.TimeoutException:
            raise MCPError("MCP timed out") from None
        except httpx.RequestError:
            raise MCPError("MCP transport failed") from None

        if response.headers.get("Mcp-Session-Id"):
            self._session = response.headers["Mcp-Session-Id"]
        if not response.content:
            if empty_ok:
                return {}
            raise MCPError("MCP returned no response")
        if "text/event-stream" in response.headers.get("content-type", "").lower():
            events = []
            for line in response.text.splitlines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("id") == request.get("id"):
                    events.append(event)
            if not events:
                if empty_ok:
                    return {}
                raise MCPError("MCP returned no matching SSE result")
            result = events[-1]
        else:
            try:
                result = response.json()
            except ValueError:
                raise MCPError("MCP response was not JSON") from None
        if not isinstance(result, dict):
            raise MCPError("Unexpected MCP response")
        if result.get("error"):
            error = result["error"]
            message = str(error.get("message", "MCP RPC error")) if isinstance(error, dict) else str(error)
            raise MCPError(str(redact(message))[:350])
        return result

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            response = await self._post({
                "jsonrpc": "2.0", "id": self._next(), "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "hubitat-mcp-ai-v2", "version": "2.0.0"},
                },
            })
            if "result" not in response:
                raise MCPError("MCP initialize returned no result")
            self._initialized = True
            try:
                await self._post({
                    "jsonrpc": "2.0", "method": "notifications/initialized"
                }, empty_ok=True)
            except MCPError:
                pass

    async def list_tools(self) -> list[dict]:
        await self.initialize()
        if not self._tools:
            response = await self._post({
                "jsonrpc": "2.0", "id": self._next(), "method": "tools/list",
                "params": {},
            })
            declared = response.get("result", {}).get("tools", [])
            if not isinstance(declared, list):
                raise MCPError("Invalid MCP tool catalog")
            self._tools = {
                tool["name"]: tool for tool in declared
                if isinstance(tool, dict)
                and isinstance(tool.get("name"), str)
                and is_read_tool(tool["name"])
            }
        return list(self._tools.values())

    async def call(self, name: str, arguments: dict) -> dict:
        if not is_read_tool(name):
            raise MCPError("Tool is not available in the read-only v2 pilot")
        await self.list_tools()
        if name not in self._tools:
            raise MCPError("Tool is not available in the read-only v2 pilot")
        if not isinstance(arguments, dict):
            raise MCPError("MCP arguments must be an object")
        if name in READ_GATEWAYS and arguments.get("tool") not in READ_GATEWAYS[name]:
            raise MCPError("Sub-tool is not available in this read-only gateway")
        response = await self._post({
            "jsonrpc": "2.0", "id": self._next(), "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise MCPError("Invalid MCP tool response")
        return redact(result)

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


class MCPError(RuntimeError):
    pass


@dataclass(slots=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]

    def as_ollama_tool(self) -> dict[str, Any]:
        schema = self.input_schema if isinstance(self.input_schema, dict) else {}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description or self.name,
                "parameters": schema or {"type": "object", "properties": {}},
            },
        }


@dataclass(slots=True)
class MCPToolResult:
    name: str
    arguments: dict[str, Any]
    raw: dict[str, Any]
    text: str
    data: Any
    is_error: bool = False


class HubitatMCPClient:
    """Small Streamable-HTTP MCP client tailored to Hubitat's local endpoint."""

    def __init__(
        self,
        endpoint_url: str,
        access_token: str = "",
        timeout_seconds: float = 25,
    ) -> None:
        self.endpoint_url = self._with_token(endpoint_url.strip(), access_token.strip())
        self.timeout_seconds = max(3.0, float(timeout_seconds))
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "User-Agent": "Hubitat-MCP-AI/0.1",
            },
        )
        self._session_id: str | None = None
        self._request_id = 0
        self._initialized = False
        self._tools: dict[str, MCPTool] = {}
        self._lock = asyncio.Lock()
        self.server_info: dict[str, Any] = {}

    @staticmethod
    def _with_token(url: str, token: str) -> str:
        if not url:
            return ""
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if token and not query.get("access_token"):
            query["access_token"] = token
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @property
    def configured(self) -> bool:
        return self.endpoint_url.startswith(("http://", "https://"))

    async def close(self) -> None:
        await self._http.aclose()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"online": False, "error": "MCP endpoint is not configured"}
        try:
            await self.initialize()
            tools = await self.list_tools()
            return {
                "online": True,
                "tools": len(tools),
                "server": self.server_info,
                "session": bool(self._session_id),
            }
        except Exception as exc:
            return {"online": False, "error": str(exc)}

    async def initialize(self, force: bool = False) -> None:
        if self._initialized and not force:
            return
        if not self.configured:
            raise MCPError("Hubitat MCP endpoint is not configured")

        async with self._lock:
            if self._initialized and not force:
                return
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "Hubitat MCP AI",
                        "version": "0.1.0",
                    },
                },
            }
            response = await self._post(payload)
            result = self._rpc_result(response)
            self.server_info = result.get("serverInfo") or {}
            self._initialized = True

            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            try:
                await self._post(notification, allow_empty=True)
            except Exception:
                # Some Hubitat implementations are stateless and do not require the notification.
                pass

    async def list_tools(self, refresh: bool = False) -> list[MCPTool]:
        await self.initialize()
        if self._tools and not refresh:
            return list(self._tools.values())

        async with self._lock:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {},
            }
            response = await self._post(payload)
            result = self._rpc_result(response)
            tools = result.get("tools") or []
            parsed: dict[str, MCPTool] = {}
            for item in tools:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                tool = MCPTool(
                    name=str(item["name"]),
                    description=str(item.get("description") or ""),
                    input_schema=item.get("inputSchema") or {
                        "type": "object",
                        "properties": {},
                    },
                )
                parsed[tool.name] = tool
            self._tools = parsed
            return list(parsed.values())

    async def get_tool(self, name: str) -> MCPTool | None:
        await self.list_tools()
        return self._tools.get(name)

    async def supported_arguments(
        self,
        tool_name: str,
        desired: dict[str, Any],
    ) -> dict[str, Any]:
        tool = await self.get_tool(tool_name)
        if not tool:
            return desired
        schema = tool.input_schema or {}
        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            return desired
        return {key: value for key, value in desired.items() if key in properties}

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        await self.initialize()
        arguments = arguments if isinstance(arguments, dict) else {}

        async with self._lock:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments,
                },
            }
            response = await self._post(payload)
            result = self._rpc_result(response)

        content = result.get("content") or []
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(str(item.get("text") or ""))
                elif item.get("text") is not None:
                    text_parts.append(str(item.get("text")))
            elif item is not None:
                text_parts.append(str(item))

        structured = result.get("structuredContent")
        if not text_parts and structured is not None:
            text_parts.append(json.dumps(structured, ensure_ascii=False))

        text = "\n".join(part for part in text_parts if part).strip()
        data = structured if structured is not None else self._decode_tool_text(text)
        is_error = bool(result.get("isError"))
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw=result,
            text=text,
            data=data,
            is_error=is_error,
        )

    async def _post(
        self,
        payload: dict[str, Any],
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        headers: dict[str, Any] = {}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        response = await self._http.post(
            self.endpoint_url,
            json=payload,
            headers=headers,
        )
        if response.headers.get("Mcp-Session-Id"):
            self._session_id = response.headers["Mcp-Session-Id"]

        if response.status_code >= 400:
            detail = response.text.strip()
            raise MCPError(
                f"MCP HTTP {response.status_code}: {detail[:500] or response.reason_phrase}"
            )
        if not response.content:
            if allow_empty:
                return {}
            raise MCPError("MCP returned an empty response")

        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            events = []
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        events.append(json.loads(raw))
                    except json.JSONDecodeError:
                        continue
            if not events:
                if allow_empty:
                    return {}
                raise MCPError("MCP SSE response contained no JSON event")
            return events[-1]

        try:
            value = response.json()
        except Exception as exc:
            raise MCPError(f"MCP returned invalid JSON: {response.text[:500]}") from exc
        if not isinstance(value, dict):
            raise MCPError("MCP JSON response was not an object")
        return value

    @staticmethod
    def _rpc_result(response: dict[str, Any]) -> dict[str, Any]:
        if response.get("error"):
            error = response["error"]
            if isinstance(error, dict):
                message = error.get("message") or json.dumps(error, ensure_ascii=False)
            else:
                message = str(error)
            raise MCPError(message)
        result = response.get("result")
        if result is None:
            return {}
        if not isinstance(result, dict):
            return {"value": result}
        return result

    @staticmethod
    def _decode_tool_text(text: str) -> Any:
        value = text.strip()
        if not value:
            return None
        candidates = [value]
        fenced = re.search(r"```(?:json)?\s*(.*?)```", value, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            candidates.insert(0, fenced.group(1).strip())
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue
        return value

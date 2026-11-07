"""Streamable HTTP MCP transport using the connected server catalog.

No v1 orchestration, device-specific routing or answer publication policy.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from referencing import Registry
from referencing.exceptions import Unresolvable


class MCPError(RuntimeError):
    pass


class MCPContractError(MCPError):
    """Rejected locally before a tools/call request is sent."""


_SECRET_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|credential)",
    re.IGNORECASE,
)
_SECRET_TEXT = re.compile(
    r"""(?ix)(?<![\w-])
    ((?:"?)(?:access_token|api_key|password|passwd|secret|token|authorization|credential)(?:"?)\s*[:=]\s*)
    (?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s&"'{}\[\],]+)
    """
)
_BEARER = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/-]+")


def _scrub_text(value: str) -> str:
    return _SECRET_TEXT.sub(
        lambda match: match[1] + '"[REDACTED]"',
        _BEARER.sub("Bearer [REDACTED]", value),
    )


def _secret_sample(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _secret_sample(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_secret_sample(item) for item in value]
    return "[REDACTED]" if isinstance(value, str) else value


def _redact_schema(value: Any, sensitive: bool = False) -> Any:
    """Preserve schema vocabulary/property names; redact credential samples."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in ("properties", "patternProperties", "$defs", "definitions") and isinstance(item, dict):
                result[key] = {
                    name: _redact_schema(schema, bool(_SECRET_KEY.search(name)))
                    for name, schema in item.items()
                }
            elif key in ("default", "examples") and sensitive:
                result[key] = _secret_sample(item)
            else:
                result[key] = _redact_schema(item, sensitive)
        return result
    if isinstance(value, list):
        return [_redact_schema(item, sensitive) for item in value]
    return _scrub_text(value) if isinstance(value, str) else value


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = str(key)
            if key in ("inputSchema", "outputSchema") and isinstance(item, (dict, bool)):
                result[key] = _redact_schema(item)
            elif _SECRET_KEY.search(key) and not isinstance(item, bool):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        # MCP text blocks frequently contain JSON. Parse before redacting so
        # object/array syntax and secret-named schema properties remain intact.
        try:
            parsed = json.loads(value)
        except (ValueError, RecursionError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            cleaned = redact(parsed)
            return value if cleaned == parsed else json.dumps(cleaned, ensure_ascii=False)
        return _scrub_text(value)
    return value


def is_tool_catalog(result: dict) -> bool:
    """Distinguish upstream schema discovery from executed domain reads."""
    for block in result.get("content", []) or []:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        try:
            payload = json.loads(block.get("text", ""))
        except (ValueError, TypeError):
            continue
        if (isinstance(payload, dict) and payload.get("mode") == "catalog"
                and isinstance(payload.get("tools"), list)):
            return True
    return False


def _validate_arguments(arguments: dict, schema: dict | bool) -> None:
    try:
        validator = validator_for(schema)
        validator.check_schema(schema)
        # Explicit registry never retrieves remote schema references.
        errors = validator(schema, registry=Registry()).iter_errors(arguments)
        error = next(errors, None)
    except (SchemaError, Unresolvable, TypeError, ValueError):
        raise MCPContractError("The live input schema could not be validated; inspect the server schema/guide") from None
    if error:
        path = "/".join(str(part) for part in error.absolute_path) or "<root>"
        # Do not echo invalid argument values: they may be credentials.
        raise MCPContractError(f"Arguments violate the live input schema at {path} ({error.validator}); inspect inputSchema")


class MCPClient:
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
        self._protocol = "2025-03-26"
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
        headers = {"MCP-Protocol-Version": self._protocol} if self._initialized else {}
        if self._session:
            headers["Mcp-Session-Id"] = self._session
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
            self._protocol = response["result"].get("protocolVersion", self._protocol)
            self._initialized = True
            try:
                await self._post({
                    "jsonrpc": "2.0", "method": "notifications/initialized"
                }, empty_ok=True)
            except MCPError:
                pass

    async def list_tools(self, refresh: bool = False) -> list[dict]:
        await self.initialize()
        if refresh or not self._tools:
            tools: dict[str, dict] = {}
            cursor = None
            seen = set()
            while True:
                response = await self._post({
                    "jsonrpc": "2.0", "id": self._next(), "method": "tools/list",
                    "params": {"cursor": cursor} if cursor else {},
                })
                page = response.get("result", {})
                declared = page.get("tools") if isinstance(page, dict) else None
                if not isinstance(declared, list):
                    raise MCPError("Invalid MCP tool catalog")
                for tool in declared:
                    if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
                        raise MCPError("Invalid MCP tool definition")
                    tools[tool["name"]] = tool
                cursor = page.get("nextCursor")
                if not cursor:
                    break
                if not isinstance(cursor, str) or cursor in seen:
                    raise MCPError("Invalid or repeated MCP catalog cursor")
                seen.add(cursor)
            self._tools = tools
        return list(self._tools.values())

    async def call(self, name: str, arguments: dict) -> dict:
        await self.list_tools()
        if name not in self._tools:
            raise MCPError("Tool is not in the connected server catalog")
        if not isinstance(arguments, dict):
            raise MCPError("MCP arguments must be an object")
        schema = self._tools[name].get("inputSchema")
        if isinstance(schema, (dict, bool)):
            _validate_arguments(arguments, schema)
            properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
            # Infer upstream gateway shape from its live schema, never names.
            if "tool" in properties and "args" in properties:
                if not arguments.get("tool") and arguments.get("args"):
                    raise MCPContractError(
                        "Gateway 'tool' must be a top-level sibling of 'args', not inside it. "
                        'Use {"tool":"<name from catalog>","args":{...}} to execute, or {} for schema discovery.'
                    )
                if set(arguments) - set(properties):
                    raise MCPContractError("Gateway tool parameters belong inside 'args'; use only the live top-level properties")
        # Preserve gateway discovery (empty args) and server-owned leaf routing.
        # Never retry a tools/call: an uncertain write outcome must be inspected.
        response = await self._post({
            "jsonrpc": "2.0", "id": self._next(), "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise MCPError("Invalid MCP tool response")
        return redact(result)

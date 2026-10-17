"""Read-only source-code investigation for a named installed Hubitat app.

Installed app instance IDs are NOT code IDs. Use only explicit live metadata,
discover compatible read operations, and bound source reads and output.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any

from mcp_client import tool_succeeded

_APP_ID = re.compile(r"\b(?:app|application)\s*(?:id\s*)?#?\s*(\d{3,7})\b", re.I)
_SOURCE_INTENT = re.compile(
    r"\b(?:groovy|source[- ]code|actual\s+source|source\s+of|"
    r"implementation\s+code|implementation\s+source|"
    r"code\s+implementation|read\s+the\s+code|"
    r"defaultvalue|state\.motionlockout|"
    r"getmotionlockoutdurationminutes|startmotionlockoutfordevice)\b", re.I,
)
_READ_OP = re.compile(r"^hub_(?:get|read|list)_[a-z0-9_]*(?:source|code)[a-z0-9_]*$", re.I)
_DENY_OP = re.compile(r"write|save|install|modify|edit|update|delete|upload|import|set_|create", re.I)
_SYMBOLS = ("motionOffLockoutMinutes", "getMotionLockoutDurationMinutes",
            "startMotionLockoutForDevice", "startMotionLockoutForAllLights",
            "isDeviceMotionLockedOut", "state.motionLockout", "initialize")
MAX_CHUNKS = 16
MAX_CHARS = 250000


def requested_groovy_app_id(prompt: str) -> str | None:
    text = str(prompt or "")
    match = _APP_ID.search(text)
    return match.group(1) if match and _SOURCE_INTENT.search(text) else None


def _containers(payload: Any) -> list[dict[str, Any]]:
    result = [payload] if isinstance(payload, dict) else []
    for item in list(result):
        for key in ("result", "data", "output", "app", "code"):
            nested = item.get(key)
            if isinstance(nested, dict) and nested not in result:
                result.append(nested)
    return result[:10]


def source_code_id(config: dict[str, Any], app_id: str) -> str | None:
    """Only metadata that actually names the installed app may link to code."""
    app = config.get("app")
    if not isinstance(app, dict) or str(app.get("id") or app.get("appId") or "") != app_id:
        return None
    for item in _containers(app):
        for key in ("codeId", "appCodeId", "sourceCodeId", "appCodeID", "appTypeId"):
            value = item.get(key)
            if isinstance(value, (str, int)) and str(value).isdigit():
                return str(value)
    return None


def _matches(data: Any) -> list[dict[str, Any]]:
    for item in _containers(data):
        for key in ("results", "matches"):
            rows = item.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _source_operations(tools: list[Any], discovery: Any) -> list[tuple[str, str]]:
    names = {tool.name for tool in tools}
    found: set[tuple[str, str]] = set()
    for match in _matches(discovery):
        operation, gateway = match.get("tool"), match.get("gateway")
        if (isinstance(operation, str) and isinstance(gateway, str)
                and gateway in names and operation != gateway
                and _READ_OP.fullmatch(operation) and not _DENY_OP.search(operation)):
            found.add((gateway, operation))
    for tool in tools:
        # A gateway named hub_read_apps_code is a TOOL CONTAINER, not a
        # source-read operation. Do not send bare {"appId": ...} to it.
        # Only actual source-read functions qualify.
        if tool.name == "hub_read_apps_code":
            pass
        # Some MCP servers advertise source reads as top-level functions,
        # rather than as an operation inside the apps/code facade.
        if (tool.name != "hub_read_apps_code"
                and _READ_OP.fullmatch(tool.name)
                and not _DENY_OP.search(tool.name)):
            found.add((tool.name, tool.name))
        schema = getattr(tool, "input_schema", {}) or {}
        properties = schema.get("properties") or {}
        enum = (properties.get("tool") or {}).get("enum") or []
        for operation in enum:
            if (isinstance(operation, str) and operation != tool.name
                    and _READ_OP.fullmatch(operation) and not _DENY_OP.search(operation)):
                found.add((tool.name, operation))
    return sorted(found, key=lambda pair: (0 if "source" in pair[1] else 1, pair))


def _source_body(data: Any) -> tuple[str, dict[str, Any]]:
    for item in _containers(data):
        for key in ("source", "sourceCode", "rawSource", "sourceText",
                    "sourceChunk", "chunk", "content", "code", "text"):
            value = item.get(key)
            if isinstance(value, str) and len(value) > 40 and "\n" in value:
                return value, item
    return "", {}


def _excerpts(body: str) -> list[str]:
    lines = body.splitlines()
    result: list[str] = []
    captured: set[int] = set()
    for symbol in _SYMBOLS:
        for index, line in enumerate(lines):
            if symbol.casefold() not in line.casefold() or index in captured:
                continue
            span = list(range(max(0, index - 3), min(len(lines), index + 7)))
            if any(i in captured for i in span):
                continue
            excerpt = "\n".join(f"{i+1}: {lines[i]}" for i in span)
            if sum(len(x) for x in result) + len(excerpt) > 6500:
                return result
            result.append(excerpt)
            captured.update(span)
            break
    return result


@dataclass(slots=True)
class GroovySourceReport:
    message: str
    retrieved: bool = False
    complete: bool = False


class GroovySourceService:
    """Call only source-read operations positively identified by live MCP metadata."""

    def __init__(self, mcp: Any, evidence: Any) -> None:
        self.mcp, self.evidence = mcp, evidence

    def _record(self, gateway: str, operation: str, args: dict[str, Any],
                began: float, ok: bool, summary: str) -> None:
        self.evidence.record(
            gateway,
            args if gateway in {"hub_search_tools", operation}
            else {"tool": operation, "args": args},
            success=ok, elapsed_ms=round((time.monotonic()-began)*1000),
            summary=summary[:200], supports_live_claim=False,
            evidence_kind="groovy_source_discovery" if gateway == "hub_search_tools"
                          else "groovy_source_evidence",
            mutates=False, effect="read",
        )

    async def inspect(self, app_id: str) -> GroovySourceReport:
        title = f"App {app_id} — read-only Groovy implementation investigation:"
        try:
            tools = await self.mcp.list_tools()
        except Exception:
            return GroovySourceReport(title + "\n- MCP tool discovery failed; no source verified.")
        names = {item.name for item in tools}
        discovery: Any = {}
        if "hub_search_tools" in names:
            args = {"query": "read installed custom Groovy app source code codeId chunks"}
            began = time.monotonic()
            try:
                result = await self.mcp.call_tool("hub_search_tools", args)
                ok = tool_succeeded(result)
                discovery = result.data if ok else {}
            except Exception:
                ok = False
            self._record("hub_search_tools", "hub_search_tools", args, began, ok,
                         "Searched live MCP for source-code read operations")
        config: dict[str, Any] = {}
        if "hub_read_apps_code" in names:
            leaf_args = {"appId": app_id, "includeSettings": False}
            began = time.monotonic()
            try:
                result = await self.mcp.call_tool("hub_read_apps_code", {
                    "tool": "hub_get_app_config", "args": leaf_args,
                })
                ok = tool_succeeded(result)
                config = result.data if ok and isinstance(result.data, dict) else {}
            except Exception:
                ok = False
            self._record("hub_read_apps_code", "hub_get_app_config",
                         leaf_args, began, ok, "Read installed app metadata")
        code_id = source_code_id(config, app_id)
        operations = _source_operations(tools, discovery)
        if not operations:
            return GroovySourceReport(
                title + "\n- No source-read operation was verified in the live "
                "MCP schema/discovery results. App configuration cannot prove "
                "Groovy method behaviour."
                + (f"\n- App code ID: {code_id} (metadata)." if code_id else
                   "\n- No instance-to-code mapping verified.")
            )
        viable = next(
            ((gateway, op) for gateway, op in operations
             if code_id or "app" in op), None,
        )
        if viable is None:
            return GroovySourceReport(
                title + "\n- Discovered source operations: "
                + ", ".join(f"{op} via {gateway}" for gateway, op in operations[:4])
                + "\n- Source code ID was not provided by the installed-app "
                  "metadata. No guessed code ID was used."
            )
        gateway, operation = viable
        if operation == "hub_get_source":
            if not code_id:
                return GroovySourceReport(title + "\n- No verified app-to-code ID; refusing a guessed source read.")
            base_args = {"id": code_id, "type": "app"}
        else:
            base_args = {"codeId": code_id} if code_id else {"appId": app_id}
        body = ""
        total: int | None = None
        version: Any = None
        offset = 0
        for index in range(MAX_CHUNKS):
            leaf_args = dict(base_args)
            if operation == "hub_get_source":
                leaf_args.update({"offset": offset, "length": 20000})
            elif index > 0:
                leaf_args.update({"offset": offset, "limit": 65536})
            began = time.monotonic()
            try:
                wire_args = (leaf_args if gateway == operation
                             else {"tool": operation, "args": leaf_args})
                result = await self.mcp.call_tool(gateway, wire_args)
                ok = tool_succeeded(result)
                chunk, meta = _source_body(result.data if ok else {})
            except Exception:
                ok, chunk, meta = False, "", {}
            self._record(gateway, operation, leaf_args, began, ok and bool(chunk),
                         f"Raw source chunk {index+1}: {len(chunk)} chars")
            if not ok or not chunk:
                break
            body += chunk
            version = meta.get("version") or meta.get("codeVersion") or version
            for field in ("totalChars", "totalLength", "sourceLength"):
                if isinstance(meta.get(field), int) and meta[field] >= 0:
                    total = meta[field]
            if len(body) >= MAX_CHARS:
                break
            next_offset = meta.get("nextOffset")
            if isinstance(next_offset, int) and next_offset > offset:
                offset = next_offset
                continue
            if total is not None and len(body) < total:
                offset = len(body)
                continue
            break
        if not body:
            return GroovySourceReport(
                title + f"\n- Verified source operation: {operation} via {gateway}."
                + (f"\n- Verified code ID: {code_id}." if code_id else
                   "\n- Attempted instance-ID read; code ID not verified.")
                + "\n- No raw Groovy source returned. Cannot verify the "
                  "defaultValue declaration, getter, stored lockout expiry or "
                  "updated()/initialize() behaviour."
            )
        complete = total is not None and len(body) == total
        lines = [
            title, f"- Source reader: {operation} via {gateway}.",
            f"- Source text retrieved: {len(body)} characters; "
            + ("complete by declared length." if complete else
               "full source coverage unverified."),
            f"- Retrieved text SHA-256: {hashlib.sha256(body.encode()).hexdigest()}.",
        ]
        if code_id:
            lines.append(f"- Verified code ID: {code_id}.")
        if version is not None:
            lines.append(f"- Source version: {str(version)[:32]}.")
        excerpts = _excerpts(body)
        if excerpts:
            lines.append("Source excerpts (retrieved-text-relative line numbers):")
            lines.extend(excerpts)
        else:
            lines.append("No target lockout symbols found in retrieved source segment.")
        if not complete:
            lines.append("Do not assert that a function is absent or a state write "
                         "never occurs without complete implementation coverage.")
        return GroovySourceReport("\n\n".join(lines), bool(excerpts), complete)


__all__ = ["requested_groovy_app_id", "source_code_id",
           "GroovySourceReport", "GroovySourceService"]

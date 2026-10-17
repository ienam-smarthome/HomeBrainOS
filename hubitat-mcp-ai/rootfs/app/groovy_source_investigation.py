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
            "isDeviceMotionLockedOut", "state.motionLockout",
            "getMotionLockoutStatusSummary", "updated()", "initialize()")
MAX_CHUNKS = 32
MAX_CHARS = 250000
SOURCE_READ_LENGTH = 48000
MAX_SYMBOLS = 12
MAX_EXCERPT_CHARS = 14500


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


def _validated_symbols(symbols: list[str] | None) -> tuple[str, ...]:
    """A model-selected read target, not an implementation-specific branch."""
    if not symbols:
        return _SYMBOLS
    cleaned = []
    for candidate in symbols[:MAX_SYMBOLS]:
        text = str(candidate).strip()
        if (1 <= len(text) <= 100
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*(?:\(\))?", text)
                and text not in cleaned):
            cleaned.append(text)
    return tuple(cleaned) or _SYMBOLS


def _excerpts(body: str, symbols: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Bounded, line-numbered slices for the caller's code questions.

    Source verification is independent of whether a requested symbol appears.
    Multiple occurrences can reveal separate declaration/read/write sites.
    """
    lines = body.splitlines()
    result: list[str] = []
    found: list[str] = []
    selected: set[int] = set()
    budget = 0
    for symbol in _validated_symbols(symbols):
        indexes = [i for i, line in enumerate(lines) if symbol.casefold() in line.casefold()]
        if indexes:
            found.append(symbol)
        for index in indexes[:4]:
            start, stop = max(0, index - 5), min(len(lines), index + 16)
            span = range(start, stop)
            if index in selected:
                continue
            passage = "\n".join(f"{i+1}: {lines[i]}" for i in span)
            if budget + len(passage) > MAX_EXCERPT_CHARS:
                return result, found
            result.append(passage)
            budget += len(passage)
            selected.update(span)
    return result, found


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

    async def inspect(self, app_id: str, symbols: list[str] | None = None) -> GroovySourceReport:
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
        if not code_id and "hub_read_apps_code" in names:
            began = time.monotonic()
            leaf = {"scope": "instances"}
            try:
                result = await self.mcp.call_tool("hub_read_apps_code", {
                    "tool": "hub_list_apps", "args": leaf,
                })
                ok = tool_succeeded(result)
                inventory = result.data if ok else {}
                apps = inventory.get("apps", []) if isinstance(inventory, dict) else []
                for app in apps if isinstance(apps, list) else []:
                    if isinstance(app, dict):
                        code_id = source_code_id({"app": app}, app_id)
                        if code_id:
                            break
            except Exception:
                ok = False
            self._record("hub_read_apps_code", "hub_list_apps",
                         leaf, began, ok,
                         "Read installed app identity and verified code type")
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
        chunk_size = SOURCE_READ_LENGTH
        retries = 0
        incomplete_reason = ""
        # The MCP gateway may return a 47,999-character chunk for a requested
        # 48,000-character page while advertising a larger nextOffset. Never
        # silently skip a character. Retry the same offset with a smaller page,
        # and only append a segment after its offset and nextOffset agree.
        for index in range(MAX_CHUNKS):
            leaf_args = dict(base_args)
            if operation == "hub_get_source":
                leaf_args.update({"offset": offset, "length": chunk_size})
            elif index > 0:
                leaf_args.update({"offset": offset, "limit": min(chunk_size, 48000)})
            began = time.monotonic()
            try:
                wire_args = (leaf_args if gateway == operation
                             else {"tool": operation, "args": leaf_args})
                result = await self.mcp.call_tool(gateway, wire_args)
                ok = tool_succeeded(result)
                chunk, meta = _source_body(result.data if ok else {})
            except Exception:
                ok, chunk, meta = False, "", {}
            if not ok or not chunk:
                incomplete_reason = f"No raw text returned at offset {offset}"
                self._record(gateway, operation, leaf_args, began, False,
                             incomplete_reason)
                if operation == "hub_get_source" and chunk_size > 8000:
                    chunk_size = 16000 if chunk_size > 16000 else 8000
                    retries += 1
                    continue
                break
            actual_offset = meta.get("offset", offset)
            advertised_next = meta.get("nextOffset")
            expected_next = offset + len(chunk)
            chunk_total = next((
                meta[field] for field in ("totalChars", "totalLength", "sourceLength")
                if isinstance(meta.get(field), int) and meta[field] > 0
            ), None)
            returned_id = meta.get("appId")
            chunk_version = meta.get("version") or meta.get("codeVersion")

            fault = ""
            if not isinstance(actual_offset, int) or actual_offset != offset:
                fault = f"Unexpected source offset at {offset}"
            elif isinstance(advertised_next, int) and advertised_next > offset and advertised_next != expected_next:
                fault = f"Source nextOffset disagrees with returned text length at {offset}"
            elif chunk_total is not None and total is not None and chunk_total != total:
                fault = f"Source length changed during retrieval at {offset}"
            elif (returned_id is not None and code_id
                  and str(returned_id).isdigit() and str(returned_id) != code_id):
                fault = f"Source identity changed during retrieval at {offset}"
            elif version is not None and chunk_version is not None and str(chunk_version) != str(version):
                fault = f"Source version changed during retrieval at {offset}"
            elif chunk_total is not None and expected_next > chunk_total:
                fault = f"Returned source extends beyond declared length at {offset}"
            if fault:
                incomplete_reason = fault
                self._record(gateway, operation, leaf_args, began, False, fault)
                if operation == "hub_get_source" and chunk_size > 8000:
                    chunk_size = 16000 if chunk_size > 16000 else 8000
                    retries += 1
                    continue
                break

            if len(body) + len(chunk) > MAX_CHARS:
                incomplete_reason = "Source exceeds bounded retrieval allowance"
                self._record(gateway, operation, leaf_args, began, False,
                             incomplete_reason)
                break
            body += chunk
            offset = expected_next
            if chunk_total is not None:
                total = chunk_total
            if chunk_version is not None:
                version = chunk_version
            self._record(gateway, operation, leaf_args, began, True,
                         f"Verified source chars {actual_offset}..{expected_next}")
            if total is not None and offset == total:
                break
            if total is not None and offset > total:
                incomplete_reason = "Received more source text than declared total"
                break
            if not meta.get("hasMore", True) and total is None:
                break
        else:
            incomplete_reason = "Reached bounded source-read call limit"

        if not body:
            return GroovySourceReport(
                title + f"\n- Verified source operation: {operation} via {gateway}."
                + (f"\n- Verified code ID: {code_id}." if code_id else
                   "\n- Attempted instance-ID read; code ID not verified.")
                + "\n- No raw Groovy source returned. Cannot verify the "
                  "defaultValue declaration, getter, stored lockout expiry or "
                  "updated()/initialize() behaviour."
            )
        complete = total is not None and offset == total and len(body) == total
        lines = [
            title, f"- Source reader: {operation} via {gateway}.",
            f"- Source text retrieved: {len(body)} characters; "
            + ("complete by declared length." if complete else
               "full source coverage unverified."),
            f"- Retrieved text SHA-256: {hashlib.sha256(body.encode()).hexdigest()}.",
            f"- Verified contiguous range: 0..{offset}"
            + (f" / {total} characters." if total is not None else " (total unknown)."),
            f"- Smaller-page recovery attempts: {retries}.",
        ]
        if incomplete_reason and not complete:
            lines.append(f"- Retrieval limitation: {incomplete_reason}.")
        if code_id:
            lines.append(f"- Verified code ID: {code_id}.")
        if version is not None:
            lines.append(f"- Source version: {str(version)[:32]}.")
        excerpts, found_symbols = _excerpts(body, symbols)
        requested_symbols = _validated_symbols(symbols)
        lines.append("- Matched symbols: " + (", ".join(found_symbols) if found_symbols else "none in retrieved text") + ".")
        missing_symbols = [name for name in requested_symbols if name not in found_symbols]
        if missing_symbols:
            lines.append("- Symbols not located in retrieved text: " + ", ".join(missing_symbols) + ".")
        if excerpts:
            lines.append("Source excerpts (retrieved-text-relative line numbers):")
            lines.extend(excerpts)
        else:
            lines.append("No requested code symbols found in retrieved source text.")
        if not complete:
            lines.append("Do not assert that a function is absent or a state write "
                         "never occurs without complete implementation coverage.")
        return GroovySourceReport("\n\n".join(lines), True, complete)


__all__ = ["requested_groovy_app_id", "source_code_id",
           "GroovySourceReport", "GroovySourceService"]

"""Narrow source projections for V2 read-only MCP execution.

Never pass raw MCP output, textual tool summaries or credentials to a model.
Every returned receipt is an allowlisted host projection. This deliberately
supports a small number of reviewed source operations; other reads still count
toward coverage but produce no invented evidence. No writes are possible here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

from mcp_client import MCPToolResult, tool_succeeded
from existing_rule_settings_evidence import project_installed_app_settings
from .temporal_scope import IncidentWindow

_ID = re.compile(r"^[0-9]{1,20}$")
_EVENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9:_-]{0,79}$")
_SHORT_VALUE = re.compile(r"^[A-Za-z0-9 _.,:;@+/-]{0,80}$")
_MAX_ROWS = 120


def _id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    candidate = str(value).strip()
    return candidate if _ID.fullmatch(candidate) else None


def _timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    return value.strip() if dt.tzinfo is not None and dt.utcoffset() is not None else None


def _event_rows(raw_rows: Any, requested_id: str) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(raw_rows, list):
        return [], 0
    result: list[dict[str, Any]] = []
    for row in raw_rows[:_MAX_ROWS]:
        if not isinstance(row, dict):
            continue
        if (event_id := _id(row.get("deviceId"))) and event_id != requested_id:
            continue
        if "deviceId" in row and not _id(row.get("deviceId")):
            continue
        name = row.get("name") or row.get("eventName")
        stamp = _timestamp(row.get("date") or row.get("timestamp"))
        if not isinstance(name, str) or not _EVENT_NAME.fullmatch(name) or not stamp:
            continue
        event: dict[str, Any] = {"deviceId": requested_id, "name": name, "date": stamp}
        if name.startswith("command-") or row.get("type") == "command":
            event["type"] = "command"
        value = row.get("value")
        if type(value) in (int, float, bool) and abs(float(value)) < 1e15:
            event["value"] = value
        elif isinstance(value, str) and _SHORT_VALUE.fullmatch(value):
            event["value"] = value
        producer = row.get("producedBy")
        if isinstance(producer, dict) and (producer_id := _id(producer.get("id"))):
            # No producer labels, free-form summaries or triggered listeners.
            event["producedBy"] = {"id": producer_id}
        result.append(event)
    return result, len(raw_rows)


def project_read_receipt(
    name: str, arguments: Mapping[str, Any], result: MCPToolResult | None,
    *, source_request_id: str, read_at: str | None = None,
    incident_window: IncidentWindow | None = None,
) -> dict[str, Any]:
    """Build one guarded, auditable source receipt without copying raw payload.

    A successful response means a tool returned, not that source integrity,
    physical state, or a causal explanation was proved.
    """
    op = arguments.get("tool") if isinstance(arguments.get("tool"), str) else name
    args = arguments.get("args") if isinstance(arguments.get("args"), dict) else arguments
    permitted_args = {k: args[k] for k in ("deviceId", "appId", "attribute", "hoursBack",
                     "limit", "since", "until", "includeSettings")
                      if k in args and type(args[k]) in (str, int, float, bool)}
    receipt = {
        "tool": name, "sub_tool": op, "source_request_id": source_request_id,
        "arguments": {"tool": op, "args": permitted_args},
        "timestamp": read_at or datetime.now(timezone.utc).isoformat(),
        "success": bool(result is not None and tool_succeeded(result)),
        "mutates": False, "effect": "read", "evidence_kind": "v2_read_source",
        "details": {},
    }
    if not receipt["success"]:
        return receipt
    data = result.data
    if not isinstance(data, dict):
        return receipt
    if data.get("status") in ("pending", "in_progress"):
        receipt["success"] = False
        return receipt
    if op == "hub_list_device_events":
        target = _id(args.get("deviceId"))
        if not target or ("deviceId" in data and _id(data.get("deviceId")) != target):
            receipt["success"] = False
            return receipt
        rows, original_count = _event_rows(data.get("events"), target)
        if incident_window is not None:
            rows = [event for event in rows if incident_window.contains(event["date"])]
        if not isinstance(data.get("events"), list):
            return receipt
        details = {
            "deviceId": target, "events": rows,
            "sourceEventCount": original_count,
            "rowsOutsideRequestedWindowOrInvalid": original_count - len(rows),
            "requestedIncidentWindow": (incident_window.to_dict()
                                        if incident_window is not None else None),
            "observedEventsTruncated": bool(original_count > _MAX_ROWS),
        }
        for source_key in ("sourceCompleteToWindowStart", "sourceComplete",
                           "historySourceIntegrityVerified", "pageReachesStart"):
            if type(data.get(source_key)) is bool:
                details[source_key] = data[source_key]
        if type(data.get("truncated")) is bool:
            details["observedEventsTruncated"] |= data["truncated"]
        if isinstance(data.get("nextCursor"), str):
            details["nextCursor"] = data["nextCursor"][:160]
        receipt["details"] = details
        return receipt

    if op == "hub_get_app_config":
        app_id = _id(args.get("appId"))
        if not app_id:
            receipt["success"] = False
            return receipt
        projected = project_installed_app_settings(data, app_id)
        receipt["details"] = projected
        if projected["settingsReadable"] is True:
            receipt["evidence_kind"] = "typed_existing_rule_partial_settings"
        return receipt

    if op == "hub_get_logs":
        raw = data.get("logs")
        if not isinstance(raw, list):
            return receipt
        safe = []
        for item in raw[:_MAX_ROWS]:
            if not isinstance(item, dict):
                continue
            date = _timestamp(item.get("date") or item.get("timestamp"))
            if not date:
                continue  # Native timezone-naive logs are NOT guessed.
            safe.append({"name": "log", "date": date})
        receipt["details"] = {
            "logs": safe, "sourceEventCount": len(raw),
            "truncated": len(raw) > _MAX_ROWS or data.get("truncated") is True,
        }
        return receipt
    return receipt


__all__ = ["project_read_receipt"]

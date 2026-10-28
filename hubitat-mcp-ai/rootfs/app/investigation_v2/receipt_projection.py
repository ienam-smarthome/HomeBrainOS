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
_MAX_SCAN = 2000  # bound untrusted source pages before incident filtering

# Explicit projection contract. A generic read-only MCP operation is NOT
# necessarily useful evidence: without a reviewed typed projection it consumes
# planning budget but contributes no canonical observations. Keep this list
# aligned with project_read_receipt() and its adapters, not tool descriptions.
PROJECTED_V2_READ_OPERATIONS = frozenset({
    "hub_get_device", "hub_list_device_events", "hub_list_apps",
    "hub_list_rules", "hub_get_app_config", "hub_get_logs",
})
_CATALOG_LABEL = re.compile(r"^[\w][ \w.,:+()'’/\-–&]{0,100}$", re.UNICODE)
_PRIVATE_TERMS = ("password", "api_key", "apikey", "bearer", "token", "credential", "secret")



def _id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    candidate = str(value).strip()
    return candidate if _ID.fullmatch(candidate) else None


def _source_producer_id(raw: Any) -> str | None:
    """Hubitat command producer: typed ID or trusted relative app-link shape.

    The live event endpoint sometimes returns producedBy as a relative HTML
    anchor, not a dictionary. Extract *only* an anchored installed-app ID;
    never retain the HTML, arbitrary label, href, or triggered listeners.
    """
    if isinstance(raw, dict):
        candidates = [_id(raw.get(k)) for k in ("id", "appId", "deviceId")]
        values = {x for x in candidates if x}
        if len(values) != 1:
            return None
        kind = raw.get("type")
        if kind is not None and (not isinstance(kind, str)
                                or kind.casefold() not in ("app", "device", "hub", "automation")):
            return None
        return next(iter(values))
    if isinstance(raw, str) and len(raw) <= 650:
        match = re.search(
            r"""<a\b[^>]{0,300}\bhref\s*=\s*['"]/installedapp/configure/([0-9]{1,20})['"][^>]{0,300}>""",
            raw, re.IGNORECASE,
        )
        return _id(match.group(1)) if match else None
    return None


def _timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    return value.strip() if dt.tzinfo is not None and dt.utcoffset() is not None else None


def _event_rows(raw_rows: Any, requested_id: str, incident_window: IncidentWindow | None = None) -> tuple[list[dict[str, Any]], int, str | None, str | None, bool, dict[str, int]]:
    if not isinstance(raw_rows, list):
        return [], 0, None, None, False, {}
    result: list[dict[str, Any]] = []
    source_instants = []
    diagnostic_counts = {"wrong_target": 0, "invalid_device_id": 0,
                         "invalid_name_or_time": 0, "outside_incident": 0,
                         "retention_cap": 0}
    # Scan a bounded source page, filter by the user-authorized time window,
    # THEN cap retained incident observations. The inverse drops historical
    # evidence whenever unrelated recent rows fill the start of the page.
    for row in raw_rows[:_MAX_SCAN]:
        if not isinstance(row, dict):
            continue
        if (event_id := _id(row.get("deviceId"))) and event_id != requested_id:
            diagnostic_counts["wrong_target"] += 1
            continue
        if "deviceId" in row and not _id(row.get("deviceId")):
            diagnostic_counts["invalid_device_id"] += 1
            continue
        name = row.get("name") or row.get("eventName")
        stamp = _timestamp(row.get("date") or row.get("timestamp"))
        if not isinstance(name, str) or not _EVENT_NAME.fullmatch(name) or not stamp:
            diagnostic_counts["invalid_name_or_time"] += 1
            continue
        instant = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        source_instants.append(instant)
        if incident_window is not None and not incident_window.contains(stamp):
            diagnostic_counts["outside_incident"] += 1
            continue
        if len(result) >= _MAX_ROWS:
            diagnostic_counts["retention_cap"] += 1
            continue
        event: dict[str, Any] = {"deviceId": requested_id, "name": name, "date": stamp}
        if name.startswith("command-") or row.get("type") == "command":
            event["type"] = "command"
        value = row.get("value")
        if type(value) in (int, float, bool) and abs(float(value)) < 1e15:
            event["value"] = value
        elif isinstance(value, str) and _SHORT_VALUE.fullmatch(value):
            event["value"] = value
        producer_id = _source_producer_id(row.get("producedBy"))
        if producer_id:
            # No producer labels, free-form summaries or triggered listeners.
            event["producedBy"] = {"id": producer_id}
        result.append(event)
    oldest = min(source_instants).isoformat() if source_instants else None
    newest = max(source_instants).isoformat() if source_instants else None
    return (result, len(raw_rows), oldest, newest,
            len(raw_rows) > _MAX_SCAN, diagnostic_counts)


def _project_app_catalogue(data: Mapping[str, Any], operation: str) -> dict[str, Any]:
    """Conservative app identities for source-ID interpretation, not actions.

    Names from live hub inventory are metadata only. They are NEVER proof of
    what a rule did on the historic date, and no other settings or arbitrary
    log/source text enters the model.
    """
    source = data
    for _ in range(3):
        expected = ("apps", "installedApps") if operation == "hub_list_apps" else ("rules",)
        if any(isinstance(source.get(key), list) for key in expected):
            break
        inner = next((source.get(key) for key in ("data", "result", "output")
                      if isinstance(source.get(key), dict)), None)
        if inner is None:
            break
        source = inner
    names = ("apps", "installedApps") if operation == "hub_list_apps" else ("rules",)
    raw_rows = next((source[key] for key in names
                     if isinstance(source.get(key), list)), None)
    if raw_rows is None:
        return {"appCatalogReadable": False, "appIdentities": []}
    identity: dict[str, str] = {}
    conflicts: set[str] = set()
    for item in raw_rows[:300]:
        if not isinstance(item, dict):
            continue
        app_id = _id(item.get("id") or item.get("appId"))
        label = item.get("label") or item.get("name")
        if (app_id is None or not isinstance(label, str)
                or not _CATALOG_LABEL.fullmatch(label.strip())
                or any(word in label.casefold() for word in _PRIVATE_TERMS)):
            continue
        label = label.strip()
        if app_id in identity and identity[app_id] != label:
            conflicts.add(app_id)
        else:
            identity[app_id] = label
    return {
        "appCatalogReadable": True,
        "appIdentities": [
            {"id": app_id, "name": label}
            for app_id, label in sorted(identity.items(), key=lambda row: int(row[0]))
            if app_id not in conflicts
        ],
        "catalogRowsReturned": len(raw_rows),
        "catalogTruncated": len(raw_rows) > 300,
    }


# Allowlisted read-time device context; NEVER copy driver preferences,
# arbitrary attributes, credentials, IPs, URLs or free-form log messages.
_STATUS_FIELDS = frozenset({
    "switch", "healthStatus", "deviceHealth", "mqttStatus",
    "networkStatus", "lastSeen", "lastActivity", "lastMessage",
    "power", "energy", "battery", "level", "presence", "temperature",
    "humidity", "contact", "motion",
})


def _snapshot(data: Mapping[str, Any], target: str) -> dict[str, Any] | None:
    source: Mapping[str, Any] = data
    for key in ("device", "data", "result"):
        child = source.get(key)
        if isinstance(child, dict) and (not child.get("id") or _id(child.get("id")) == target):
            source = child
    reported = _id(source.get("id") or source.get("deviceId"))
    if reported and reported != target:
        return None
    fields: dict[str, Any] = {}
    containers = (source, source.get("attributes"), source.get("states"),
                  source.get("currentStates"))
    for obj in containers:
        pairs: list[tuple[Any, Any]]
        if isinstance(obj, dict):
            pairs = list(obj.items())
        elif isinstance(obj, list):
            pairs = [(entry.get("name") or entry.get("attribute"),
                      entry.get("currentValue", entry.get("value")))
                     for entry in obj if isinstance(entry, dict)]
        else:
            continue
        for key, value in pairs:
            if key not in _STATUS_FIELDS:
                continue
            if isinstance(value, str) and (
                _SHORT_VALUE.fullmatch(value) or _timestamp(value)
            ):
                fields[key] = value[:80]
            elif type(value) in (int, float, bool) and (
                not isinstance(value, float) or abs(value) < 1e12
            ):
                fields[key] = value
    return {"deviceId": target, "attributes": fields}


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
    if op == "hub_get_device":
        target = _id(args.get("deviceId"))
        if not target:
            receipt["success"] = False
            return receipt
        snapshot = _snapshot(data, target)
        if snapshot is None:
            receipt["success"] = False
            return receipt
        receipt["details"] = {"deviceId": target, "deviceSnapshot": snapshot}
        receipt["evidence_kind"] = "typed_current_device_snapshot"
        return receipt
    if op == "hub_list_device_events":
        target = _id(args.get("deviceId"))
        if not target or ("deviceId" in data and _id(data.get("deviceId")) != target):
            receipt["success"] = False
            return receipt
        rows, original_count, oldest, newest, scan_truncated, diagnostic_counts = _event_rows(
            data.get("events"), target, incident_window)
        if not isinstance(data.get("events"), list):
            return receipt
        details = {
            "deviceId": target, "events": rows,
            "sourceEventCount": original_count,
            "rowsOutsideRequestedWindowOrInvalid": original_count - len(rows),
            "sourceOldestReturnedUtc": oldest,
            "sourceNewestReturnedUtc": newest,
            "sourceScanTruncated": scan_truncated,
            "sourceProjectionDropCounts": diagnostic_counts,
            "requestedWindowReached": (
                (oldest <= incident_window.start_utc)
                if incident_window is not None and oldest is not None
                   and not scan_truncated else None),
            "requestedIncidentWindow": (incident_window.to_dict()
                                        if incident_window is not None else None),
            "observedEventsTruncated": bool(
                original_count > _MAX_ROWS or scan_truncated),
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

    if op in ("hub_list_apps", "hub_list_rules"):
        receipt["details"] = _project_app_catalogue(data, op)
        if receipt["details"].get("appCatalogReadable") is True:
            receipt["evidence_kind"] = "typed_app_identity_catalogue"
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

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from automation_status_service import AutomationStatusService
from device_state_summary import capability_names, device_attributes
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult, tool_succeeded


_ERROR_WORDS = re.compile(r"\b(?:error|exception|traceback|failed|failure|fatal)\b", re.I)
_WARNING_WORDS = re.compile(r"\b(?:warn|warning|degraded|retrying|timeout)\b", re.I)
_VOLATILE_LOG_TOKENS = re.compile(
    r"(?:\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b|"
    r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b|"
    r"\b\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\b|\b0x[0-9a-f]+\b|\b\d{5,}\b)",
    re.I,
)
_VOLATILE_LOG_FIELDS = re.compile(
    r"(?i)(\b(?:request|correlation|trace|event|device|app|job)[_-]?id\b\s*[:=]\s*)"
    r"(?:\"[^\"]+\"|'[^']+'|[a-z0-9_.:-]+)"
)
_ADB_TIMEOUT = re.compile(
    r"(?:(?:^|\s)dev\|(?:\d+|#)\|(?P<label>[^|]{2,80})\|)?"
    r".{0,180}?\b(?:firetv\s+shell\s+timeout|adb(?:\s+shell)?\s+timeout|"
    r"shell\s+(?:connection\s+)?timeout)\b",
    re.I,
)
_PASSIVE_CAPABILITIES = {
    "button",
    "pushablebutton",
    "holdablebutton",
    "doubletappablebutton",
    "motionsensor",
    "contactsensor",
    "presencesensor",
    "lock",
    "doorcontrol",
    "windowshade",
}
_PERIODIC_CAPABILITIES = {
    "temperaturemeasurement",
    "relativehumiditymeasurement",
    "powermeter",
    "energymeter",
    "voltagemeasurement",
    "currentmeter",
    "airquality",
    "carbondioxidemeasurement",
    "pressuremeasurement",
    "moisturemeasurement",
}
_PERIODIC_STATES = {
    "temperature",
    "humidity",
    "power",
    "energy",
    "voltage",
    "current",
    "airqualityindex",
    "carbondioxide",
    "pressure",
    "moisture",
}
_PASSIVE_LABEL = re.compile(
    r"\b(?:button|remote|scene|motion|contact|door|window|presence|occupancy|"
    r"fp1|fp2|fp300|lock|shade|blind)\b",
    re.I,
)
_ACTIVITY_KEYS = (
    "lastActivity",
    "lastEvent",
    "lastSeen",
    "lastCheckin",
    "lastCheckIn",
    "lastUpdated",
)
_TIMESTAMP_KEYS = ("timestamp", "time", "date", "datetime", "createdAt", "created_at")
_SUBSYSTEM_PATTERNS = (
    ("MQTT", re.compile(r"\b(?:mqtt|tasmota)\b", re.I)),
    ("Matter", re.compile(r"\bmatter\b", re.I)),
    ("Zigbee", re.compile(r"\bzigbee\b", re.I)),
    ("Z-Wave", re.compile(r"\bz[- ]?wave\b", re.I)),
    ("LAN", re.compile(r"\b(?:lan|http|tcp|wifi|wi-fi)\b", re.I)),
)
_OFFLINE_VALUES = {
    "offline",
    "unavailable",
    "dead",
    "disconnected",
    "not reachable",
    "unreachable",
    "failed",
}
_LOG_LEVEL_KEYS = ("level", "severity", "priority", "type")
_LOG_MESSAGE_KEYS = (
    "message",
    "msg",
    "description",
    "descriptionText",
    "text",
    "error",
)
_HEALTH_STATE_KEYS = (
    "healthStatus",
    "deviceStatus",
    "connectionStatus",
    "networkStatus",
    "DeviceWatch-DeviceStatus",
)
_BOOL_ONLINE_KEYS = ("online", "reachable", "connected")
_SNAPSHOT_SCHEMA_VERSION = 2


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _label(device: dict[str, Any]) -> str:
    return str(device.get("label") or device.get("name") or device.get("displayName") or "Unnamed device").strip()


def _device_id(device: dict[str, Any]) -> str:
    return str(device.get("id") or device.get("deviceId") or _label(device)).strip()


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _issue_id(category: str, key: str) -> str:
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()[:12]
    return f"{category}:{digest}"


def _issue(
    category: str,
    severity: str,
    title: str,
    detail: str,
    *,
    key: str | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    item = {
        "id": _issue_id(category, key or f"{title}|{detail}"),
        "category": category,
        "domain": _issue_domain(category),
        "severity": severity,
        "title": title,
        "detail": detail,
        **({"count": int(count)} if count is not None else {}),
    }
    item["priority"] = _issue_priority(item)
    return item


def _canonical_attributes(device: dict[str, Any]) -> dict[str, Any]:
    values = {**device, **device_attributes(device)}
    return {_normalized_key(key): value for key, value in values.items()}


def _first(values: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        normalized = _normalized_key(key)
        if normalized in values and values[normalized] not in (None, ""):
            return values[normalized]
    return None


def _false_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value is False
    return str(value or "").strip().casefold() in {"false", "0", "no", "off"}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        try:
            parsed = datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        text = str(value or "").strip()
        if not text or text.casefold() in {"never", "none", "null", "unknown", "n/a"}:
            return None
        candidate = text.replace("Z", "+00:00")
        if re.search(r"[+-]\d{4}$", candidate):
            candidate = f"{candidate[:-2]}:{candidate[-2:]}"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            parsed = None
            for pattern in (
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
            ):
                try:
                    parsed = datetime.strptime(text, pattern)
                    break
                except ValueError:
                    continue
            if parsed is None:
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _activity_value(device: dict[str, Any]) -> tuple[bool, Any, datetime | None]:
    values = _canonical_attributes(device)
    for key in _ACTIVITY_KEYS:
        normalized = _normalized_key(key)
        if key in device:
            raw = device.get(key)
            return True, raw, _parse_datetime(raw)
        if normalized in values:
            raw = values.get(normalized)
            return True, raw, _parse_datetime(raw)
    return False, None, None


def _age_hours(value: datetime, now: datetime) -> float:
    return max(0.0, (now.astimezone(timezone.utc) - value).total_seconds() / 3600)


def _format_age(hours: float) -> str:
    if hours < 1:
        return f"{max(1, round(hours * 60))}m"
    if hours < 48:
        return f"{hours:.1f}h".replace(".0h", "h")
    return f"{hours / 24:.1f}d".replace(".0d", "d")


def _device_profile(device: dict[str, Any]) -> str:
    capabilities = {_normalized_key(item) for item in capability_names(device)}
    values = _canonical_attributes(device)
    states = set(values)
    identity = " ".join(
        str(device.get(key) or "")
        for key in ("label", "name", "type", "deviceType", "driverName", "category")
    )
    active_periodic = {
        "powermeter",
        "energymeter",
        "voltagemeasurement",
        "currentmeter",
    }
    networked = bool(re.search(r"\b(?:mqtt|tasmota|lan|http|tcp)\b", identity, re.I))
    battery_powered = (
        "battery" in capabilities
        or _safe_float(values.get("battery")) is not None
    )
    if battery_powered and not (capabilities & active_periodic) and not networked:
        return "passive"
    if capabilities & _PERIODIC_CAPABILITIES or states & _PERIODIC_STATES:
        return "periodic"
    if capabilities & _PASSIVE_CAPABILITIES or _PASSIVE_LABEL.search(identity):
        return "passive"
    return "unknown"


def _device_subsystem(device: dict[str, Any]) -> str | None:
    identity = " ".join(
        str(device.get(key) or "")
        for key in (
            "label",
            "name",
            "type",
            "deviceType",
            "driverName",
            "networkType",
            "protocol",
            "integration",
        )
    )
    for name, pattern in _SUBSYSTEM_PATTERNS:
        if pattern.search(identity):
            return name
    return None


def _stale_clusters(
    rows: list[dict[str, Any]],
    *,
    cluster_minutes: int,
) -> list[dict[str, Any]]:
    by_subsystem: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        subsystem = row.get("subsystem")
        if subsystem and isinstance(row.get("last_activity_at"), datetime):
            by_subsystem.setdefault(str(subsystem), []).append(row)

    clusters: list[dict[str, Any]] = []
    span_seconds = max(1, int(cluster_minutes)) * 60
    for subsystem, candidates in by_subsystem.items():
        candidates.sort(key=lambda item: item["last_activity_at"])
        pending: list[dict[str, Any]] = []
        for row in candidates:
            if pending and (
                row["last_activity_at"] - pending[0]["last_activity_at"]
            ).total_seconds() > span_seconds:
                if len(pending) >= 3:
                    clusters.append({"subsystem": subsystem, "members": list(pending)})
                pending = []
            pending.append(row)
        if len(pending) >= 3:
            clusters.append({"subsystem": subsystem, "members": list(pending)})
    return clusters


def _issue_domain(category: str) -> str:
    if category.startswith("device-"):
        return "devices"
    if category.startswith("automation"):
        return "automations"
    if category.startswith("log-"):
        return "logs"
    return "hub"


def _issue_priority(item: dict[str, Any]) -> int:
    category = str(item.get("category") or "")
    priorities = {
        "hub": 0,
        "device-stale-cluster": 10,
        "device-offline": 20,
        "device-motion-active": 25,
        "automation": 30,
        "device-long-stale": 32,
        "device-stale": 35,
        "device-battery": 40,
        "log-error": 50,
        "log-warning": 60,
    }
    return priorities.get(category, 80)


def _hub_device_summary(devices: list[dict[str, Any]]) -> dict[str, Any]:
    hub = next(
        (
            item
            for item in devices
            if "hub info" in str(item.get("label") or item.get("name") or "").casefold()
        ),
        None,
    )
    if not isinstance(hub, dict):
        return {}
    values = _canonical_attributes(hub)
    return {
        "label": _label(hub),
        "model": _first(values, ("hubModel", "model")),
        "firmware_version": _first(values, ("firmwareVersionString", "firmwareVersion")),
        "update_status": _first(values, ("hubUpdateStatus", "updateStatus")),
        "update_version": _first(values, ("hubUpdateVersion", "availableVersion")),
        "cpu_percent": _first(values, ("cpuPct", "cpu15Pct", "loadPct")),
        "free_memory": _first(values, ("freeMemory", "freeMem15")),
        "temperature": _first(values, ("internalTemp", "temperature")),
        "uptime": _first(values, ("formattedUptime", "uptime")),
        "database_size": _first(values, ("dbSize", "databaseSize")),
        "matter_status": _first(values, ("matterStatus",)),
    }


def _device_findings(
    devices: list[dict[str, Any]],
    *,
    low_battery_threshold: int,
    stale_hours: int = 24,
    long_stale_hours: int = 24 * 7,
    cluster_minutes: int = 15,
    motion_active_hours: int = 2,
    previously_stale_ids: set[str] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    low_batteries: list[dict[str, Any]] = []
    offline: list[dict[str, Any]] = []
    suspicious_stale: list[dict[str, Any]] = []
    stale_candidates: list[dict[str, Any]] = []
    long_term_stale: list[dict[str, Any]] = []
    passive_quiet: list[dict[str, Any]] = []
    never_reported: list[dict[str, Any]] = []
    motion_active_too_long: list[dict[str, Any]] = []
    occupied_long: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for device in devices:
        label = _label(device)
        identifier = _device_id(device)
        values = _canonical_attributes(device)

        battery = _safe_float(_first(values, ("battery",)))
        if battery is not None and battery <= low_battery_threshold:
            row = {
                "id": identifier,
                "label": label,
                "battery": round(battery, 1),
            }
            low_batteries.append(row)
            issues.append(
                _issue(
                    "device-battery",
                    "warning",
                    f"Low battery: {label}",
                    f"{battery:g}% (threshold {low_battery_threshold}%).",
                    key=identifier,
                )
            )

        state = _first(values, _HEALTH_STATE_KEYS)
        online_flag = _first(values, _BOOL_ONLINE_KEYS)
        state_text = str(state or "").strip().casefold()
        explicitly_offline = state_text in _OFFLINE_VALUES
        explicitly_unreachable = online_flag is not None and _false_like(online_flag)
        if explicitly_offline or explicitly_unreachable:
            reason = str(state or "not reachable").strip()
            row = {
                "id": identifier,
                "label": label,
                "state": reason,
            }
            offline.append(row)
            issues.append(
                _issue(
                    "device-offline",
                    "warning",
                    f"Device unavailable: {label}",
                    reason or "Device reports unavailable/offline.",
                    key=identifier,
                )
            )
            continue

        has_activity_field, raw_activity, activity_at = _activity_value(device)
        profile = _device_profile(device)
        subsystem = _device_subsystem(device)
        if has_activity_field and activity_at is None:
            row = {
                "id": identifier,
                "label": label,
                "profile": profile,
                "last_activity": raw_activity,
            }
            never_reported.append(row)
            continue
        if activity_at is None:
            continue

        age = _age_hours(activity_at, checked_at)
        activity_row = {
            "id": identifier,
            "label": label,
            "profile": profile,
            "subsystem": subsystem,
            "last_activity": activity_at.isoformat(),
            "last_activity_at": activity_at,
            "age_hours": round(age, 2),
        }
        motion = str(_first(values, ("motion",)) or "").strip().casefold()
        occupancy = str(
            _first(values, ("presence", "occupancy")) or ""
        ).strip().casefold()
        if motion == "active" and age >= motion_active_hours:
            motion_active_too_long.append(dict(activity_row))
            issues.append(
                _issue(
                    "device-motion-active",
                    "warning",
                    f"Motion active too long: {label}",
                    f"Motion remains active; last activity was {_format_age(age)} ago.",
                    key=identifier,
                )
            )
            continue
        if occupancy in {"present", "occupied", "active"} and age >= stale_hours:
            occupied_long.append(dict(activity_row))
            passive_quiet.append(dict(activity_row))
            continue
        if age < stale_hours:
            continue
        if profile == "periodic" and not (explicitly_offline or explicitly_unreachable):
            if age >= long_stale_hours:
                long_term_stale.append(dict(activity_row))
            elif (
                previously_stale_ids is not None
                and identifier not in previously_stale_ids
            ):
                stale_candidates.append(dict(activity_row))
            else:
                suspicious_stale.append(dict(activity_row))
        else:
            passive_quiet.append(dict(activity_row))

    clusters = _stale_clusters(
        suspicious_stale,
        cluster_minutes=cluster_minutes,
    )
    clustered_ids: set[str] = set()
    cluster_rows: list[dict[str, Any]] = []
    for cluster in clusters:
        members = list(cluster["members"])
        labels = sorted(str(item["label"]) for item in members)
        first = min(item["last_activity_at"] for item in members)
        last = max(item["last_activity_at"] for item in members)
        identifiers = {str(item["id"]) for item in members}
        clustered_ids.update(identifiers)
        subsystem = str(cluster["subsystem"])
        row = {
            "subsystem": subsystem,
            "count": len(members),
            "device_ids": sorted(identifiers),
            "devices": labels,
            "first_stopped": first.isoformat(),
            "last_stopped": last.isoformat(),
        }
        cluster_rows.append(row)
        issues.append(
            _issue(
                "device-stale-cluster",
                "warning",
                f"Possible {subsystem} interruption",
                f"{len(members)} devices stopped reporting within "
                f"{cluster_minutes} minutes: {', '.join(labels)}.",
                key=f"{subsystem}:{','.join(sorted(identifiers))}",
                count=len(members),
            )
        )

    for row in suspicious_stale:
        if str(row["id"]) in clustered_ids:
            continue
        issues.append(
            _issue(
                "device-stale",
                "warning",
                f"Telemetry stale: {row['label']}",
                f"Periodic telemetry last reported {_format_age(float(row['age_hours']))} ago.",
                key=str(row["id"]),
            )
        )

    for row in long_term_stale:
        issues.append(
            _issue(
                "device-long-stale",
                "warning",
                f"Long-term stale: {row['label']}",
                f"No periodic telemetry for {_format_age(float(row['age_hours']))}; "
                "the device may be unused, disconnected, or obsolete.",
                key=str(row["id"]),
            )
        )

    low_batteries.sort(key=lambda row: (row["battery"], row["label"].casefold()))
    offline.sort(key=lambda row: row["label"].casefold())
    for rows in (
        suspicious_stale,
        stale_candidates,
        long_term_stale,
        passive_quiet,
        never_reported,
        motion_active_too_long,
        occupied_long,
    ):
        rows.sort(key=lambda row: str(row["label"]).casefold())
        for row in rows:
            row.pop("last_activity_at", None)
    cluster_rows.sort(key=lambda row: (row["subsystem"], row["first_stopped"]))
    return {
        "total": len(devices),
        "low_battery_count": len(low_batteries),
        "offline_count": len(offline),
        "suspicious_stale_count": len(suspicious_stale),
        "stale_candidate_count": len(stale_candidates),
        "long_term_stale_count": len(long_term_stale),
        "passive_quiet_count": len(passive_quiet),
        "never_reported_count": len(never_reported),
        "motion_active_too_long_count": len(motion_active_too_long),
        "occupied_long_count": len(occupied_long),
        "stale_cluster_count": len(cluster_rows),
        "low_batteries": low_batteries,
        "offline": offline,
        "suspicious_stale": suspicious_stale,
        "stale_candidates": stale_candidates,
        "long_term_stale": long_term_stale,
        "passive_quiet": passive_quiet,
        "never_reported": never_reported,
        "motion_active_too_long": motion_active_too_long,
        "occupied_long": occupied_long,
        "stale_clusters": cluster_rows,
    }, issues


def _tool_map(tools: list[MCPTool]) -> dict[str, MCPTool]:
    return {str(tool.name): tool for tool in tools}


def _gateway_arguments(tool: MCPTool, operation: str, args: dict[str, Any]) -> dict[str, Any]:
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    properties = schema.get("properties")
    if isinstance(properties, dict) and "tool" in properties:
        return {"tool": operation, "args": args}
    if isinstance(properties, dict) and "args" in properties:
        return {"args": {"tool": operation, "args": args}}
    return {"tool": operation, "args": args}


def _looks_like_log_row(row: dict[str, Any]) -> bool:
    keys = {_normalized_key(key) for key in row}
    return bool(
        keys
        & {
            "level",
            "severity",
            "priority",
            "type",
            "message",
            "msg",
            "description",
            "descriptiontext",
            "text",
            "error",
        }
    )


def _log_lists(value: Any) -> list[list[dict[str, Any]]]:
    found: list[list[dict[str, Any]]] = []
    if isinstance(value, list):
        rows = [row for row in value if isinstance(row, dict) and _looks_like_log_row(row)]
        if rows:
            found.append(rows)
        for child in value:
            found.extend(_log_lists(child))
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(_log_lists(child))
    return found


def _log_rows(result: MCPToolResult) -> list[dict[str, Any]]:
    candidates = _log_lists(result.data)
    if not candidates:
        return []
    return max(candidates, key=len)


def _log_level(row: dict[str, Any]) -> str:
    values = {_normalized_key(key): value for key, value in row.items()}
    explicit = str(_first(values, _LOG_LEVEL_KEYS) or "").strip().casefold()
    if any(token in explicit for token in ("error", "fatal", "severe")):
        return "error"
    if any(token in explicit for token in ("warn", "warning")):
        return "warning"

    message = _log_message(row)
    if _ERROR_WORDS.search(message):
        return "error"
    if _WARNING_WORDS.search(message):
        return "warning"
    return "info"


def _log_message(row: dict[str, Any]) -> str:
    values = {_normalized_key(key): value for key, value in row.items()}
    for key in _LOG_MESSAGE_KEYS:
        value = values.get(_normalized_key(key))
        if value not in (None, ""):
            return " ".join(str(value).split())
    return " ".join(str(row).split())


def _log_group_key(message: str) -> str:
    adb_timeout = _ADB_TIMEOUT.search(str(message or ""))
    if adb_timeout:
        label = " ".join(str(adb_timeout.group("label") or "ADB device").split())
        return f"adb|{label.casefold()}|shell connection timed out"
    normalized = str(message or "").casefold()
    normalized = _VOLATILE_LOG_FIELDS.sub(r"\1#", normalized)
    normalized = _VOLATILE_LOG_TOKENS.sub("#", normalized)
    if "mcp rule server" in normalized and (
        "vrb" in normalized or "visual rule builder" in normalized
    ) and ("missing" in normalized or "omitted" in normalized):
        counts = re.search(r"\b(\d+)\s*(?:/|of)\s*(\d+)\b", normalized)
        if counts:
            return (
                "mcp rule server|vrb feed missing "
                f"{counts.group(1)}/{counts.group(2)} devices"
            )
        missing = re.search(r"\b(?:missing|omitted)\s+(\d+)\s+devices?\b", normalized)
        return (
            "mcp rule server|vrb feed missing "
            f"{missing.group(1) if missing else '#'} devices"
        )
    return " ".join(normalized.split())[:320]


def _log_source(row: dict[str, Any], message: str) -> str | None:
    values = {_normalized_key(key): value for key, value in row.items()}
    for key in ("appName", "source", "logger", "component", "name"):
        value = values.get(_normalized_key(key))
        if value not in (None, ""):
            return " ".join(str(value).split())[:120]
    lowered = message.casefold()
    if "mcp rule server" in lowered:
        return "MCP Rule Server"
    adb_timeout = _ADB_TIMEOUT.search(message)
    if adb_timeout and adb_timeout.group("label"):
        return " ".join(adb_timeout.group("label").split())[:120]
    for separator in (" — ", " - ", ": "):
        if separator in message:
            candidate = message.split(separator, 1)[0].strip()
            if 2 <= len(candidate) <= 80:
                return candidate
    return None


def _log_timestamp(row: dict[str, Any]) -> datetime | None:
    values = {_normalized_key(key): value for key, value in row.items()}
    for key in _TIMESTAMP_KEYS:
        value = values.get(_normalized_key(key))
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _log_summary(message: str, fingerprint: str) -> str:
    if fingerprint.startswith("mcp rule server|vrb feed missing "):
        summary = fingerprint.split("|", 1)[1]
        return f"VRB{summary[3:]}."
    if fingerprint.startswith("adb|") and fingerprint.endswith(
        "|shell connection timed out"
    ):
        return "ADB shell connection timed out; the retained TCP shell channel was closed."
    summary = _VOLATILE_LOG_FIELDS.sub(r"\1#", str(message or ""))
    summary = _VOLATILE_LOG_TOKENS.sub("#", summary)
    return " ".join(summary.split())[:500]


def _previous_stale_ids(previous: dict[str, Any] | None) -> set[str]:
    devices = (previous or {}).get("sections", {}).get("devices", {})
    if not isinstance(devices, dict):
        return set()
    identifiers: set[str] = set()
    for field in ("suspicious_stale", "stale_candidates", "long_term_stale"):
        rows = devices.get(field, [])
        if not isinstance(rows, list):
            continue
        identifiers.update(
            str(row.get("id"))
            for row in rows
            if isinstance(row, dict) and row.get("id") not in (None, "")
        )
    return identifiers


def _log_findings(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        level = _log_level(row)
        if level not in {"error", "warning"}:
            continue
        message = _log_message(row)
        fingerprint = _log_group_key(message)
        key = (level, fingerprint)
        timestamp = _log_timestamp(row)
        source = _log_source(row, message)
        group = groups.setdefault(
            key,
            {
                "level": level,
                "message": message[:500],
                "summary": _log_summary(message, fingerprint),
                "fingerprint": fingerprint,
                "source": source,
                "count": 0,
                "first_seen": timestamp,
                "last_seen": timestamp,
            },
        )
        group["count"] += 1
        if group.get("source") is None and source:
            group["source"] = source
        if timestamp is not None:
            first_seen = group.get("first_seen")
            last_seen = group.get("last_seen")
            group["first_seen"] = min(first_seen, timestamp) if first_seen else timestamp
            group["last_seen"] = max(last_seen, timestamp) if last_seen else timestamp

    for group in groups.values():
        for field in ("first_seen", "last_seen"):
            value = group.get(field)
            group[field] = value.isoformat() if isinstance(value, datetime) else None

    ordered = sorted(
        groups.values(),
        key=lambda item: (
            0 if item["level"] == "error" else 1,
            -int(item["count"]),
            item["message"].casefold(),
        ),
    )
    errors = [row for row in ordered if row["level"] == "error"]
    warnings = [row for row in ordered if row["level"] == "warning"]
    issues: list[dict[str, Any]] = []
    for row in ordered[:20]:
        severity = "warning"
        title = str(
            row.get("source")
            or ("Hub log error" if row["level"] == "error" else "Hub log warning")
        )
        issues.append(
            _issue(
                f"log-{row['level']}",
                severity,
                title,
                str(row["summary"]),
                key=str(row["fingerprint"]),
                count=int(row["count"]),
            )
        )
    return {
        "entries_checked": len(rows),
        "error_groups": errors[:10],
        "warning_groups": warnings[:10],
        "error_group_count": len(errors),
        "warning_group_count": len(warnings),
    }, issues


class HealthAuditService:
    """Deterministic read-only health audit shared by schedule and dashboard."""

    def __init__(
        self,
        mcp: HubitatMCPClient,
        automation_status: AutomationStatusService,
        *,
        snapshot_path: Path,
        low_battery_threshold: int = 20,
        log_hours: int = 24,
        stale_hours: int = 24,
        long_stale_hours: int = 24 * 7,
        cluster_minutes: int = 15,
        motion_active_hours: int = 2,
        now_factory=_utc_now,
    ) -> None:
        self.mcp = mcp
        self.automation_status = automation_status
        self.snapshot_path = Path(snapshot_path)
        self.low_battery_threshold = max(1, min(100, int(low_battery_threshold)))
        self.log_hours = max(1, min(168, int(log_hours)))
        self.stale_hours = max(1, min(24 * 30, int(stale_hours)))
        self.long_stale_hours = max(
            self.stale_hours + 1,
            min(24 * 365, int(long_stale_hours)),
        )
        self.cluster_minutes = max(1, min(120, int(cluster_minutes)))
        self.motion_active_hours = max(1, min(24, int(motion_active_hours)))
        self._now = now_factory
        self._lock = asyncio.Lock()

    def latest(self) -> dict[str, Any] | None:
        try:
            if not self.snapshot_path.exists():
                return None
            data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            latest = data.get("latest") if isinstance(data, dict) else None
            return latest if isinstance(latest, dict) else None
        except Exception:
            return None

    def previous(self) -> dict[str, Any] | None:
        try:
            if not self.snapshot_path.exists():
                return None
            data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            previous = data.get("previous") if isinstance(data, dict) else None
            return previous if isinstance(previous, dict) else None
        except Exception:
            return None

    def _persist(self, latest: dict[str, Any], previous: dict[str, Any] | None) -> None:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _SNAPSHOT_SCHEMA_VERSION,
            "latest": latest,
            "previous": previous,
        }
        temp = self.snapshot_path.with_suffix(self.snapshot_path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temp.replace(self.snapshot_path)

    async def _logs(
        self,
        tools: dict[str, MCPTool],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        tool = tools.get("hub_read_diagnostics")
        if tool is None:
            return {
                "available": False,
                "checked_hours": self.log_hours,
                "reason": "hub_read_diagnostics is not installed",
            }, [
                _issue(
                    "log-audit-gap",
                    "warning",
                    "Log audit unavailable",
                    "The MCP server does not expose hub_read_diagnostics.",
                    key="hub_read_diagnostics",
                )
            ]

        arguments = _gateway_arguments(
            tool,
            "hub_get_logs",
            {
                "since": f"{self.log_hours}h",
                "limit": 200,
            },
        )
        started = time.monotonic()
        try:
            result = await self.mcp.call_tool("hub_read_diagnostics", arguments)
        except Exception as exc:
            return {
                "available": False,
                "checked_hours": self.log_hours,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            }, [
                _issue(
                    "log-audit-gap",
                    "warning",
                    "Log audit failed",
                    f"{type(exc).__name__}: {str(exc)[:240]}",
                    key="hub_read_diagnostics",
                )
            ]

        elapsed_ms = round((time.monotonic() - started) * 1000)
        if not tool_succeeded(result):
            detail = str(result.text or "Hub log read failed")[:300]
            return {
                "available": False,
                "checked_hours": self.log_hours,
                "elapsed_ms": elapsed_ms,
                "error": detail,
            }, [
                _issue(
                    "log-audit-gap",
                    "warning",
                    "Log audit failed",
                    detail,
                    key="hub_read_diagnostics",
                )
            ]

        rows = _log_rows(result)
        findings, issues = _log_findings(rows)
        findings.update({
            "available": True,
            "checked_hours": self.log_hours,
            "elapsed_ms": elapsed_ms,
        })
        return findings, issues

    async def run(self, *, reason: str = "manual") -> dict[str, Any]:
        async with self._lock:
            started = time.monotonic()
            checked_at = self._now()
            previous = self.latest()
            issues: list[dict[str, Any]] = []
            sections: dict[str, Any] = {}

            try:
                mcp_health = await self.mcp.health()
            except Exception as exc:
                mcp_health = {
                    "online": False,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            online = bool(mcp_health.get("online"))
            sections["mcp"] = dict(mcp_health)
            if not online:
                issues.append(
                    _issue(
                        "hub",
                        "critical",
                        "Hub/MCP unavailable",
                        str(mcp_health.get("error") or "Hubitat MCP did not report online."),
                        key="mcp-offline",
                    )
                )

            tools: list[MCPTool] = []
            tool_map: dict[str, MCPTool] = {}
            if online:
                try:
                    tools = list(await self.mcp.list_tools(refresh=True))
                    tool_map = _tool_map(tools)
                except Exception as exc:
                    issues.append(
                        _issue(
                            "mcp-tools",
                            "warning",
                            "MCP tool inventory failed",
                            f"{type(exc).__name__}: {str(exc)[:240]}",
                            key="tool-inventory",
                        )
                    )
            sections["mcp"]["tool_count"] = len(tools)

            devices: list[dict[str, Any]] = []
            if online:
                try:
                    devices = list(await self.mcp.get_cached_devices(refresh=True))
                    device_section, device_issues = _device_findings(
                        devices,
                        low_battery_threshold=self.low_battery_threshold,
                        stale_hours=self.stale_hours,
                        long_stale_hours=self.long_stale_hours,
                        cluster_minutes=self.cluster_minutes,
                        motion_active_hours=self.motion_active_hours,
                        previously_stale_ids=_previous_stale_ids(previous),
                        now=checked_at,
                    )
                    sections["devices"] = device_section
                    issues.extend(device_issues)
                except Exception as exc:
                    sections["devices"] = {
                        "available": False,
                        "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }
                    issues.append(
                        _issue(
                            "device-audit-gap",
                            "warning",
                            "Device audit failed",
                            f"{type(exc).__name__}: {str(exc)[:240]}",
                            key="device-audit",
                        )
                    )
            else:
                sections["devices"] = {"available": False, "reason": "MCP offline"}

            hub = _hub_device_summary(devices)
            sections["hub"] = hub
            update_status = str(hub.get("update_status") or "").casefold()
            update_available = (
                ("available" in update_status or "update ready" in update_status)
                and not any(
                    phrase in update_status
                    for phrase in ("no update", "not available", "current", "up to date")
                )
            )
            if update_available:
                version = str(hub.get("update_version") or "").strip()
                issues.append(
                    _issue(
                        "hub-update",
                        "info",
                        "Hub firmware update available",
                        f"Available version {version}." if version else str(hub.get("update_status") or "Update available."),
                        key="hub-firmware-update",
                    )
                )

            if online:
                try:
                    automation = await self.automation_status.snapshot(advisory=False)
                    counts = dict(automation.automation_counts)
                    attention = [
                        item
                        for item in automation.automation_items
                        if str(item.get("status")) in {"broken", "paused", "unknown"}
                    ]
                    sections["automations"] = {
                        "total": len(automation.automation_items),
                        "counts": counts,
                        "attention_count": len(attention),
                        "disabled_count": int(counts.get("disabled") or 0),
                        "attention": attention,
                    }
                    for item in attention:
                        status = str(item.get("status") or "unknown")
                        name = str(item.get("display_name") or item.get("name") or "Unnamed automation")
                        identifier = str(item.get("id") or name)
                        reason_detail = str(item.get("status_reason") or "").strip()
                        detail = (
                            reason_detail
                            if reason_detail
                            else f"{item.get('type') or 'automation'} reports {status}."
                        )
                        issues.append(
                            _issue(
                                "automation",
                                "warning",
                                f"Automation {status}: {name}",
                                detail,
                                key=f"{item.get('type')}:{identifier}:{status}",
                            )
                        )
                except Exception as exc:
                    sections["automations"] = {
                        "available": False,
                        "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }
                    issues.append(
                        _issue(
                            "automation-audit-gap",
                            "warning",
                            "Automation audit failed",
                            f"{type(exc).__name__}: {str(exc)[:240]}",
                            key="automation-audit",
                        )
                    )
                log_section, log_issues = await self._logs(tool_map)
                sections["logs"] = log_section
                issues.extend(log_issues)
            else:
                sections["automations"] = {"available": False, "reason": "MCP offline"}
                sections["logs"] = {"available": False, "reason": "MCP offline"}

            severities = {"critical": 0, "warning": 0, "info": 0}
            for item in issues:
                severity = str(item.get("severity") or "info")
                if severity not in severities:
                    severity = "info"
                severities[severity] += 1

            status = (
                "critical"
                if severities["critical"]
                else "attention"
                if severities["warning"]
                else "healthy"
            )
            current_attention_ids = {
                str(item["id"])
                for item in issues
                if item.get("severity") in {"critical", "warning"}
            }
            previous_schema = int(
                _safe_float((previous or {}).get("snapshot_schema_version")) or 0
            )
            change_tracking_ready = (
                isinstance(previous, dict)
                and previous_schema == _SNAPSHOT_SCHEMA_VERSION
            )
            previous_attention = {
                str(item.get("id")): item
                for item in (
                    (previous or {}).get("issues", [])
                    if change_tracking_ready
                    else []
                )
                if isinstance(item, dict)
                and item.get("severity") in {"critical", "warning"}
                and item.get("id")
            }
            issues.sort(
                key=lambda item: (
                    {"critical": 0, "warning": 1, "info": 2}.get(
                        str(item.get("severity")), 3
                    ),
                    0 if int(item.get("priority", 80)) < 50 else 1,
                    0 if str(item.get("id")) not in previous_attention else 1,
                    int(item.get("priority", 80)),
                    1
                    if item.get("domain") == "logs" and int(item.get("count") or 1) > 1
                    else 0,
                    str(item.get("title") or "").casefold(),
                )
            )
            new_issues = [
                item
                for item in issues
                if item.get("severity") in {"critical", "warning"}
                and str(item.get("id")) not in previous_attention
            ] if change_tracking_ready else []
            resolved = [
                item
                for issue_id, item in previous_attention.items()
                if issue_id not in current_attention_ids
            ] if change_tracking_ready else []

            attention_count = severities["critical"] + severities["warning"]
            hierarchy: dict[str, dict[str, Any]] = {}
            domain_labels = {
                "hub": "Hub",
                "devices": "Devices",
                "automations": "Automations",
                "logs": "Logs",
            }
            domain_icons = {
                "healthy": "✅",
                "attention": "⚠️",
                "critical": "❌",
            }
            for domain, label in domain_labels.items():
                domain_issues = [
                    item
                    for item in issues
                    if item.get("domain") == domain
                    and item.get("severity") in {"critical", "warning"}
                ]
                domain_critical = sum(
                    item.get("severity") == "critical" for item in domain_issues
                )
                domain_status = (
                    "critical"
                    if domain_critical
                    else "attention"
                    if domain_issues
                    else "healthy"
                )
                hierarchy[domain] = {
                    "label": label,
                    "status": domain_status,
                    "icon": domain_icons[domain_status],
                    "attention_count": len(domain_issues),
                    "critical_count": domain_critical,
                }
            sections["summary"] = hierarchy

            hub_summary = hierarchy["hub"]
            hub_phrase = (
                f"Hub {str(hub_summary['status']).replace('attention', 'needs attention')}"
            )
            if status == "healthy":
                message = "System check: Healthy — Hub healthy; no items need attention."
            elif status == "critical":
                message = (
                    f"System check: Critical — {hub_phrase}; {attention_count} item"
                    f"{'s' if attention_count != 1 else ''} need attention."
                )
            else:
                affected = [
                    f"{value['label']} {value['attention_count']}"
                    for domain, value in hierarchy.items()
                    if domain != "hub" and value["attention_count"]
                ]
                breakdown = f" ({', '.join(affected)})" if affected else ""
                message = (
                    f"System check: Attention — {hub_phrase}; {attention_count} item"
                    f"{'s' if attention_count != 1 else ''} need attention{breakdown}."
                )

            result = {
                "snapshot_schema_version": _SNAPSHOT_SCHEMA_VERSION,
                "change_tracking_state": (
                    "compared"
                    if change_tracking_ready
                    else "baseline-reset"
                    if isinstance(previous, dict)
                    else "baseline-created"
                ),
                "status": status,
                "message": message,
                "reason": str(reason),
                "checked_at": checked_at.isoformat(),
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "severity_counts": severities,
                "attention_count": attention_count,
                "info_count": severities["info"],
                "new_count": len(new_issues),
                "resolved_count": len(resolved),
                "health_hierarchy": hierarchy,
                "new_issues": new_issues,
                "resolved_issues": resolved,
                "issues": issues,
                "sections": sections,
                "thresholds": {
                    "low_battery": self.low_battery_threshold,
                    "log_hours": self.log_hours,
                    "stale_hours": self.stale_hours,
                    "long_stale_hours": self.long_stale_hours,
                    "cluster_minutes": self.cluster_minutes,
                    "motion_active_hours": self.motion_active_hours,
                },
            }
            self._persist(result, previous)
            return result


__all__ = [
    "HealthAuditService",
    "_device_findings",
    "_gateway_arguments",
    "_log_findings",
    "_log_rows",
]

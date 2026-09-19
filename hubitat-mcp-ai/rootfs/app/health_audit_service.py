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
from device_state_summary import device_attributes
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult, tool_succeeded


_ERROR_WORDS = re.compile(r"\b(?:error|exception|traceback|failed|failure|fatal)\b", re.I)
_WARNING_WORDS = re.compile(r"\b(?:warn|warning|degraded|retrying|timeout)\b", re.I)
_VOLATILE_LOG_TOKENS = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?|"
    r"\d{1,2}:\d{2}:\d{2}(?:\.\d+)?|0x[0-9a-f]+|\d{4,})\b",
    re.I,
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
    return {
        "id": _issue_id(category, key or f"{title}|{detail}"),
        "category": category,
        "severity": severity,
        "title": title,
        "detail": detail,
        **({"count": int(count)} if count is not None else {}),
    }


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
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    low_batteries: list[dict[str, Any]] = []
    offline: list[dict[str, Any]] = []
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

    low_batteries.sort(key=lambda row: (row["battery"], row["label"].casefold()))
    offline.sort(key=lambda row: row["label"].casefold())
    return {
        "total": len(devices),
        "low_battery_count": len(low_batteries),
        "offline_count": len(offline),
        "low_batteries": low_batteries,
        "offline": offline,
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
    normalized = _VOLATILE_LOG_TOKENS.sub("#", str(message or "").casefold())
    return " ".join(normalized.split())[:320]


def _log_findings(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        level = _log_level(row)
        if level not in {"error", "warning"}:
            continue
        message = _log_message(row)
        key = (level, _log_group_key(message))
        group = groups.setdefault(
            key,
            {
                "level": level,
                "message": message[:500],
                "count": 0,
            },
        )
        group["count"] += 1

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
        title = "Hub log error" if row["level"] == "error" else "Hub log warning"
        issues.append(
            _issue(
                f"log-{row['level']}",
                severity,
                title,
                row["message"],
                key=_log_group_key(row["message"]),
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
        now_factory=_utc_now,
    ) -> None:
        self.mcp = mcp
        self.automation_status = automation_status
        self.snapshot_path = Path(snapshot_path)
        self.low_battery_threshold = max(1, min(100, int(low_battery_threshold)))
        self.log_hours = max(1, min(168, int(log_hours)))
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
                    "audit-gap",
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
                    "audit-gap",
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
                    "audit-gap",
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
                            "audit-gap",
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
                        issues.append(
                            _issue(
                                "automation",
                                "warning",
                                f"Automation {status}: {name}",
                                f"{item.get('type') or 'automation'} reports {status}.",
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
                            "audit-gap",
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
            previous_attention = {
                str(item.get("id")): item
                for item in (previous or {}).get("issues", [])
                if isinstance(item, dict)
                and item.get("severity") in {"critical", "warning"}
                and item.get("id")
            }
            new_issues = [
                item
                for item in issues
                if item.get("severity") in {"critical", "warning"}
                and str(item.get("id")) not in previous_attention
            ]
            resolved = [
                item
                for issue_id, item in previous_attention.items()
                if issue_id not in current_attention_ids
            ]

            attention_count = severities["critical"] + severities["warning"]
            if status == "healthy":
                message = "System check: Healthy — no items need attention."
            elif status == "critical":
                message = (
                    f"System check: Critical — {attention_count} item"
                    f"{'s' if attention_count != 1 else ''} need attention."
                )
            else:
                message = (
                    f"System check: Attention — {attention_count} item"
                    f"{'s' if attention_count != 1 else ''} need attention."
                )

            result = {
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
                "new_issues": new_issues,
                "resolved_issues": resolved,
                "issues": issues,
                "sections": sections,
                "thresholds": {
                    "low_battery": self.low_battery_threshold,
                    "log_hours": self.log_hours,
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

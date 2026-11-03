"""Bounded, value-level provenance for authoritative Hub Information Driver reads.

This projection is for offline Q1 source grading, not a health conclusion.
Only known non-private scalar fields leave the tool response in evidence receipts.
The model continues to receive the normal complete (location-redacted) tool result.
"""
from __future__ import annotations

import math
import re
from typing import Any

_VERSION = re.compile(r"\d{1,4}(?:\.\d{1,5}){1,5}")
_NUMBER = re.compile(r"[+-]?\d{1,8}(?:\.\d{1,5})?")
_UPTIME = re.compile(r"\d{1,6}d:\d{1,3}h:\d{1,3}m:\d{1,3}s")
_STATUS = frozenset({
    "online", "offline", "enabled", "disabled", "connected", "disconnected",
    "ok", "healthy", "unhealthy", "unknown", "true", "false", "up to date",
    "update available", "no update available", "no updates available",
    "checking", "not available", "none", "no alerts", "clear", "0",
})
_NUMERIC_FIELDS = frozenset({
    "cpu_5_min", "cpu_percent", "cpu_15_min", "cpu_15_percent",
    "free_memory", "free_memory_15_min", "temperature", "database_size",
})
_STATUS_FIELDS = frozenset({
    "update_status", "zigbee_status", "zwave_status",
    "matter_status", "zigbee_healthy", "zwave_healthy",
})
_UNITS = {
    "free_memory_unit": frozenset({"KB", "MB", "GB", "TB"}),
    "temperature_unit": frozenset({"°C", "°F", "C", "F"}),
    "database_size_unit": frozenset({"KB", "MB", "GB", "TB"}),
}


def _safe_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) and abs(value) <= 1e10 else None
    if not isinstance(value, str) or not _NUMBER.fullmatch(value.strip()):
        return None
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and abs(parsed) <= 1e10 else None


def hub_info_receipt_details(
    arguments: Any, data: Any,
) -> dict[str, Any] | None:
    """Source-returned allowlisted values, never guessed or filled with defaults.

    A successful function response is not proof the refreshed device was
    physically healthy, firmware up to date, or that the model saw a given
    input. A missing field is simply omitted, not a negative observation.
    """
    if not isinstance(arguments, dict) or not isinstance(data, dict):
        return None
    scope = arguments.get("scope")
    if (data.get("success") is not True
            or scope not in {"full", "firmware", "resources"}
            or data.get("scope") != scope):
        return None
    fields: dict[str, Any] = {}
    for name in _NUMERIC_FIELDS:
        number = _safe_number(data.get(name))
        if number is not None:
            fields[name] = number
    for name in ("installed_firmware", "available_firmware"):
        value = data.get(name)
        if isinstance(value, str) and _VERSION.fullmatch(value.strip()):
            fields[name] = value.strip()
    for name in _STATUS_FIELDS:
        value = data.get(name)
        if isinstance(value, bool):
            fields[name] = value
        elif isinstance(value, str) and value.strip().casefold() in _STATUS:
            fields[name] = value.strip().casefold()
    alerts = data.get("hub_alerts")
    if isinstance(alerts, str) and alerts.strip().casefold() in {
        "none", "no alerts", "clear", "0",
    }:
        fields["hub_alerts"] = alerts.strip().casefold()
    elif alerts == 0:
        fields["hub_alerts"] = 0
    uptime = data.get("uptime")
    if isinstance(uptime, str) and _UPTIME.fullmatch(uptime.strip()):
        fields["uptime"] = uptime.strip()
    for name, permitted in _UNITS.items():
        val = data.get(name)
        if isinstance(val, str) and val in permitted:
            fields[name] = val

    diagnostics: dict[str, Any] = {}
    # Instrumentation reflects *this* snapshot execution only. It is not
    # an estimate of external network latency or an assertion of freshness.
    for name in ("poll_read_count", "poll_sleep_ms", "refresh_command_count"):
        num = data.get(name)
        if type(num) is int and 0 <= num <= 60000:
            diagnostics[name] = num
    if type(data.get("firmware_status_settled")) is bool:
        diagnostics["firmware_status_settled"] = data["firmware_status_settled"]

    return {
        "sourceType": "hub_information_driver",
        "requestedScope": scope,
        "sourceScopeMatched": True,
        "reported": fields,
        "snapshotDiagnostics": diagnostics,
        "limitations": (
            "Typed driver-reported scalar fields only; no independently "
            "verified physical health, alert absence, firmware freshness, "
            "or source timestamp."
        ),
    }


__all__ = ["hub_info_receipt_details"]

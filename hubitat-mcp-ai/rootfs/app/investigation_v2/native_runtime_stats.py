"""Source-typed and privacy-safe projections of Hubitat Logs Device/App Stats.

The current upstream MCP operation is hub_get_logs(mode='devices'|'apps'),
not the retired hub_get_performance_stats. These cumulative snapshots
cannot establish CPU use at a previous warning timestamp.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .native_source_adapters import safe_string, unwrapped

_MODES = frozenset(("devices", "apps"))
_FIELDS = ("pct", "count", "total", "stateSize", "events")
_SUMMARY = {
    "devices": ("devicesUptime", "totalDevicesRuntime", "devicePct"),
    "apps": ("appsUptime", "totalAppsRuntime", "appPct"),
}


def _nonnegative_number(value: Any) -> int | float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0 or number > 1e15:
        return None
    return value


def project_log_runtime_stats(data: Any) -> dict[str, Any] | None:
    raw = unwrapped(data)
    mode = raw.get("mode")
    if not isinstance(mode, str) or mode not in _MODES:
        return None
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return {
            "mode": mode, "rows": [], "reported_rows": None,
            "source_complete": False, "stats_projection_unavailable": True,
            "interpretation_limit": (
                "No typed Logs-page performance rows returned; cannot "
                "infer that any device or app is idle or has low busy time."),
        }
    rows = []
    for entry in entries[:60]:
        if not isinstance(entry, Mapping):
            continue
        source_id = entry.get("id")
        if type(source_id) not in (int, str) or not str(source_id).isdecimal():
            continue
        if not 0 < int(source_id) < 10**16:
            continue
        item: dict[str, Any] = {"id": str(source_id)}
        if isinstance(entry.get("name"), str):
            item["name"] = safe_string(entry["name"], 90)
        for key in _FIELDS:
            value = _nonnegative_number(entry.get(key))
            if value is not None:
                item[key] = value
        if type(entry.get("largeState")) is bool:
            item["largeState"] = entry["largeState"]
        rows.append(item)
    raw_summary = raw.get("summary")
    summary = {}
    if isinstance(raw_summary, Mapping):
        for key in _SUMMARY[mode]:
            number = _nonnegative_number(raw_summary.get(key))
            if number is not None:
                summary[key] = number
    return {
        "mode": mode,
        "rows": rows[:40],
        "reported_rows": len(entries),
        "returned_rows": len(rows[:40]),
        "total_source_rows": (
            raw.get("total") if type(raw.get("total")) is int
            and 0 <= raw["total"] < 10**7 else None),
        "matched_source_rows": (
            raw.get("matched") if type(raw.get("matched")) is int
            and 0 <= raw["matched"] < 10**7 else None),
        "summary": summary,
        "source_complete": False,
        "stats_projection_unavailable": not bool(rows),
        "sample_limited": bool(
            len(entries) > 40 or
            isinstance(raw.get("nextCursor"), str) and raw["nextCursor"]),
        "interpretation_limit": (
            "Hubitat Logs-page performance stats at the time of this "
            "cumulative snapshot. pct is source-reported percentage busy, "
            "total is source-reported cumulative runtime, not a measured "
            "CPU contribution at an earlier warning timestamp. Stats may "
            "reset at reboot and the returned rows may be capped."),
    }


__all__ = ["project_log_runtime_stats"]

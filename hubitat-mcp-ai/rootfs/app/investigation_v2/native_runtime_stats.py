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




def verified_caller_app_ids(
    witnesses: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    focus_ids: set[str],
) -> set[str]:
    """Only target-scoped, source-attested command issuer IDs are callers."""
    callers: set[str] = set()
    if not focus_ids:
        return callers
    for receipt in witnesses[:16]:
        if receipt.get("operation") != "hub_list_device_events":
            continue
        filters = receipt.get("read_filters")
        source = receipt.get("source_data")
        if (not isinstance(filters, Mapping)
                or str(filters.get("deviceId")) not in focus_ids
                or not isinstance(source, Mapping)):
            continue
        for issuer in source.get("issuer_apps", [])[:16]:
            if isinstance(issuer, Mapping):
                app = str(issuer.get("appId") or "")
                if app.isdecimal():
                    callers.add(app)
    return callers


def focused_runtime_stat_receipts(
    witnesses: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    focus_ids: list[str] | set[str] | tuple[str, ...],
) -> list[dict[str, Any]]:
    """Select identity-matched device + attested-caller stats from ANY page.

    A broad app-stat page is eligible only for independently attested callers.
    A requested appId/deviceId must still agree with a row's returned ID;
    it is NEVER overruled by a matching row in an unrelated scoped response.
    """
    focus = {str(x) for x in focus_ids if str(x).isdecimal()}
    if not focus:
        return []
    callers = verified_caller_app_ids(list(witnesses), focus)
    result: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for receipt in witnesses[:16]:
        if (receipt.get("operation") != "hub_get_logs"
                or type(receipt.get("read")) is not int):
            continue
        filters = receipt.get("read_filters")
        source = receipt.get("source_data")
        if not isinstance(filters, Mapping) or not isinstance(source, Mapping):
            continue
        stats = source.get("runtime_stats")
        if not isinstance(stats, Mapping):
            continue
        mode = stats.get("mode")
        if mode == "devices":
            approved = focus
            field = "deviceId"
        elif mode == "apps":
            approved = callers
            field = "appId"
        else:
            continue
        requested = filters.get(field)
        requested = str(requested) if requested is not None else None
        rows = stats.get("rows")
        if not isinstance(rows, list):
            continue
        for row in rows[:40]:
            if not isinstance(row, Mapping):
                continue
            rid = str(row.get("id") or "")
            if (rid not in approved
                    or requested is not None and requested != rid):
                continue
            key = (receipt["read"], mode, rid)
            if key in seen:
                continue
            seen.add(key)
            entry = {
                "read": receipt["read"], "kind": mode, "id": rid,
                "name": safe_string(row.get("name") or "", 65),
                **{k: row[k] for k in ("pct", "count", "total", "stateSize")
                   if _nonnegative_number(row.get(k)) is not None},
                "scope_basis": ("target_device_source_row" if mode == "devices"
                                else "independently_attested_calling_app"),
                "incident_time_aligned": False,
                "snapshot_complete": False,
            }
            result.append(entry)
            if len(result) >= 16:
                return result
    return result


__all__ = ["project_log_runtime_stats", "verified_caller_app_ids",
           "focused_runtime_stat_receipts"]

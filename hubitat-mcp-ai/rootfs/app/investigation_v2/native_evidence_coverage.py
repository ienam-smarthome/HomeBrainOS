"""Evidence coverage measured against source windows, not successful tool counts.

A successful device-event read is not causal coverage when its newest-first
page is later than the actual slow-method warning. Parsed times are unzoned
wall-clock comparisons; cross-source clock alignment stays unverified.
This host layer suggests discriminating read filters. The model chooses tools.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Mapping, Sequence

_METHOD = re.compile(r"\bmethod\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.I)
_WALL = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?")


def _wall_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    found = _WALL.search(value[:55])
    if not found:
        return None
    try:
        day, clock, fractional = found.groups()
        return datetime.strptime(day + " " + clock, "%Y-%m-%d %H:%M:%S").replace(
            microsecond=int((fractional or "0").ljust(6, "0"))
        )
    except ValueError:
        return None


def _warning_ranges(witnesses: Sequence[Mapping[str, Any]],
                    focus: set[str]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    seen = set()
    for w in witnesses:
        if w.get("operation") != "hub_get_logs":
            continue
        data = w.get("source_data")
        summary = data.get("log_summary") if isinstance(data, dict) else None
        if not isinstance(summary, dict):
            continue
        for item in summary.get("warning_error_groups", [])[:30]:
            if not isinstance(item, dict) or str(item.get("source_id")) not in focus:
                continue
            oldest = _wall_time(item.get("oldest_returned"))
            newest = _wall_time(item.get("newest_returned"))
            if oldest is None or newest is None:
                continue
            if newest < oldest:
                oldest, newest = newest, oldest
            message = item.get("message", "")
            match = _METHOD.search(str(message))
            method = match.group(1) if match else None
            key = (oldest, newest, method)
            if key in seen:
                continue
            seen.add(key)
            groups.append({
                "start": oldest, "end": newest,
                "method": method, "read": w.get("read"),
                "start_text": item.get("oldest_returned"),
                "end_text": item.get("newest_returned"),
            })
    # Narrow, explicitly named method warnings are the best source-grounded
    # discriminator. Generic load warnings should not crowd them out.
    return sorted(groups, key=lambda x: (
        0 if x["method"] else 1,
        (x["end"] - x["start"]).total_seconds(),
        x["start"],
    ))


def _event_windows(witnesses: Sequence[Mapping[str, Any]],
                   focus: set[str]) -> list[dict[str, Any]]:
    windows = []
    for w in witnesses:
        if w.get("operation") != "hub_list_device_events":
            continue
        filters = w.get("read_filters")
        filters = filters if isinstance(filters, dict) else {}
        if str(filters.get("deviceId")) not in focus:
            continue
        data = w.get("source_data")
        if not isinstance(data, dict):
            continue
        events = data.get("events", [])
        times = sorted(t for t in (_wall_time(e.get("date") or e.get("time"))
                               for e in events if isinstance(e, dict)) if t)
        commands = [
            (e, _wall_time(e.get("date") or e.get("time")))
            for e in events if isinstance(e, dict)
            and str(e.get("name", "")).startswith("command-")
            and isinstance(e.get("producedBy"), dict)
            and e["producedBy"].get("appId")
        ]
        windows.append({
            "read": w.get("read"),
            "start": times[0] if times else None,
            "end": times[-1] if times else None,
            "command_times": [(e["name"], when) for e, when in commands if when],
            "count": len(events) if isinstance(events, list) else 0,
            "filters": filters,
        })
    return windows


def gap_for_target(witnesses: Sequence[Mapping[str, Any]],
                   focus_ids: Sequence[str],
                   *, can_read_events: bool) -> dict[str, Any] | None:
    if not focus_ids or not can_read_events:
        return None
    focus = {str(i) for i in focus_ids}
    warnings = _warning_ranges(witnesses, focus)
    if not warnings:
        return None
    events = _event_windows(witnesses, focus)
    # When there are many grouped warnings, a single intersecting command
    # observation is still not proof of ALL warning mechanisms. Prefer the
    # narrowest slow-method window with no verified calling app.
    chosen = None
    for warning in warnings:
        # Allow five minutes of uncertainty around the printed source clocks.
        expanded_start = warning["start"] - timedelta(minutes=5)
        expanded_end = warning["end"] + timedelta(minutes=5)
        matching_command = any(
            when is not None and expanded_start <= when <= expanded_end
            and (not warning["method"] or
                 name.casefold() == ("command-" + warning["method"]).casefold())
            for window in events
            for name, when in window["command_times"]
        )
        if not matching_command:
            chosen = warning
            break
    if chosen is None:
        return None
    expanded_start = chosen["start"] - timedelta(minutes=5)
    expanded_end = chosen["end"] + timedelta(minutes=5)
    overlaps = [
        window for window in events
        if window["start"] is not None and window["end"] is not None
        and window["start"] <= expanded_end and window["end"] >= expanded_start
    ]
    gap_kind = (
        "target_warning_actor_provenance_unchecked" if not events
        else ("target_warning_event_window_uncovered"
              if not overlaps else "target_warning_command_issuer_unverified")
    )
    return {
        "kind": gap_kind,
        "focus_ids": sorted(focus),
        "supporting_warning_reads": sorted({
            x["read"] for x in warnings
            if isinstance(x["read"], int)
        }),
        "method": chosen["method"],
        "warning_window": {
            "oldest": chosen["start_text"], "newest": chosen["end_text"],
            "timezone_verified": False,
        },
        "event_windows_checked": [{
            "read": w["read"],
            "oldest": w["start"].isoformat() if w["start"] else None,
            "newest": w["end"].isoformat() if w["end"] else None,
            "returned_events": w["count"],
            "filters": w["filters"],
        } for w in events[:5]],
        "candidate_read": "hub_list_device_events",
        "candidate_filters": {
            "deviceId": sorted(focus)[0],
            "hoursBack": 48,
            "limit": 50,
            **({"attribute": "command-" + chosen["method"]}
               if chosen["method"] else {}),
        },
        "candidate_filter_caveat": (
            "Example filters only: hoursBack must be adjusted to cover the "
            "source incident and is capped by the gateway; a filtered "
            "zero-row result does not prove no historical commands existed."),
        "materiality": (
            "Check whether a bounded command-name/time-window history can "
            "distinguish an app-issued command from a driver-internal stall."),
        "limitation": (
            "Source clock zones and completeness are unverified; command "
            "proximity is correlation, not proof of a causal mechanism."),
    }


def gateway_offers_operation(manifest: Mapping[str, Any],
                             discovered: Mapping[str, set[str]],
                             operation: str) -> bool:
    for name, tool in manifest.items():
        if not name.startswith("hub_read_"):
            continue
        enum = tool.input_schema.get("properties", {}).get("tool", {}).get("enum")
        if isinstance(enum, list) and operation in enum:
            return True
        if operation in discovered.get(name, set()):
            return True
    return False


def useful_discovery_fingerprint(source: Mapping[str, Any]) -> tuple[str, ...]:
    result = source.get("results")
    if not isinstance(result, list):
        return ()
    return tuple(sorted({
        str(item.get("gateway")) + ":" + str(item.get("tool"))
        for item in result
        if isinstance(item, dict)
        and isinstance(item.get("gateway"), str)
        and isinstance(item.get("tool"), str)
    }))


__all__ = ["gap_for_target", "gateway_offers_operation",
           "useful_discovery_fingerprint"]

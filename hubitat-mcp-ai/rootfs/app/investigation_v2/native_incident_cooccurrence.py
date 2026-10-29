"""Bounded cross-occurrence warning/state association for any verified device.

The receipts describe timestamp proximity only, not executed driver paths,
app causation, a shared clock, or CPU contribution. A log-group min/max
range is never interpreted as continuous runtime activity. Repeated reads
of identical source rows do not inflate occurrence counts.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .native_evidence_coverage import _wall_time

_MAX_WARNINGS = 16
_MAX_STATES = 120
_ALLOW_STATE = frozenset({
    "volume", "status", "mediaSource", "switch", "level", "healthStatus",
    "networkStatus", "mute", "motion", "contact",
})


def incident_state_cooccurrences(
    witnesses: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str],
    *, tolerance_ms: int = 2000,
) -> dict[str, Any] | None:
    """Correlate individual returned warning instants with device state rows.

    Only device-scoped event history with a matching producer deviceId may
    supply state observations. Apps' command events are intentionally excluded:
    an issued command is not a device state update. No "absence" conclusion.
    """
    focus = {str(x) for x in focus_ids if str(x).isdecimal()}
    if len(focus) != 1:
        return None
    target = next(iter(focus))
    tolerance = max(0, min(10000, int(tolerance_ms)))
    warnings: dict[tuple[str, str, str], dict[str, Any]] = {}
    group_missing_timestamps = False
    source_truncation = False
    for w in witnesses[:16]:
        if w.get("operation") != "hub_get_logs":
            continue
        read = w.get("read")
        if type(read) is not int:
            continue
        source = w.get("source_data")
        summary = source.get("log_summary") if isinstance(source, Mapping) else None
        if not isinstance(summary, Mapping):
            continue
        source_truncation |= bool(summary.get("truncated_or_partial"))
        groups = summary.get("warning_error_groups", [])
        if not isinstance(groups, list):
            continue
        for g in groups[:25]:
            if not isinstance(g, Mapping) or str(g.get("source_id")) != target:
                continue
            level = str(g.get("level") or "").upper()
            if level not in ("WARN", "WARNING", "ERROR", "ERR", "FATAL"):
                continue
            instants = g.get("sample_timestamps")
            if not isinstance(instants, list) or not instants:
                group_missing_timestamps = True
                continue
            source_truncation |= bool(g.get("sample_timestamps_capped"))
            for instant in instants[-48:]:
                if not isinstance(instant, str) or _wall_time(instant) is None:
                    continue
                key = (target, str(g.get("message") or "")[:330], instant)
                if key not in warnings:
                    warnings[key] = {
                        "source_id": target, "severity": level,
                        "timestamp": instant, "read_ids": [read],
                    }
                elif read not in warnings[key]["read_ids"]:
                    warnings[key]["read_ids"].append(read)

    if not warnings:
        return None
    events: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    event_reads: set[int] = set()
    returned_event_rows = 0
    event_history_partial = False
    for w in witnesses[:16]:
        if w.get("operation") != "hub_list_device_events":
            continue
        filters = w.get("read_filters")
        if not isinstance(filters, Mapping) or str(filters.get("deviceId")) != target:
            continue
        read = w.get("read")
        data = w.get("source_data")
        if type(read) is not int or not isinstance(data, Mapping):
            continue
        event_reads.add(read)
        rows = data.get("events", [])
        if not isinstance(rows, list):
            continue
        returned_event_rows += int(data.get("returned_event_rows") or len(rows))
        event_history_partial |= bool(
            data.get("event_rows_omitted_from_model") or
            data.get("source_complete") is not True)
        for row in rows[:_MAX_STATES]:
            if not isinstance(row, Mapping):
                continue
            source = row.get("producedBy")
            if not isinstance(source, Mapping) or str(source.get("deviceId")) != target:
                continue
            if source.get("appId") is not None:
                continue
            name = row.get("name")
            if not isinstance(name, str) or name not in _ALLOW_STATE:
                continue
            stamp = row.get("date") or row.get("time")
            if not isinstance(stamp, str) or _wall_time(stamp) is None:
                continue
            value = row.get("value")
            # Limit values to small scalar state descriptions: never allow
            # arbitrary free-form media/metadata to enter the answer.
            if name == "volume":
                if str(value).isdecimal() and 0 <= int(value) <= 100:
                    safe_value = str(int(value))
                else:
                    continue
            elif name == "status":
                safe_value = str(value).strip().lower()
                if safe_value not in ("playing", "paused", "idle", "buffering",
                                      "online", "offline", "stopped"):
                    continue
            elif name in ("networkStatus", "healthStatus"):
                safe_value = str(value).strip().lower()
                if safe_value not in ("online", "offline", "unknown"):
                    continue
            elif name in ("switch", "motion", "contact", "mute"):
                safe_value = str(value).strip().lower()
                if safe_value not in ("on", "off", "active", "inactive", "open",
                                      "closed", "muted", "unmuted"):
                    continue
            elif name == "level":
                if str(value).isdecimal() and 0 <= int(value) <= 100:
                    safe_value = str(int(value))
                else:
                    continue
            elif name == "mediaSource":
                # Source strings may be URLs, titles, cast session text or
                # speech content, and cannot establish a method execution.
                continue
            else:
                continue
            key = (target, stamp, name, safe_value)
            if key not in events:
                events[key] = {
                    "name": name, "value": safe_value, "timestamp": stamp,
                    "read_ids": [read],
                }
            elif read not in events[key]["read_ids"]:
                events[key]["read_ids"].append(read)
    ordered_warns = sorted(
        warnings.values(),
        key=lambda w: _wall_time(w["timestamp"]),
        reverse=True,
    )
    ordered_states = list(events.values())
    instances: list[dict[str, Any]] = []
    coobserved = 0
    for warn in ordered_warns[:_MAX_WARNINGS]:
        when = _wall_time(warn["timestamp"])
        near = []
        for state in ordered_states:
            elapsed = abs((_wall_time(state["timestamp"]) - when).total_seconds()) * 1000
            if elapsed <= tolerance:
                near.append((elapsed, state))
        near.sort(key=lambda item: (item[0], item[1]["timestamp"], item[1]["name"]))
        if near:
            coobserved += 1
        instances.append({
            "warning_timestamp": warn["timestamp"],
            "warning_read_ids": warn["read_ids"],
            "coincident_states": [{
                **item[1], "reported_absolute_gap_ms": round(item[0], 3),
            } for item in near[:6]],
        })
    return {
        "target_device_id": target,
        "observed_distinct_warning_occurrences": len(warnings),
        "analyzed_warning_occurrences": len(instances),
        "warnings_with_nearby_state_in_returned_sample": coobserved,
        "window_tolerance_ms": tolerance,
        "instances": instances,
        "verified_scoped_event_reads": sorted(event_reads),
        "returned_scoped_event_rows": returned_event_rows,
        "group_times_missing": group_missing_timestamps,
        "sample_incomplete": bool(source_truncation or event_history_partial
                                  or len(ordered_warns) > _MAX_WARNINGS),
        "timezone_alignment_verified": False,
        "runtime_cause_verified": False,
        "interpretation_limit": (
            "Only source-reported timestamp proximity for independently "
            "returned warning records and device state events; repeated "
            "READs are deduplicated. This does not measure runtime CPU, "
            "prove command provenance or identify a driver callback. "
            "Sampling, coverage and source-clock alignment are unverified."
        ),
    }


__all__ = ["incident_state_cooccurrences"]

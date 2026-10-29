"""Cross-occurrence, clustered app-command leads for source-recorded warnings.

Keep three things distinct: discrete warning log rows, temporally close
app-issued commands, and *unverified* causal mechanism. A high-frequency
warning sequence is one cluster of observations, not N proven CPU incidents.
Every input is an independently approved read receipt, never model prose.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .native_evidence_coverage import _wall_time

_MAX_WARNINGS = 32
_MAX_COMMANDS = 120


def incident_command_temporal_leads(
    witnesses: Sequence[Mapping[str, Any]], focus_ids: Sequence[str],
    *, cluster_gap_ms: int = 15000, edge_ms: int = 2000,
) -> dict[str, Any] | None:
    focus = {str(x) for x in focus_ids if str(x).isdecimal()}
    if len(focus) != 1:
        return None
    device = next(iter(focus))
    gap = max(1000, min(30000, int(cluster_gap_ms)))
    edge = max(0, min(5000, int(edge_ms)))
    warnings: dict[tuple[str, str], dict[str, Any]] = {}
    commands: dict[tuple[str, str, str], dict[str, Any]] = {}
    event_reads: set[int] = set()
    source_partial = False
    for w in witnesses[:16]:
        source = w.get("source_data")
        if not isinstance(source, Mapping) or type(w.get("read")) is not int:
            continue
        read = w["read"]
        if w.get("operation") == "hub_get_logs":
            ls = source.get("log_summary")
            if not isinstance(ls, Mapping):
                continue
            source_partial |= bool(ls.get("truncated_or_partial"))
            for g in ls.get("warning_error_groups", [])[:25]:
                if (not isinstance(g, Mapping) or
                        str(g.get("source_id")) != device or
                        "excessive hub load" not in
                        str(g.get("message") or "").casefold()):
                    continue
                times = g.get("sample_timestamps")
                if not isinstance(times, list) or not times:
                    continue
                source_partial |= bool(g.get("sample_timestamps_capped"))
                for stamp in times[:48]:
                    if not isinstance(stamp, str) or _wall_time(stamp) is None:
                        continue
                    key = (str(g.get("message") or "")[:330], stamp)
                    if key not in warnings:
                        warnings[key] = {"timestamp": stamp, "read_ids": [read]}
                    elif read not in warnings[key]["read_ids"]:
                        warnings[key]["read_ids"].append(read)
        elif w.get("operation") == "hub_list_device_events":
            filters = w.get("read_filters")
            if (not isinstance(filters, Mapping) or
                    str(filters.get("deviceId")) != device):
                continue
            event_reads.add(read)
            source_partial |= bool(
                source.get("event_rows_omitted_from_model") or
                source.get("source_complete") is not True)
            rows = source.get("events")
            if not isinstance(rows, list):
                continue
            for event in rows[:_MAX_COMMANDS]:
                if not isinstance(event, Mapping):
                    continue
                actor = event.get("producedBy")
                name = event.get("name")
                stamp = event.get("date") or event.get("time")
                if (not isinstance(actor, Mapping) or
                        not isinstance(name, str) or
                        not name.startswith("command-") or
                        len(name) > 60 or
                        not isinstance(stamp, str) or
                        _wall_time(stamp) is None):
                    continue
                app = str(actor.get("appId") or "")
                if not app.isdecimal() or len(app) > 16:
                    continue
                command = name[8:]
                if (not command or len(command) > 45 or
                        not all(c.isalnum() or c in "_-" for c in command)):
                    continue
                key = (app, command, stamp)
                if key not in commands:
                    commands[key] = {
                        "app_id": app, "command": command,
                        "timestamp": stamp, "read_ids": [read],
                    }
                elif read not in commands[key]["read_ids"]:
                    commands[key]["read_ids"].append(read)
    if not warnings:
        return None
    sorted_warns = sorted(
        warnings.values(), key=lambda e: _wall_time(e["timestamp"]))
    # Consecutive warnings within a short gap form one bounded observation
    # cluster; an earlier outlying row is not a continuous incident.
    clusters: list[list[dict[str, Any]]] = []
    for warn in sorted_warns:
        if (not clusters or
                (_wall_time(warn["timestamp"]) -
                 _wall_time(clusters[-1][-1]["timestamp"])).total_seconds()
                 * 1000 > gap):
            clusters.append([])
        clusters[-1].append(warn)
    observed_commands = list(commands.values())
    results = []
    for cluster in clusters[-12:]:
        first = _wall_time(cluster[0]["timestamp"])
        last = _wall_time(cluster[-1]["timestamp"])
        near = []
        for cmd in observed_commands:
            when = _wall_time(cmd["timestamp"])
            if ((when - first).total_seconds() * 1000 < -edge or
                    (when - last).total_seconds() * 1000 > edge):
                continue
            gaps = [(when - _wall_time(w["timestamp"])).total_seconds() * 1000
                    for w in cluster]
            signed = min(gaps, key=lambda x: abs(x))
            near.append({**cmd,
                         "nearest_warning_gap_ms": round(abs(signed), 3),
                         "command_relative_to_warning": (
                             "after" if signed > 0 else
                             "before" if signed < 0 else "same_timestamp"),
                        })
        near.sort(key=lambda x: _wall_time(x["timestamp"]))
        by_actor: dict[str, dict[str, Any]] = {}
        for cmd in near:
            actor = by_actor.setdefault(cmd["app_id"], {
                "app_id": cmd["app_id"], "observed_commands": 0,
                "command_counts": {},
            })
            actor["observed_commands"] += 1
            name = cmd["command"]
            actor["command_counts"][name] = actor["command_counts"].get(name, 0) + 1
        results.append({
            "first_warning_timestamp": cluster[0]["timestamp"],
            "last_warning_timestamp": cluster[-1]["timestamp"],
            "warning_rows": len(cluster),
            "span_ms": round((last - first).total_seconds()*1000, 3),
            "commands_in_window_with_edges": len(near),
            "command_edge_tolerance_ms": edge,
            "app_issuers": list(by_actor.values())[:8],
            "sample_commands": near[:8],
            "warning_read_ids": sorted({r for x in cluster for r in x["read_ids"]}),
        })
    return {
        "target_device_id": device,
        "sampled_warning_rows": len(sorted_warns),
        "warning_clusters": results,
        "warning_cluster_count": len(clusters),
        "cluster_gap_ms": gap,
        "verified_scoped_event_reads": sorted(event_reads),
        "sample_incomplete": bool(source_partial or not event_reads or
                                  len(sorted_warns) > _MAX_WARNINGS or
                                  len(clusters) > 12),
        "clock_alignment_verified": False,
        "command_caused_warning_verified": False,
        "interpretation_limit": (
            "Clusters are source-timed groups of warning records, not "
            "measured CPU episodes. appId commands were read in the "
            "verified target device's history. Ordering and proximity "
            "are not driver-callback/CPU causality. Event sampling may "
            "omit commands and log/event clocks may not align."
        ),
    }


__all__ = ["incident_command_temporal_leads"]

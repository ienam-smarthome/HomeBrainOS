"""Stage 9.0: deterministic report-transition analysis on one bounded source page.

The observed ON->OFF intervals are differences between *reported* event
timestamps. A matched pair does not prove a complete physical operating cycle,
a correct device clock, an originating app, or any causal mechanism.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any


def _stamp(value: Any) -> datetime | None:
    if type(value) is not str or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def summarize_reported_transitions(evidence: dict[str, Any]) -> dict[str, Any]:
    """Summarise only sanitised command-shadow rows; do not issue any reads."""
    base = {
        "schema": "homebrain-stage90-reported-transitions.v1",
        "status": "no_usable_source",
        "report_intervals": [],
        "reported_on_count": 0,
        "reported_off_count": 0,
        "reported_command_count": 0,
        "reported_command_source": "bounded_device_event_pages_only",
        "trailing_on_without_later_off_in_page": False,
        "unmatched_or_ambiguous_state_rows": 0,
        "shortest_interval_seconds": None,
        "longest_interval_seconds": None,
        "median_interval_seconds": None,
        "findings": [],
        "conclusion": (
            "These records alone cannot establish why the device switched, "
            "which app initiated an action, or what happened physically."
        ),
        "next_evidence": (
            "A verified controlling-app ID and bounded contemporaneous "
            "app-decision logs or command provenance would be needed to "
            "investigate a specific ON/OFF report."
        ),
        "complete_history_verified": False,
        "device_clock_authenticated": False,
        "physical_cycle_verified": False,
        "app_causation_verified": False,
        "production_publisher_approval": False,
        "additional_hubitat_reads": 0,
        "additional_cloud_requests": 0,
        "device_commands": 0,
    }
    if (type(evidence) is not dict
            or evidence.get("schema") != "homebrain-stage85-command-shadow.v1"):
        return base
    rows = evidence.get("events")
    if type(rows) is not list:
        return base
    if evidence.get("status") not in (
        "bounded_source_evidence", "bounded_sources_no_day_matches"
    ):
        base["status"] = "partial_source_evidence"
        base["findings"] = [
            "Some bounded source reads failed or were unusable; a complete "
            "transition sequence cannot be assessed from this result."
        ]
        return base
    events = []
    commands = 0
    for row in rows[:150]:
        if type(row) is not dict:
            continue
        timestamp = _stamp(row.get("source_reported_time_utc"))
        if timestamp is None:
            continue
        if row.get("kind") == "recorded_command":
            if row.get("command") in ("off", "on"):
                commands += 1
        elif (row.get("kind") == "reported_switch_state"
              and row.get("value") in ("on", "off")):
            events.append((timestamp, row["value"]))
    events.sort(key=lambda pair: (pair[0], pair[1]))
    base["reported_on_count"] = sum(v == "on" for _, v in events)
    base["reported_off_count"] = sum(v == "off" for _, v in events)
    base["reported_command_count"] = commands
    pending_on: datetime | None = None
    ambiguous_pending = False
    unmatched = 0
    intervals = []
    for stamp, state in events:
        if state == "on":
            if pending_on is not None:
                unmatched += 1
                ambiguous_pending = True
            else:
                ambiguous_pending = False
            pending_on = stamp
        else:
            if pending_on is None:
                unmatched += 1
            elif ambiguous_pending or stamp <= pending_on:
                unmatched += 2
            else:
                delta = (stamp - pending_on).total_seconds()
                intervals.append({
                    "on_reported_utc": pending_on.isoformat(),
                    "off_reported_utc": stamp.isoformat(),
                    "reported_interval_seconds": round(delta, 1),
                    "clock_basis": "hubitat_event_source_reported_unverified",
                    "physical_duration_proven": False,
                })
            pending_on = None
            ambiguous_pending = False
    if pending_on is not None:
        unmatched += 1
        base["trailing_on_without_later_off_in_page"] = True
    base["unmatched_or_ambiguous_state_rows"] = unmatched
    base["report_intervals"] = intervals[:50]
    durations = [r["reported_interval_seconds"] for r in intervals]
    if durations:
        base["shortest_interval_seconds"] = round(min(durations), 1)
        base["longest_interval_seconds"] = round(max(durations), 1)
        base["median_interval_seconds"] = round(median(durations), 1)

    count = len(intervals)
    total = len(events)
    findings = [
        f"This bounded Hubitat event page contains {total} switch reports: "
        f"{base['reported_on_count']} ON and {base['reported_off_count']} OFF.",
        f"Within these returned reports, {count} ordered ON-to-OFF "
        "pairs have identifiable timestamps. These are REPORT intervals, "
        "not verified physical operating cycles.",
    ]
    if durations:
        findings.append(
            f"Their source-reported intervals range from "
            f"{base['shortest_interval_seconds']:.1f} to "
            f"{base['longest_interval_seconds']:.1f} seconds "
            f"(median {base['median_interval_seconds']:.1f} seconds); "
            "clock accuracy and intervening event coverage are not proven."
        )
    if pending_on is not None:
        findings.append(
            "The most recent ON report in this returned page has no later "
            "OFF report in the same page. This does not establish that the "
            "device is still ON."
        )
    if unmatched:
        findings.append(
            f"{unmatched} state report positions were unmatched or ambiguous "
            "in this bounded pairing analysis; the source may omit events."
        )
    if not commands:
        findings.append(
            "The bounded command-on/off pages supplied no recorded commands "
            "with a verified issuer. This does not prove no automation acted."
        )
    else:
        findings.append(
            f"The returned pages contain {commands} recorded command rows, "
            "but temporal proximity alone does not identify which command "
            "caused an ON/OFF report or establish execution."
        )
    if any(
        type(diag) is dict and diag.get("page_at_limit") is True
        for diag in (evidence.get("read_diagnostics") or {}).values()
    ):
        findings.append(
            "At least one upstream page hit its row cap, so earlier events "
            "may be missing."
        )
    base["findings"] = findings
    base["status"] = "bounded_report_transition_review"
    return base


__all__ = ["summarize_reported_transitions"]

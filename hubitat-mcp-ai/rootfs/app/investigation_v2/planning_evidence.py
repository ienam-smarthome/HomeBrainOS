"""Bounded planning view over the unmodified canonical V2 evidence case.

Keep every command and every material switch/health transition. Coalesce
repetitive non-decisive telemetry only in the model's prompt. The full
source case, source IDs and coverage remain available for audit and reports.
No source completeness or physical state is inferred from sampling.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .evidence import CaseFile
from .temporal_scope import IncidentWindow
from .transition_links import incident_links
from .causal_evidence import command_state_pairs, command_history_coverage, focused_switch_command


def _planning_indices(case: CaseFile) -> set[int]:
    """Retain every material transition; reduce repeated background sampling.

    Small investigations are lossless. For large investigations, keep all
    commands, switch and explicit availability transitions, settings, and
    observations near a command. Otherwise retain first/last by action so
    background polling does not drown decisive incident evidence.
    """
    records = case.records
    # Above a small lossless case, sample background telemetry rather
    # than carry every 2-minute electricity/meter update into a model plan.
    # Command, switch, availability and config observations remain lossless.
    if len(records) <= 12:
        return set(range(len(records)))
    commands = [
        (row.target_id, datetime.fromisoformat(row.timestamp_utc))
        for row in records if row.stage == "command_issued"
    ]
    picked: set[int] = set()
    seen: dict[tuple[str, str, str | None], list[int]] = {}
    for i, row in enumerate(records):
        key = (row.stage, row.action, row.target_id)
        seen.setdefault(key, []).append(i)
        # Never coalesce a command, observed switch/availability transition,
        # physical observation or typed stored configuration. Suppressed rows
        # are still retained in the canonical source-backed investigation.
        if (row.stage in ("command_issued", "config_stored",
                          "independent_physical_observation")
                or row.action in ("switch", "healthStatus", "networkStatus")
                or (row.action == "deviceHealth" and
                    str(row.value).lower() in ("online", "offline", "connected",
                                               "disconnected"))):
            # Alternating stale/unknown is a driver watchdog classification,
            # not independent contact; coalesce samples into explicit counts.
            # Keep substantive online/offline classifications individually.
            picked.add(i)
    for indices in seen.values():
        # Bound polling samples by signal and device: first, last, nearest
        # preceding and immediately following each incident command.
        # A ±15-minute inclusion window previously retained every voltage,
        # energy and lastSeen poll and inflated the planning input.
        picked.update(indices[:1])
        picked.update(indices[-1:])
        for target, stamp in commands:
            candidates = [(i, (datetime.fromisoformat(records[i].timestamp_utc)
                               - stamp).total_seconds())
                          for i in indices if records[i].target_id == target]
            earlier = [i for i, seconds in candidates if -900 <= seconds <= 0]
            later = [i for i, seconds in candidates if 0 < seconds <= 300]
            if earlier:
                picked.add(max(earlier, key=lambda i: records[i].timestamp_utc))
            if later:
                picked.add(min(later, key=lambda i: records[i].timestamp_utc))
    return picked


def planning_evidence(
    case: CaseFile, window: IncidentWindow | None, *,
    focus_latest: bool = False,
) -> str:
    zone = ZoneInfo(window.zone_name) if window is not None else None
    kept = _planning_indices(case)
    # The canonical case always stays lossless. Only a MODEL'S planning
    # input for a large, undated case may focus around the latest attested
    # switch incident. Explicit historical-window investigations remain
    # lossless, and an unpaired switch report does not justify guessing.
    focused_command, focus_basis = focused_switch_command(case)
    reduced_latest = False
    if (focus_latest and window is None and len(case.records) > 48
            and focused_command is not None
            and focus_basis == "paired_latest_switch_transition"):
        switch_reports = [r for r in case.records
                          if r.stage == "state_reported" and r.action == "switch"
                          and r.target_id == focused_command.target_id
                          and r.time_basis == "event_time"]
        if switch_reports:
            anchor = max(switch_reports, key=lambda row: row.timestamp_utc)
            moment = datetime.fromisoformat(anchor.timestamp_utc)
            recent = {
                idx for idx, row in enumerate(case.records)
                if (row.stage == "config_stored"
                    or row.target_id == focused_command.target_id
                    and abs((datetime.fromisoformat(row.timestamp_utc)-moment).total_seconds()) <= 7200
                    or row.target_id != focused_command.target_id
                    and -7200 <= (datetime.fromisoformat(row.timestamp_utc)-moment).total_seconds() <= 7200)
            }
            earlier: dict[tuple[str, str, str | None], list[int]] = {}
            for idx in sorted(kept - recent):
                row = case.records[idx]
                earlier.setdefault((row.stage, row.action, row.producer_id), []).append(idx)
            for indices in earlier.values():
                recent.update(indices[-1:])
            recent.update(idx for idx,row in enumerate(case.records)
                          if row.record_id == focused_command.record_id
                          or row.record_id == anchor.record_id)
            if len(recent) < len(kept):
                kept = recent
                reduced_latest = True
    events = []
    omitted = Counter()
    for i, row in enumerate(case.records):
        if i not in kept:
            omitted[(row.stage, row.action)] += 1
            continue
        local = (datetime.fromisoformat(row.timestamp_utc).astimezone(zone).isoformat()
                 if zone is not None else None)
        item = {
            "id": row.record_id, "utc": row.timestamp_utc,
            "stage": row.stage, "action": row.action,
            "target": row.target_id, "issuer_id": row.producer_id,
        }
        if local is not None:
            item["local"] = local
        if row.value is not None:
            item["value"] = row.value
        events.append(item)
    coverage = [{
        "operation": c.operation, "target": c.query_target_id,
        "succeeded": c.succeeded, "rows": c.returned_rows,
        "historical_start_reached": c.requested_window_reached,
        "source_complete": c.source_complete, "truncated": c.truncated,
        "errors": list(c.errors)[:3],
    } for c in case.coverage]
    issuers = {r.producer_id for r in case.records if r.producer_id}
    identities = {k: v for k, v in case.app_identities.items() if k in issuers}
    links = [{
        "command_id": link.command.record_id,
        "state_report_id": (link.reported_state.record_id
                            if link.reported_state else None),
        "adverse_report_id": link.adverse_state.record_id,
        "seconds_to_adverse": round(link.seconds_to_adverse, 3),
        "physical_cause_verified": False,
    } for link in incident_links(case)[:8]]
    targets = sorted({
        r.target_id for r in case.records if r.target_id
    }, key=lambda ident: int(ident))[:8]
    # Never turn event chronology into an unverified rule decision.
    # These immutable typed links are useful to every model/provider,
    # including native-tool and structured-proposal planners.
    command_pairs = [pair.to_dict() for pair in command_state_pairs(case)[:16]]
    command_coverage = []
    for target in targets:
        coverage_info = command_history_coverage(case, target)
        if (command_pairs
                or "command_events_excluded_by_filter" in coverage_info["issues"]
                or coverage_info["observed_command_records"] == 0):
            # Compact evidence, not duplicated full coverage tables. Ordinary
            # command-only historical data already appear in the records and
            # basic source completeness list; no empty boilerplate arrays.
            command_coverage.append({
                "device_id": target,
                "issues": coverage_info["issues"],
                "observed_command_records": coverage_info["observed_command_records"],
            })
    # Stored references are provenance-typed current selections, never
    # inferred sensor triggers or guaranteed historical rule configuration.
    selected_sensor_ids = [
        {"app_id": app_id, "setting": entry["key"],
         "sensor_ids": entry["deviceIds"][:8],
         "historical_selection_verified": False}
        for app_id, references in sorted(case.app_sensor_references.items(), key=lambda x: int(x[0]))
        for entry in references[:8]
    ][:16]
    return json.dumps({
        "records": events,
        "total_case_records": len(case.records),
        **({"planning_view": "latest_attested_switch_incident",
            "full_case_retained_for_audit": True,
            "suppressed_older_records": len(case.records)-len(events)}
           if reduced_latest else {}),
        "coalesced_context": [
            {"stage": stage, "action": action, "rows": count}
            for (stage, action), count in sorted(omitted.items())
        ],
        "incident_links": links,
        **({"command_state_pairs": command_pairs} if command_pairs else {}),
        **({"command_history_coverage": command_coverage}
           if command_coverage else {}),
        "coverage": coverage,
        "current_app_name_by_issuer_id": identities,
        **({"current_controller_sensor_selections": selected_sensor_ids}
           if selected_sensor_ids else {}),
        "constraints": [
            "Command issued does not prove physical state changed",
            "A command-state time pair is not proof of internal automation logic",
            "Switch-only event history cannot establish no command was issued",
            "Incident links are temporal candidates, not causal proof",
            "Coalesced model context is retained in the full source case",
            "History source completeness unverified unless explicit",
            "Current settings do not prove historical execution",
            *(['Current sensor selections do not prove event-time triggers']
              if selected_sensor_ids else []),
            "Use event record IDs; never invent clock times or command issuers",
        ],
    }, ensure_ascii=True, separators=(",", ":"))


__all__ = ["planning_evidence"]

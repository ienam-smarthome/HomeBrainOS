"""Bounded planning view over the unmodified canonical V2 evidence case.

Keep every command and every material switch/health transition. Coalesce
repetitive non-decisive telemetry only in the model's prompt. The full
source case, source IDs and coverage remain available for audit and reports.
No source completeness or physical state is inferred from sampling.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from .evidence import CaseFile
from .temporal_scope import IncidentWindow
from .transition_links import incident_links


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
        datetime.fromisoformat(row.timestamp_utc)
        for row in records if row.stage == "command_issued"
    ]
    picked: set[int] = set()
    seen: dict[tuple[str, str, str | None], list[int]] = {}
    for i, row in enumerate(records):
        key = (row.stage, row.action, row.target_id)
        seen.setdefault(key, []).append(i)
        essential = (
            row.stage in ("command_issued", "config_stored",
                          "independent_physical_observation")
            or row.action in ("switch", "healthStatus", "networkStatus")
        )
        near_command = any(
            abs((datetime.fromisoformat(row.timestamp_utc) - stamp).total_seconds())
            <= 15 * 60 for stamp in commands
        )
        if essential or near_command:
            picked.add(i)
    for indices in seen.values():
        # Source before/after state context remains represented for every
        # non-essential action, including lastSeen and MQTT client statuses.
        picked.update(indices[:1])
        picked.update(indices[-1:])
    return picked


def planning_evidence(case: CaseFile, window: IncidentWindow | None) -> str:
    zone = ZoneInfo(window.zone_name) if window is not None else None
    kept = _planning_indices(case)
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
    return json.dumps({
        "records": events,
        "total_case_records": len(case.records),
        "coalesced_context": [
            {"stage": stage, "action": action, "rows": count}
            for (stage, action), count in sorted(omitted.items())
        ],
        "incident_links": links,
        "coverage": coverage,
        "current_app_name_by_issuer_id": identities,
        "constraints": [
            "Command issued does not prove physical state changed",
            "Incident links are temporal candidates, not causal proof",
            "Coalesced model context is retained in the full source case",
            "History source completeness unverified unless explicit",
            "Current settings do not prove historical execution",
            "Use event record IDs; never invent clock times or command issuers",
        ],
    }, ensure_ascii=True, separators=(",", ":"))


__all__ = ["planning_evidence"]

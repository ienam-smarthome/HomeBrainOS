"""Compact, complete-for-planning projection of host-verified V2 case records.

The full immutable case and exhaustive canonical evidence remain untouched.
This only removes redundant tool provenance repetition from the FIRST-stage
decision prompt. Every record ID, event stage, UTC/local timestamp, command
actor, target, and source coverage remains. If too long, fail closed instead
of silently discarding material commands.
"""
from __future__ import annotations
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from .evidence import CaseFile
from .temporal_scope import IncidentWindow


def planning_evidence(case: CaseFile, window: IncidentWindow | None) -> str:
    zone = ZoneInfo(window.zone_name) if window is not None else None
    events = []
    for row in case.records:
        local = None
        if zone is not None:
            local = datetime.fromisoformat(row.timestamp_utc).astimezone(zone).isoformat()
        events.append({
            "id": row.record_id,
            "utc": row.timestamp_utc,
            "local": local,
            "stage": row.stage,
            "action": row.action,
            "value": row.value,
            "target": row.target_id,
            "issuer_id": row.producer_id,
        })
    coverage = [{
        "operation": c.operation,
        "target": c.query_target_id,
        "succeeded": c.succeeded,
        "rows": c.returned_rows,
        "historical_start_reached": c.requested_window_reached,
        "source_complete": c.source_complete,
        "truncated": c.truncated,
        "errors": list(c.errors)[:3],
    } for c in case.coverage]
    known_issuers = {r.producer_id for r in case.records if r.producer_id}
    identities = {
        k: v for k,v in case.app_identities.items() if k in known_issuers
    }
    return json.dumps({
        "records": events,
        "coverage": coverage,
        "current_app_name_by_issuer_id": identities,
        "constraints": [
            "Command issued does not prove state changed",
            "History source completeness unverified unless explicit",
            "App name is read-time metadata, not historical execution proof",
            "Use event record IDs rather than guessing clock times",
        ],
    }, ensure_ascii=True, separators=(",", ":"))


__all__ = ["planning_evidence"]

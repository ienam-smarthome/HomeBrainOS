"""Measured forensic investigation checks, not a fabricated causal grade.

Keep judgement separate from retrieval coverage and known source records.
Any model claimed causal accuracy requires independent review.
"""
from __future__ import annotations
from .evidence import CaseFile
from .temporal_scope import IncidentWindow


def forensic_metrics(case: CaseFile, window: IncidentWindow | None) -> dict:
    if window is None:
        relevant=list(case.records)
    else:
        relevant=[row for row in case.records if window.contains(row.timestamp_utc)]
    commands=[row for row in relevant if row.stage=="command_issued"]
    attributed=[row for row in commands if row.producer_id]
    pages=[c for c in case.coverage if c.operation=="hub_list_device_events"]
    reached=any(c.requested_window_reached is True and c.succeeded for c in pages)
    unknown=any(c.succeeded and c.requested_window_reached is None for c in pages)
    return {
        "incident_window_configured": window is not None,
        "incident_records": len(relevant),
        "incident_command_records": len(commands),
        "incident_commands_with_source_id": len(attributed),
        "incident_command_attribution_fraction": (len(attributed)/len(commands) if commands else None),
        "incident_history_pages": len(pages),
        "incident_start_reached_by_returned_page": (reached if pages else None),
        "incident_start_coverage_unverified": bool(window is not None and not reached),
        "incident_source_completion_proven": bool(pages) and all(c.source_complete is True for c in pages),
        "causal_accuracy_verified": False,
        "evidence_missing_is_not_proof_of_no_activity": True,
    }


__all__=["forensic_metrics"]

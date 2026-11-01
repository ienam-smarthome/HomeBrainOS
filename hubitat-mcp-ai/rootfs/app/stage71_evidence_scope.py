"""Stage 7.1: structured evidence-coverage and causal-question review.

Only inspect *static fictional fixture records* after the model's investigation
is over. This module does not evaluate arbitrary natural-language claims or
promote missing records to proof that an event did not occur.

The entire packet is a reviewer aid; no field authorizes production publishing.
"""
from __future__ import annotations

from typing import Any


_OBLIGATIONS = (
    ("reported_observations", "What state or telemetry was actually reported?"),
    ("recorded_actions", "Which commands or app decisions were actually recorded?"),
    ("causal_attribution", "What establishes or leaves uncertain the proposed cause?"),
    ("physical_and_negative_scope",
     "What physical outcomes are independently verified, and how far do absence claims extend?"),
)


def _is_confirmed(record: dict[str, Any]) -> bool:
    """Only explicit positive confirmations count as confirmation records."""
    return (
        record.get("physical_acknowledgement") is True
        or record.get("device_confirmation") is True
    )


def _view(case: dict[str, Any], selected: set[str]) -> dict[str, Any]:
    records = [("INITIAL", case["initial"])]
    for source in case["catalog"]:
        sid = source["id"]
        if sid in selected:
            records.extend((sid, rec) for rec in source["records"])
    acknowledgements = [
        {"source_id": sid, "record_id": rec["id"]}
        for sid, rec in records if _is_confirmed(rec)
    ]
    missing_confirmations = [
        {"source_id": sid, "record_id": rec["id"],
         "field": field}
        for sid, rec in records
        for field in ("physical_acknowledgement", "device_confirmation")
        if rec.get(field) is False
    ]
    explicit_gaps = [
        {"source_id": sid, "record_id": rec["id"]}
        for sid, rec in records if rec.get("kind") == "coverage_gap"
    ]
    return {
        "sources_examined": sorted({sid for sid, _ in records}),
        "reported_state_record_ids": [
            rec["id"] for _, rec in records
            if rec.get("kind") in ("state_report", "device_telemetry")
        ],
        "command_or_app_decision_record_ids": [
            rec["id"] for _, rec in records
            if rec.get("kind") in ("command_record", "app_decision")
        ],
        "positive_confirmation_records": acknowledgements,
        "records_marked_not_physically_acknowledged": missing_confirmations,
        "explicit_coverage_gap_records": explicit_gaps,
        # Evidence completeness is NOT asserted by any fixture.
        "complete_history_proven": False,
        "absence_outside_this_view_proven": False,
        "unique_command_to_physical_outcome_link_proven": False,
    }


def build_evidence_scope_review(
    case: dict[str, Any], selected_ids: list[str],
) -> dict[str, Any]:
    """Host-derived boundaries for examining possible claims of absence/cause.

    Never use an invented natural-language keyword matcher to label prose.
    Human reviewer checks each sentence and original question using the
    source scope ledger. Model-selected and full supplied evidence are kept
    separate; reading a later hidden source cannot improve model recall.
    """
    if type(case) is not dict or type(selected_ids) is not list:
        raise ValueError("invalid synthetic scope inputs")
    catalog = case["catalog"]
    ids = {s["id"] for s in catalog}
    if (len(ids) != len(catalog)
            or len(selected_ids) > 3
            or len(selected_ids) != len(set(selected_ids))
            or any(sid not in ids for sid in selected_ids)):
        raise ValueError("invalid synthetic source selection")
    read = _view(case, set(selected_ids))
    complete_supplied = _view(case, ids)
    return {
        "schema": "homebrain-stage71-evidence-scope.v1",
        "review_questions": [
            {"id": qid, "question": q,
             "human_answer_coverage": "not_reviewed"}
            for qid, q in _OBLIGATIONS
        ],
        "model_examined_records": read,
        "all_supplied_fictional_records": complete_supplied,
        "model_skipped_source_ids": sorted(ids - set(selected_ids)),
        "negative_claim_scope": {
            "model_visible": "Only inspected fictional records, not the full event history",
            "reviewer_visible": "All supplied fictional fixture records, not all events that may have occurred",
            "supported_template": "No physical acknowledgement is recorded in the examined sources.",
            "unsupported_template": "No physical acknowledgement exists anywhere.",
            "global_absence_proven": False,
            "physical_nonexecution_proven": False,
        },
        "causal_link_proven": False,
        "full_prose_semantics_certified": False,
        "scope_review_requires_independent_human": True,
        "publisher_approval": False,
    }


__all__ = ["build_evidence_scope_review"]

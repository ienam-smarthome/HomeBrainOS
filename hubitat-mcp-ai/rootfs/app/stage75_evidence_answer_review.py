"""Stage 7.5 synthetic evidence/answer separation and causal review worklist.

Operates only AFTER the model has made all source decisions and authored prose.
Host-observable evidence structure, model-declared finding labels, and the
independent human judgment of actual language are three different things.
No model inference, text heuristics, live MCP access, or publisher authority.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Callable


def _source_records(case: dict, selected: list[str]) -> list[dict]:
    records = [case["initial"]]
    for source in case["catalog"]:
        if source["id"] in selected:
            records.extend(source["records"])
    return records


def _command_order(commands: list[dict]) -> tuple[list[dict], str]:
    """Order *recorded time-of-day* fields, never infer execution or dates.

    Source catalog order is not chronological. Equally, an HH:MM:SSZ value
    alone does not establish a date, clock accuracy, or midnight rollover.
    Invalid/mixed clock bases retain source order, explicitly unranked.
    """
    if not commands:
        return [], "no_command_records"
    values = []
    bases = set()
    for record in commands:
        at = record.get("at")
        if (type(at) is not str or len(at) != 9
                or at[2] != ":" or at[5] != ":" or at[-1] != "Z"
                or not (at[:2] + at[3:5] + at[6:8]).isdigit()
                or int(at[:2]) > 23 or int(at[3:5]) > 59
                or int(at[6:8]) > 59):
            return list(commands), "source_order_not_chronological"
        values.append(at)
        bases.add(record.get("clock_basis"))
    if len(bases) != 1:
        return list(commands), "mixed_clock_bases_not_comparable"
    # Lexicographic ordering is safe for canonical HH:MM:SSZ *time-of-day*
    # strings; this is not a claim that actual physical events occurred so.
    return sorted(commands, key=lambda row: (row["at"], row["id"])), (
        "recorded_utc_time_of_day_only_not_cross_day_or_execution_proof"
    )


def _obligation_evidence_status(obligation: dict[str, Any]) -> str:
    """Evidence availability/overlap only; never a prose-adequacy verdict."""
    unseen = obligation["reference_records_not_examined_by_model"]
    seen = set(obligation["reference_records_available_to_model"])
    cited = set(obligation["reference_records_cited_by_model"])
    if unseen:
        return "reference_evidence_not_fully_examined"
    if not cited:
        return "available_but_not_cited"
    if cited != seen:
        return "available_and_partially_cited"
    return "all_reference_ids_cited_not_semantically_reviewed"


def build_stage75_review(
    case: dict[str, Any],
    selected: list[str],
    draft: dict[str, Any],
    answer_coverage: dict[str, Any],
    typed_source_checker: Callable[[str, list[dict]], bool],
) -> dict[str, Any]:
    """Postrun structured source audit, *not* automatic answer verification.

    Host proof of source TYPE is intentionally weaker than verification of
    source content, model claims, causal links, or absence of unobserved events.
    A missing model relationship label cannot erase an observable pair of
    distinct commands; the pair cannot automatically validate model prose.
    """
    if (type(case) is not dict or type(selected) is not list
            or type(draft) is not dict or type(answer_coverage) is not dict
            or not callable(typed_source_checker)):
        raise ValueError("invalid Stage 7.5 synthetic inputs")
    catalog = case["catalog"]
    known = {src["id"] for src in catalog}
    if (len(known) != len(catalog) or len(selected) > 3
            or len(selected) != len(set(selected))
            or any(type(sid) is not str or sid not in known for sid in selected)):
        raise ValueError("invalid Stage 7.5 selected sources")
    if answer_coverage.get("schema") != "homebrain-stage72-answer-coverage.v1":
        raise ValueError("invalid Stage 7.5 answer obligations")

    records = _source_records(case, selected)
    ids = {rec["id"] for rec in records}
    if len(ids) != len(records):
        raise ValueError("duplicate synthetic record")
    sentences = draft["sentences"]
    if any(not set(s["evidence_ids"]) <= ids for s in sentences):
        raise ValueError("model cited unseen synthetic record")

    required = case["required_types"]
    observed = []
    for kind in required:
        # Only fixture-source type structures are assessed. Pair checks can
        # detect a relationship without relying on the model assigning the
        # dedicated relationship kind to any of its sentences.
        witnesses = ((rec,) for rec in records)
        pairs = combinations(records, 2)
        if any(typed_source_checker(kind, list(group))
               for group in (*witnesses, *pairs)):
            observed.append(kind)

    declared = {s["kind"] for s in sentences}
    obligations = []
    for item in answer_coverage["obligations"]:
        obligations.append({
            "id": item["id"],
            "importance": item["importance"],
            "reference_evidence_status": _obligation_evidence_status(item),
            "evidence_availability_is_not_answer_quality": True,
            "independent_semantic_verdict": "not_reviewed",
        })

    unordered_commands = [
        rec for rec in records if rec["kind"] == "command_record"
    ]
    commands, command_order_basis = _command_order(unordered_commands)
    reports = [rec["id"] for rec in records if rec["kind"] == "state_report"]
    telemetry = [rec["id"] for rec in records
                 if rec["kind"] == "device_telemetry"
                 and rec.get("independent_device_packet") is True]
    acknowledged = [rec["id"] for rec in commands
                    if rec.get("physical_acknowledgement") is True]
    gaps = [rec["id"] for rec in records if rec["kind"] == "coverage_gap"]
    return {
        "schema": "homebrain-stage75-evidence-answer-review.v1",
        "source_evidence": {
            "host_observable_reference_type_coverage":
                f"{len(observed)}/{len(required)}",
            "host_observable_reference_types": observed,
            "model_declared_reference_type_coverage":
                f"{len(set(required) & declared)}/{len(required)}",
            "model_declared_reference_types": sorted(set(required) & declared),
            "missing_model_relationship_labels_do_not_reduce_host_evidence": True,
            "source_type_presence_is_not_full_factual_or_prose_proof": True,
        },
        "original_question_review": {
            "obligations": obligations,
            "no_automatic_answer_completeness_verdict": True,
            "model_sentence_semantics_not_independently_checked": True,
        },
        "causal_evidence_ladder": {
            "recorded_command_ids": [rec["id"] for rec in commands],
            "recorded_command_display_order_basis": command_order_basis,
            "recorded_command_timeline": [
                {"record_id": rec["id"], "recorded_at": rec.get("at"),
                 "clock_basis": rec.get("clock_basis", "not_specified_in_record")}
                for rec in commands
            ],
            "recorded_times_prove_physical_execution": False,
            "cross_day_chronology_or_clock_accuracy_proven": False,
            "reported_state_record_ids": reports,
            "independent_device_telemetry_ids": telemetry,
            "command_acknowledgement_record_ids": acknowledged,
            "explicit_coverage_gap_ids": gaps,
            "state_report_clock_receipts": [
                {"record_id": rec["id"],
                 "source_time": rec.get("source_time"),
                 "received_at": rec.get("received_at"),
                 "clock_basis": rec.get("clock_basis")}
                for rec in records if rec["kind"] == "state_report"
            ],
            "source_timestamp_is_not_independent_telemetry": True,
            "driver_broker_session_ids": [
                rec["id"] for rec in records if rec["kind"] == "broker_session"
            ],
            "broker_session_alone_proves_device_online": False,
            # A device packet can establish a physical observation without
            # tying the observation to either competing command.
            "telemetry_alone_identifies_command_initiator": False,
            # No fixture contains an authenticated command->outcome binding.
            "command_correlated_execution_confirmed": False,
            "unique_causal_attribution_proven": False,
            "absence_outside_examined_records_proven": False,
            "next_evidence_review_hint":
                "Check command-correlated execution receipts or equivalent "
                "independent causal evidence; device telemetry alone does "
                "not necessarily identify the initiating application.",
        },
        "model_next_evidence_suggestion": {
            "text": draft["next_evidence"],
            "independently_validated": False,
        },
        "synthetic_postrun_only": True,
        "host_reference_labels_not_sent_to_model": True,
        "natural_language_factual_semantics_verified": False,
        "independent_human_review_required": True,
        "additional_cloud_requests": 0,
        "publisher_approval": False,
    }


__all__ = ["build_stage75_review"]

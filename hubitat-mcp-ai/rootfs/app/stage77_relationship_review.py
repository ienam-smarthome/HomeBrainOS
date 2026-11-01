"""Stage 7.7: independent, post-inference relationship and evidence-gap review.

Only static fictional fixtures are accepted by the caller. This review is
constructed AFTER the model has chosen all reads and written its answer. It
does not route reads, augment model-facing prompts with hidden references,
certify text, establish clock accuracy, or approve production publishing.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any


def _hhmmss(value: Any) -> bool:
    if type(value) is not str or len(value) != 9:
        return False
    return (
        value[2] == ":" and value[5] == ":" and value[8] == "Z"
        and all(value[i].isdigit() for i in (0, 1, 3, 4, 6, 7))
        and int(value[:2]) < 24 and int(value[3:5]) < 60
        and int(value[6:8]) < 60
    )


def build_stage77_review(
    case: dict[str, Any], selected: list[str],
    answer_coverage: dict[str, Any],
) -> dict[str, Any]:
    """Expose independently typed relationships, never judge author wording."""
    if (type(case) is not dict or type(selected) is not list
            or type(answer_coverage) is not dict
            or answer_coverage.get("schema") != "homebrain-stage72-answer-coverage.v1"):
        raise ValueError("invalid Stage 7.7 synthetic inputs")
    catalog = case["catalog"]
    available = {src["id"] for src in catalog}
    if (len(available) != len(catalog) or len(selected) > 3
            or len(set(selected)) != len(selected)
            or any(type(x) is not str or x not in available for x in selected)):
        raise ValueError("invalid source selection")

    records = [case["initial"]]
    for source in catalog:
        if source["id"] in selected:
            records.extend(source["records"])
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("duplicate record ID")

    # Compare only time-of-day fields explicitly present on reports from the
    # same device. Differences in reception order are observable, but clocks
    # need not agree and absolute/cross-day physical order remains unknown.
    inversions = []
    reports = [r for r in records if r.get("kind") == "state_report"]
    for a, b in combinations(reports, 2):
        if (not a.get("device") or a["device"] != b.get("device")
                or a.get("clock_basis") != "device-source"
                or b.get("clock_basis") != "device-source"
                or not all(_hhmmss(r.get(k)) for r in (a, b)
                            for k in ("source_time", "received_at"))):
            continue
        source_cmp = (a["source_time"] > b["source_time"]) - (
            a["source_time"] < b["source_time"])
        receipt_cmp = (a["received_at"] > b["received_at"]) - (
            a["received_at"] < b["received_at"])
        if source_cmp * receipt_cmp < 0:
            early_source, late_source = (
                (a, b) if source_cmp < 0 else (b, a))
            early_receipt, late_receipt = (
                (a, b) if receipt_cmp < 0 else (b, a))
            inversions.append({
                "device": a["device"],
                "source_time_order_ids": [early_source["id"], late_source["id"]],
                "receipt_time_order_ids": [early_receipt["id"], late_receipt["id"]],
                "source_times": [early_source["source_time"], late_source["source_time"]],
                "receipt_times": [early_receipt["received_at"], late_receipt["received_at"]],
                "observation": "source_order_and_receipt_order_reversed",
                "proves_physical_event_order": False,
                "source_clock_accuracy_proven": False,
            })

    # This is only a postrun reference gap report. It is NEVER consulted when
    # selecting the next source; only the model chooses, without gold labels.
    missing_critical = [{
        "obligation_id": x["id"],
        "missing_record_ids": list(x["reference_records_not_examined_by_model"]),
    } for x in answer_coverage["obligations"]
        if x["importance"] == "critical"
        and x["reference_records_not_examined_by_model"]]

    statuses = {
        "broker_session_ids": [r["id"] for r in records
                               if r.get("kind") == "broker_session"],
        "watchdog_tick_ids": [r["id"] for r in records
                              if r.get("kind") == "watchdog_tick"],
        "independent_device_packet_ids": [r["id"] for r in records
            if r.get("kind") == "device_telemetry"
            and r.get("independent_device_packet") is True],
    }
    return {
        "schema": "homebrain-stage77-relationship-and-coverage.v1",
        "source_receipt_order_inversions": inversions,
        "source_receipt_inversion_count": len(inversions),
        "no_inversion_does_not_prove_correct_clock_or_complete_history": True,
        "transport_and_device_evidence": {
            **statuses,
            "broker_connection_is_not_device_online_proof": True,
            "watchdog_tick_is_not_device_origin_telemetry": True,
            "device_packet_origin_does_not_authenticate_source_clock_accuracy": True,
        },
        "postrun_critical_reference_gaps": missing_critical,
        "postrun_reference_gaps_never_control_model_reads": True,
        "model_observed_question_completeness_certified": False,
        "natural_language_semantics_certified": False,
        "additional_cloud_requests": 0,
        "synthetic_only": True,
        "publisher_approval": False,
    }


__all__ = ["build_stage77_review"]

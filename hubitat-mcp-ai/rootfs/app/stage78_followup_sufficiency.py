"""Stage 7.8: bounded follow-up evidence sufficiency review (synthetic only).

The authored follow-up proposal is NOT a source of truth. Generic source-type
limits and a human semantic review are displayed after all model reads finish.
No phrase-specific answer matching, second model, hidden-oracle source routing,
device access, or production publication approval.
"""
from __future__ import annotations

from typing import Any

FOLLOWUP_KINDS = frozenset({
    "device_telemetry", "broker_session", "watchdog_history",
    "command_history", "command_execution_receipt", "clock_correlation",
    "controller_decision_log", "other",
})

# Stable source-class limitations, not benchmark-specific answers.  This is
# intentionally an evidence-capability catalogue, not a truth adjudicator.
_SOURCE_LIMITS = {
    "state_report": ("Reported state", "State report alone does not prove physical execution."),
    "command_record": ("Recorded command", "Issuing a command does not prove delivery or actuation."),
    "device_telemetry": ("Device-origin observation",
                         "Device packet alone does not prove clock accuracy or the initiating command."),
    "broker_session": ("Driver/broker transport connection",
                       "Broker connection does not establish device connectivity."),
    "watchdog_tick": ("Periodic watchdog execution",
                      "A tick alone cannot establish the exact time connectivity was lost or first detected."),
    "coverage_gap": ("Recorded absence in observed coverage",
                     "Missing confirmation in a bounded view does not prove global absence."),
    "configuration": ("Stored configuration", "Current settings alone do not establish historic execution."),
    "sensor_report": ("Reported sensor observation",
                      "A sensor report alone does not prove an actuator outcome."),
}
_RECEIPTS = {
    "command_execution_receipt":
        "Execution receipt must link the actual device response to a specific command.",
    "clock_correlation":
        "Clock correlation requires independently established clock offset and timestamp provenance.",
    "controller_decision_log":
        "Decision logs show controller logic, not necessarily hardware actuation.",
    "watchdog_history":
        "Watchdog history can bound detection windows when coverage is continuous; a single tick cannot identify the loss instant.",
    "device_telemetry":
        "Packet sequence may bound observed device state; it does not independently prove causation or clock accuracy.",
    "broker_session":
        "Broker transport health is distinct from proof of an online physical device.",
    "command_history":
        "Command history establishes issued requests, not delivery or execution.",
    "other":
        "Unspecified source capability requires independent human review.",
}


def validate_followup_assessment(value: Any) -> dict:
    """Strict *structure* check; no truth, source validity, or prose grading."""
    keys = {"proposal_kind", "could_establish", "cannot_establish",
            "additional_proof_needed"}
    if type(value) is not dict or set(value) != keys:
        raise ValueError("invalid follow-up assessment fields")
    if type(value["proposal_kind"]) is not str or value["proposal_kind"] not in FOLLOWUP_KINDS:
        raise ValueError("invalid follow-up source class")
    for key in ("could_establish", "cannot_establish", "additional_proof_needed"):
        text = value[key]
        if type(text) is not str or not 8 <= len(text.strip()) <= 210:
            raise ValueError("invalid follow-up limitation declaration")
    return value


def build_stage78_review(case: dict[str, Any], selected: list[str],
                         draft: dict[str, Any]) -> dict[str, Any]:
    if type(case) is not dict or type(selected) is not list or type(draft) is not dict:
        raise ValueError("invalid synthetic follow-up inputs")
    known = {s["id"] for s in case["catalog"]}
    if (len(known) != len(case["catalog"]) or len(selected) > 3
            or len(selected) != len(set(selected))
            or any(type(s) is not str or s not in known for s in selected)):
        raise ValueError("invalid synthetic source selection")
    declaration = draft.get("next_evidence_assessment")
    if declaration is not None:
        validate_followup_assessment(declaration)
    validation = draft.get("_followup_validation", {})
    if type(validation) is not dict or any(
        (k, v) not in (
            ("next_evidence", "invalid_or_missing"),
            ("next_evidence_assessment", "invalid"),
        ) for k, v in validation.items()
    ):
        raise ValueError("invalid internal follow-up validation status")
    next_evidence = draft.get("next_evidence", "")
    valid_next_evidence = (
        type(next_evidence) is str
        and 5 <= len(next_evidence.strip()) <= 220
        and "next_evidence" not in validation
    )
    # Never echo an invalid proposal into a response or reviewer packet.
    if not valid_next_evidence:
        next_evidence = ""
    records = [case["initial"]]
    for source in case["catalog"]:
        if source["id"] in selected:
            records.extend(source["records"])
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("duplicate source record")
    # Retain only unique types and the source IDs that demonstrate them.
    classes = {}
    for record in records:
        category = record.get("kind")
        if category in _SOURCE_LIMITS:
            classes.setdefault(category, []).append(record["id"])
    capabilities = [{
        "record_kind": category, "examined_record_ids": ids,
        "can_establish": _SOURCE_LIMITS[category][0],
        "cannot_alone_establish": _SOURCE_LIMITS[category][1],
    } for category, ids in classes.items()]
    return {
        "schema": "homebrain-stage78-followup-sufficiency.v1",
        "model_proposal": {
            "next_evidence_text": next_evidence,
            "next_evidence_validated_as_bounded_string": valid_next_evidence,
            "field_status": dict(validation),
            "assessment": dict(declaration) if declaration is not None else None,
            "declaration_present": declaration is not None,
            "declaration_is_model_authored_not_proof": True,
        },
        "host_source_capability_reference": capabilities,
        "proposal_kind_host_limit": (
            _RECEIPTS[declaration["proposal_kind"]]
            if declaration else None
        ),
        "human_review": {
            "could_prove_claimed_conclusion": "not_reviewed",
            "acknowledges_evidence_limits": "not_reviewed",
            "additional_verification_is_appropriate": "not_reviewed",
        },
        "reviews_the_meaning_of_model_proposal_automatically": False,
        "no_hidden_reference_data_sent_to_model": True,
        "source_type_capability_is_not_semantic_certification": True,
        "additional_cloud_requests": 0,
        "synthetic_only": True,
        "publisher_approval": False,
    }


__all__ = ["FOLLOWUP_KINDS", "validate_followup_assessment", "build_stage78_review"]

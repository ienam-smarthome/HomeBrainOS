"""Stage 7.9: model-declared proof targets versus source-class capabilities.

Synthetic Stage 6 postrun REVIEW ONLY. This does not interpret the model's
natural-language proposal, inspect unchosen records, advise the source chooser,
or authorize the production publisher. A structured model declaration can lie.
"""
from __future__ import annotations

from typing import Any

# Bounded claim *types*, not scenario-specific strings or text classifiers.
PROOF_TARGETS = frozenset({
    "reported_device_state",
    "broker_transport_status",
    "watchdog_detection_window",
    "exact_connectivity_loss_instant",
    "physical_actuation",
    "specific_command_caused_outcome",
    "source_clock_accuracy",
    "controller_decision",
    "other",
})

# At most a compatible *evidence class*. These pairs do not constitute
# actual proof without source inspection and verification of the result.
_COMPATIBLE_CLASS_TARGETS = {
    "device_telemetry": frozenset({"reported_device_state"}),
    "broker_session": frozenset({"broker_transport_status"}),
    "watchdog_history": frozenset({"watchdog_detection_window"}),
    "command_execution_receipt": frozenset({
        "physical_actuation", "specific_command_caused_outcome",
    }),
    "clock_correlation": frozenset({"source_clock_accuracy"}),
    "controller_decision_log": frozenset({"controller_decision"}),
    "command_history": frozenset({"controller_decision"}),
    "other": frozenset(),
}
# Even a nominally compatible source may require additional origin, coverage,
# continuity, command-binding or clock accuracy evidence.
_ADDITIONAL_PROOF = {
    "reported_device_state":
        "Inspect device-origin packets and their provenance; packet timestamps alone do not prove clock accuracy.",
    "broker_transport_status":
        "Verify the specific broker session; it does not establish physical device connectivity.",
    "watchdog_detection_window":
        "Require consecutive timestamped watchdog checks, full coverage and detection-rule semantics; one tick proves no boundary.",
    "exact_connectivity_loss_instant":
        "A watchdog tick or retrospective offline report cannot pinpoint the actual physical loss instant.",
    "physical_actuation":
        "Verify independently authenticated actuator feedback, not merely issuance of a command.",
    "specific_command_caused_outcome":
        "Verify the command-to-device-outcome binding; observation or command proximity alone is insufficient.",
    "source_clock_accuracy":
        "Verify clock calibration, offset and trusted provenance across all compared clocks.",
    "controller_decision":
        "Verify the actual decision record; decisions do not establish actuator execution.",
    "other": "Specify a testable claim and independently judge appropriate supporting evidence.",
}


def build_stage79_review(draft: dict[str, Any], stage78: dict[str, Any]) -> dict[str, Any]:
    """Grade only *declared* source class versus *declared* proof target."""
    if (type(draft) is not dict or type(stage78) is not dict
            or stage78.get("schema") != "homebrain-stage78-followup-sufficiency.v1"):
        raise ValueError("invalid Stage 7.9 review input")
    model = stage78["model_proposal"]
    declaration = model.get("assessment")
    target = declaration.get("proof_target") if type(declaration) is dict else None
    source_class = declaration.get("proposal_kind") if type(declaration) is dict else None
    if target is not None and target not in PROOF_TARGETS:
        raise ValueError("invalid declared proof target")
    if source_class is not None and source_class not in _COMPATIBLE_CLASS_TARGETS:
        raise ValueError("invalid declared source class")
    if not model.get("next_evidence_validated_as_bounded_string"):
        status = "no_valid_proposal_text"
    elif not source_class or not target:
        status = "not_declared"
    elif target == "other" or source_class == "other":
        status = "unclassified_requires_human"
    elif target in _COMPATIBLE_CLASS_TARGETS[source_class]:
        status = "compatible_class_not_proof"
    else:
        status = "insufficient_source_class_alone"
    return {
        "schema": "homebrain-stage79-declared-proof-target.v1",
        "declared_source_class": source_class,
        "declared_proof_target": target,
        "class_target_status": status,
        "target_evidence_boundary": _ADDITIONAL_PROOF.get(target),
        "source_class_is_proof": False,
        "model_proof_target_matches_authored_next_evidence": "not_reviewed",
        "model_could_establish_text_matches_target": "not_reviewed",
        "model_cannot_establish_text_is_adequately_scoped": "not_reviewed",
        "human_followup_quality_verdict": "not_reviewed",
        "structured_match_is_not_natural_language_verification": True,
        "hidden_reference_oracle_used": False,
        "extra_model_requests": 0,
        "synthetic_postrun_only": True,
        "publisher_approval": False,
    }


__all__ = ["PROOF_TARGETS", "build_stage79_review"]

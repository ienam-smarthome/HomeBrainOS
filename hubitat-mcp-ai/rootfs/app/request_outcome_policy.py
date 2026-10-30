from __future__ import annotations

from collections.abc import Mapping


_OUTCOME_COUNTER_PRECEDENCE: tuple[tuple[str, str], ...] = (
    ("grounding_refusals", "refused"),
    ("mutation_verification_failures", "failed"),
    ("proposal_validation_failures", "failed"),
    ("rule_create_staging_unverified", "unresolved"),
    ("proposal_write_attempts_blocked", "unresolved"),
    ("write_unverified_no_confirmation", "unresolved"),
    ("device_control_failures", "failed"),
    ("request_cancellations", "cancelled"),
    ("device_control_needs_input", "needs_input"),
    ("semantic_needs_input", "needs_input"),
    # An approval prompt is pending work, not successful device actuation.
    # Failure/refusal counters above still outrank this status.
    ("confirmation_queued", "needs_input"),
    ("confirmation_expired", "unresolved"),
    ("device_resolution_ambiguous", "unresolved"),
    ("device_resolution_missing", "unresolved"),
    ("rule_analysis_partial", "unresolved"),
    ("task_evidence_incomplete", "unresolved"),
    ("causal_initiator_unresolved", "unresolved"),
)


def classify_completed_request(counters: Mapping[str, int] | None) -> str:
    """Classify a normally returned request from fixed privacy-safe counters."""

    values = counters or {}
    # The original native write response is missing. Even if a later
    # read-only lookup finds the rule, execution/health was not confirmed.
    # 'Unresolved' is more accurate than either green success or a false
    # assertion that the Hubitat creation failed.
    if (int(values.get("rule_create_timeout_found", 0) or 0) > 0
            or int(values.get("rule_create_timeout_unknown", 0) or 0) > 0):
        return "unresolved"
    for counter, outcome in _OUTCOME_COUNTER_PRECEDENCE:
        if int(values.get(counter, 0) or 0) > 0:
            return outcome
    return "success"


__all__ = ["classify_completed_request"]

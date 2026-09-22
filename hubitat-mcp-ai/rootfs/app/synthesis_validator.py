"""Validate final synthesis without turning validators into answer authors."""

from __future__ import annotations

from typing import Any

from causal_attribution_guard import guard_configuration_only_causal_claim
from causal_timeline import missing_material_timeline_rows
from controller_correlation_guard import guard_controller_boundary_claim
from evidence_source_guard import (
    guard_checked_source_absence_claim,
    guard_positive_source_attribution,
)
from history_cardinality_guard import guard_history_interval_cardinality
from history_temporal_analysis import guard_history_duration_claim
from location_correlation_guard import guard_location_correlation_claim


def validate_synthesis(
    message: str,
    evidence: list[dict[str, Any]],
    *,
    causal: bool = False,
) -> tuple[str, list[str]]:
    """Return a localized deterministic baseline plus issue labels.

    The corrected text is not intended to be the primary answer. It is a factual
    repair baseline for one no-tools model revision. If repair still violates an
    invariant, callers may fall back to this localized version.
    """

    corrected = str(message or "")
    issues: list[str] = []

    corrected, cardinality = guard_history_interval_cardinality(corrected, evidence)
    if cardinality:
        issues.append("history_interval_cardinality")

    corrected, duration_changed = guard_history_duration_claim(corrected, evidence)
    if duration_changed:
        issues.append("history_duration_reliability")

    corrected, correlation_changed = guard_location_correlation_claim(
        corrected, evidence
    )
    if correlation_changed:
        issues.append("location_correlation_consistency")

    corrected, source_changed = guard_checked_source_absence_claim(
        corrected, evidence
    )
    if source_changed:
        issues.append("checked_source_consistency")

    corrected, positive_source_changed = guard_positive_source_attribution(
        corrected, evidence
    )
    if positive_source_changed:
        issues.append("positive_source_attribution")

    if causal:
        corrected, controller_boundary_changed = guard_controller_boundary_claim(
            corrected,
            evidence,
        )
        if controller_boundary_changed:
            issues.append("controller_boundary_direction")

        corrected, configuration_causality_changed = (
            guard_configuration_only_causal_claim(
                corrected,
                evidence,
            )
        )
        if configuration_causality_changed:
            issues.append("configuration_only_causal_attribution")

    missing_rows = (
        missing_material_timeline_rows(corrected, evidence)
        if causal
        else []
    )
    if missing_rows:
        missing_ids = ",".join(
            str(row.get("id") or "?") for row in missing_rows[:8]
        )
        missing_starts = ",".join(
            str(row.get("startNatural") or row.get("start") or "?")
            for row in missing_rows[:8]
        )
        issues.append(
            f"causal_timeline_coverage:{missing_ids}:{missing_starts}"
        )

    return corrected, issues


__all__ = ["validate_synthesis"]

"""Validate final synthesis without turning validators into answer authors."""

from __future__ import annotations

from typing import Any

from causal_timeline import missing_material_timeline_rows
from evidence_source_guard import guard_checked_source_absence_claim
from history_cardinality_guard import guard_history_interval_cardinality
from history_temporal_analysis import guard_history_duration_claim
from location_correlation_guard import guard_location_correlation_claim


def validate_synthesis(
    message: str,
    evidence: list[dict[str, Any]],
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

    missing_rows = missing_material_timeline_rows(corrected, evidence)
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

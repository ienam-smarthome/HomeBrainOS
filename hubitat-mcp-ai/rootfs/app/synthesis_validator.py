"""Validate final synthesis without turning validators into answer authors."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from causal_attribution_guard import (
    guard_configuration_only_causal_claim,
    guard_triggered_listener_causal_claim,
)
from causal_timeline import missing_material_timeline_rows
from controller_correlation_guard import guard_controller_boundary_claim
from evidence_source_guard import (
    guard_checked_source_absence_claim,
    guard_positive_source_attribution,
)
from history_cardinality_guard import guard_history_interval_cardinality
from history_temporal_analysis import guard_history_duration_claim
from location_correlation_guard import guard_location_correlation_claim
from performance_causality_guard import guard_performance_log_causality
from performance_evidence_first import guard_evidence_first_performance
from performance_live_semantic_guard import guard_live_performance_semantics


_PERFORMANCE_REPAIR_ISSUES = {
    "performance_log_causality",
    "performance_live_semantics",
    "performance_evidence_first",
}
_PERFORMANCE_REPAIR_TRACE: ContextVar[tuple[str, ...]] = ContextVar(
    "performance_validation_issue_trace",
    default=(),
)


def _record_performance_repair_issues(issues: list[str]) -> None:
    current = list(_PERFORMANCE_REPAIR_TRACE.get())
    seen = set(current)
    for issue in issues:
        root = str(issue or "").split(":", 1)[0]
        if root in _PERFORMANCE_REPAIR_ISSUES and root not in seen:
            current.append(root)
            seen.add(root)
    _PERFORMANCE_REPAIR_TRACE.set(tuple(current))


def consume_performance_repair_issues() -> tuple[str, ...]:
    """Return and clear request-local fixed performance validator labels."""

    issues = tuple(_PERFORMANCE_REPAIR_TRACE.get())
    _PERFORMANCE_REPAIR_TRACE.set(())
    return issues


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

    corrected, performance_changed = guard_performance_log_causality(
        corrected,
        evidence,
    )
    if performance_changed:
        issues.append("performance_log_causality")

    corrected, live_performance_changed = guard_live_performance_semantics(
        corrected,
        evidence,
    )
    if live_performance_changed:
        issues.append("performance_live_semantics")

    corrected, evidence_first_changed = guard_evidence_first_performance(corrected)
    if evidence_first_changed:
        issues.append("performance_evidence_first")

    if causal:
        corrected, controller_boundary_changed = guard_controller_boundary_claim(
            corrected,
            evidence,
        )
        if controller_boundary_changed:
            issues.append("controller_boundary_direction")

        corrected, triggered_listener_changed = (
            guard_triggered_listener_causal_claim(
                corrected,
                evidence,
            )
        )
        if triggered_listener_changed:
            issues.append("triggered_listener_causal_attribution")

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

    _record_performance_repair_issues(issues)
    return corrected, issues


__all__ = [
    "consume_performance_repair_issues",
    "validate_synthesis",
]

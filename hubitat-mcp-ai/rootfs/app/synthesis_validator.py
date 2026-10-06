"""Validate final synthesis without turning validators into answer authors."""

from __future__ import annotations

from contextvars import ContextVar
import re
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
from performance_diagnostic_format_guard import guard_format_independent_performance_diagnostics
from performance_evidence_first import guard_evidence_first_performance
from performance_evidence_use_guard import guard_direct_performance_evidence_use
from performance_live_semantic_guard import guard_live_performance_semantics
from performance_log_observation_guard import guard_performance_log_observations


_PERFORMANCE_REPAIR_ISSUES = {
    "performance_log_causality",
    "performance_live_semantics",
    "performance_evidence_first",
    "performance_log_observation",
}
_PERFORMANCE_REPAIR_TRACE: ContextVar[tuple[str, ...]] = ContextVar(
    "performance_validation_issue_trace",
    default=(),
)
_DURATION_REQUEST_RE = re.compile(
    r"\bhow\s+long\b"
    r"|\bduration\b"
    r"|\btotal\s+(?:on\s+)?time\b"
    r"|\bhow\s+much\s+time\b"
    r"|\bhow\s+many\s+(?:seconds?|minutes?|hours?)\b",
    re.IGNORECASE,
)
_DURATION_GUARD_SEED = "The device was on for a total of 0 seconds."
_RECORDED_EVENT_ESTIMATE_RE = re.compile(
    r"\b(?:these|the)\s+(?:times|timestamps)\s+are\s+estimates\s+based\s+on\s+recorded\s+events\b",
    re.IGNORECASE,
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
    original_user: str = "",
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
    if not duration_changed and _DURATION_REQUEST_RE.search(str(original_user or "")):
        # The ordinary duration guard corrects a wrong numeric claim. A model can
        # also omit duration entirely (for example, list five ON timestamps for a
        # "how long" question). Seed the same deterministic guard only when the
        # original user explicitly requested a duration, so the evidence-backed
        # temporal total cannot disappear during synthesis.
        requested_duration, requested_changed = guard_history_duration_claim(
            _DURATION_GUARD_SEED,
            evidence,
        )
        if requested_changed:
            corrected = requested_duration
            duration_changed = True
    if duration_changed:
        issues.append("history_duration_reliability")

    # Recorded event timestamps are direct observations from the returned rows.
    # Unverified source integrity limits completeness/continuity claims; it does
    # not turn a timestamp that is actually present into an estimate.
    timestamp_semantics_changed = bool(_RECORDED_EVENT_ESTIMATE_RE.search(corrected))
    if timestamp_semantics_changed:
        corrected = _RECORDED_EVENT_ESTIMATE_RE.sub(
            "These timestamps are recorded event observations",
            corrected,
        )
        issues.append("history_recorded_timestamp_semantics")

    corrected, correlation_changed = guard_location_correlation_claim(corrected, evidence)
    if correlation_changed:
        issues.append("location_correlation_consistency")

    corrected, source_changed = guard_checked_source_absence_claim(corrected, evidence)
    if source_changed:
        issues.append("checked_source_consistency")

    corrected, positive_source_changed = guard_positive_source_attribution(corrected, evidence)
    if positive_source_changed:
        issues.append("positive_source_attribution")

    corrected, log_observation_changed = guard_performance_log_observations(corrected, evidence)
    if log_observation_changed:
        issues.append("performance_log_observation")

    # One format-independent adaptive diagnostic guard owns target context,
    # semantic child roles, cadence/source integrity, cluster-rate boundaries and
    # mechanism-specific action gating. The older numbered-heading guard is no
    # longer chained afterwards, avoiding a second shape-dependent rewrite pass.
    corrected, format_independent_changed = guard_format_independent_performance_diagnostics(
        corrected,
        evidence,
    )
    if format_independent_changed:
        issues.append("performance_evidence_first")

    corrected, performance_changed = guard_performance_log_causality(corrected, evidence)
    if performance_changed:
        issues.append("performance_log_causality")

    corrected, live_performance_changed = guard_live_performance_semantics(corrected, evidence)
    if live_performance_changed:
        issues.append("performance_live_semantics")

    corrected, evidence_first_changed = guard_evidence_first_performance(corrected, evidence)
    if evidence_first_changed and "performance_evidence_first" not in issues:
        issues.append("performance_evidence_first")

    # 0.16.86 final evidence-use integrity runs after the generic semantic stack so
    # later repairs cannot erase literal WARN evidence, conflate a long-running
    # operation with a connectivity failure, or turn a same-second cluster into a
    # prescriptive staggering/frequency recommendation.
    corrected, direct_evidence_changed = guard_direct_performance_evidence_use(
        corrected,
        evidence,
    )
    if direct_evidence_changed and "performance_evidence_first" not in issues:
        issues.append("performance_evidence_first")

    if causal:
        corrected, controller_boundary_changed = guard_controller_boundary_claim(corrected, evidence)
        if controller_boundary_changed:
            issues.append("controller_boundary_direction")

        corrected, triggered_listener_changed = guard_triggered_listener_causal_claim(corrected, evidence)
        if triggered_listener_changed:
            issues.append("triggered_listener_causal_attribution")

        corrected, configuration_causality_changed = guard_configuration_only_causal_claim(
            corrected,
            evidence,
        )
        if configuration_causality_changed:
            issues.append("configuration_only_causal_attribution")

    missing_rows = missing_material_timeline_rows(corrected, evidence) if causal else []
    if missing_rows:
        missing_ids = ",".join(str(row.get("id") or "?") for row in missing_rows[:8])
        missing_starts = ",".join(
            str(row.get("startNatural") or row.get("start") or "?")
            for row in missing_rows[:8]
        )
        issues.append(f"causal_timeline_coverage:{missing_ids}:{missing_starts}")

    _record_performance_repair_issues(issues)
    return corrected, issues


__all__ = [
    "consume_performance_repair_issues",
    "validate_synthesis",
]

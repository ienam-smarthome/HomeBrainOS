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
    r"\b(?:(?:these|the)\s+(?:times|timestamps)|these)\s+are\s+estimates\s+based\s+on\s+recorded\s+events\b",
    re.IGNORECASE,
)


def guard_bounded_log_absence_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Do not promote a latest-N log sample into a complete no-failure verdict.

    This is deliberately source-agnostic: any read of hub_get_logs that returns
    its full requested limit has unknown earlier-event coverage, even when its
    transport succeeded and a model sees recent INFO/online observations.
    """
    bounded: list[tuple[int, str]] = []
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        args = row.get("arguments")
        if not isinstance(args, dict):
            continue
        operation = str(row.get("sub_tool") or args.get("tool") or "")
        if operation != "hub_get_logs":
            continue
        request = args.get("args") if isinstance(args.get("args"), dict) else args
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        try:
            limit = int(request.get("limit") or 0)
            count = int(details.get("logCount") or len(details.get("logs") or []))
        except (TypeError, ValueError):
            continue
        if limit > 0 and count >= limit:
            bounded.append((limit, str(request.get("since") or "requested window")))
    if not bounded:
        return str(message or ""), False

    draft = str(message or "")
    # Scope only strong absence / continuous-health claims, not sensible
    # prose such as 'no evidence in the returned 100-row sample'.
    no_fail = re.compile(
        r"(?i)\bthere\s+(?:is|was)\s+\*{0,2}no\s+evidence\s+of\s+"
        r"(?:any\s+)?(?:polling\s+)?(?:failures?|errors?|timeouts?)\*{0,2}"
    )
    unqualified_health = re.compile(
        r"(?i)\b(?:integration\s+is\s+currently\s+healthy\s+and\s+polling\s+normally"
        r"|no\s+polling\s+failures\s+in\s+the\s+(?:last|past)\s+\d+\s*hours?)\b"
    )
    if not no_fail.search(draft) and not unqualified_health.search(draft):
        return draft, False
    corrected = no_fail.sub(
        "recent successful activity, but the sampled logs cannot rule out earlier failures",
        draft,
    )
    corrected = unqualified_health.sub(
        "integration has recent successful telemetry, with full-window health unverified",
        corrected,
    )
    limit, window = min(bounded, key=lambda item: item[0])
    qualifier = (
        f"**Log coverage limitation:** The {limit}-row log request for {window} "
        "reached its limit. Recent successes do not prove that no earlier "
        "polling or integration failures occurred during that period."
    )
    if "log coverage limitation" not in corrected.casefold():
        corrected = qualifier + "\n\n" + corrected
    return corrected, corrected != draft


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

    corrected, log_coverage_changed = guard_bounded_log_absence_claim(
        corrected, evidence
    )
    if log_coverage_changed:
        issues.append("bounded_log_absence_claim")

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
    # not turn a timestamp that is actually present into an estimate. The deictic
    # "These are estimates ..." form is included because models may refer back to
    # an immediately preceding list of recorded event times without repeating the
    # noun "times" or "timestamps".
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

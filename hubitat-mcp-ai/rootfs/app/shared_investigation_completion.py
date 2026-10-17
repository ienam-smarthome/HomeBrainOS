"""One read-only final investigation assessment for every API execution route.

This runs *after* the native, deterministic, and specialist paths finish.
It never executes a tool, changes a device, invents evidence, or converts
source-class coverage into proof of an upstream cause. Partial coverage is
visible regardless of which route produced the original answer.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from general_evidence_completion import assess_task_source_coverage
from adaptive_investigation_policy import source_evidence_request
from source_evidence_metadata import contiguous_source_coverage
from source_analysis_completion import (
    source_analysis_failed, source_failure_summary, source_method_claim_gap,
)
from typed_device_history_evidence import (
    normalize_target_device_history, render_target_device_evidence_answer,
)
from recorded_telemetry_freshness import (
    assess_recorded_telemetry_freshness, render_temporal_qualification,
    reconcile_telemetry_answer, render_command_only_evidence_answer,
)
from investigation_intelligence import assess_investigation, plan_investigation
from telemetry_clock_consistency import (
    assess_telemetry_clock_consistency,
    render_telemetry_clock_qualification,
)
from investigation_policy import is_causal_investigation
from system_audit_coverage import assess_system_audit_sources

TELEMETRY_KINDS = ("device_state", "device_history", "device_logs")
CAUSAL_KINDS = ("device_history", "command_history")
SCHEDULER_KINDS = ("scheduled_jobs",)


class _CoverageOutcome:
    """Preserve arbitrary specialist outcome fields without copying or casting."""

    def __init__(self, original: Any, coverage: dict[str, Any],
                 metrics: dict[str, Any], message: str) -> None:
        self._original = original
        self.investigation_coverage = coverage
        self.metrics = metrics
        self.message = message

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


def _historical_integrity_issues(evidence: list[dict[str, Any]]) -> list[str]:
    """Explicit bounded source-health flags; no assertions about missing rows."""
    problems: list[str] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        if details.get("historySourceIntegrityVerified") is False:
            problems.append(
                "Event-history completeness is not independently verified."
            )
        if details.get("observedEventsTruncated") is True:
            problems.append(
                "Returned device events were truncated; older boundaries may be missing."
            )
        if details.get("boundaryEventsTruncated") is True:
            problems.append(
                "Returned boundary events were truncated."
            )
    return list(dict.fromkeys(problems))


def _known_source_requirements(domain: str) -> tuple[str, ...]:
    if domain == "device_telemetry":
        return TELEMETRY_KINDS
    if domain == "scheduler_ownership":
        return SCHEDULER_KINDS
    if domain == "manual_motion_lockout":
        return ("device_history", "app_logs")
    return ()


def _safe_metrics(outcome: Any, *, partial: bool) -> dict[str, Any]:
    """Never clobber prior failures or mutate an existing metrics snapshot."""
    original = getattr(outcome, "metrics", None)
    metrics = deepcopy(original) if isinstance(original, dict) else {}
    counters = metrics.get("counters")
    if not isinstance(counters, dict):
        counters = {}
        metrics["counters"] = counters
    counters["shared_completion_checked"] = int(
        counters.get("shared_completion_checked") or 0
    ) + 1
    if partial:
        counters["shared_completion_partial"] = int(
            counters.get("shared_completion_partial") or 0
        ) + 1
        if metrics.get("outcome") in (None, "success"):
            metrics["outcome"] = "unresolved"
    return metrics


def apply_shared_investigation_completion(outcome: Any, request: str) -> Any:
    """Attach a structured assessment before /api/ask or /api/chat serialization.

    This checkpoint is independent of the path's early return and cannot make
    calls after the original agent has finished. A missing source is marked as
    incomplete, never automatically fabricated or treated as a Hubitat fault.
    """
    if str(getattr(outcome, "request_class", "")) != "live-read":
        return outcome
    goal = plan_investigation(request)
    # The broad legacy classifier also matches prospective rule "triggers".
    # This final historical gate must not turn proposal-only read requests into
    # historical-cause investigations merely for mentioning rule triggers.
    request_text = str(request or "").strip().casefold()
    causal = is_causal_investigation(request) and (
        request_text.endswith("?") or request_text.startswith((
            "why ", "investigate ", "explain ", "analyse ", "analyze ",
            "diagnose ", "determine ", "what caused ", "what triggered ",
        ))
    )
    prior = getattr(outcome, "investigation_coverage", None)
    evidence = list(getattr(outcome, "evidence", []) or [])
    # Code-reading obligations are not historical command-provenance
    # obligations. A successful config read or empty source read is NOT
    # source-code evidence and cannot close the actual objective.
    if source_evidence_request(request):
        source = assess_task_source_coverage(("source_code",), evidence)
        found = source.sources_checked
        direct_segments = contiguous_source_coverage(evidence)
        # One direct source read must not eclipse a later complete workbench
        # retrieval. Both source paths are independently verifiable: raw
        # gateway receipts carry individual spans, while the bounded local
        # workbench records its internally checked pages and declared total.
        workbench_details = [
            row["details"] for row in evidence
            if isinstance(row, dict) and row.get("success") is True
            and row.get("tool") == "homebrain_read_groovy_source"
            and isinstance(row.get("details"), dict)
            and row["details"].get("sourceRetrieved") is True
        ]

        def _workbench_complete(detail: dict[str, Any]) -> bool:
            observed = detail.get("verifiedCharacters")
            declared = detail.get("declaredTotalCharacters")
            pages = detail.get("verifiedPages")
            return bool(
                detail.get("fullImplementationVerified") is True
                and isinstance(observed, int) and not isinstance(observed, bool)
                and isinstance(declared, int) and not isinstance(declared, bool)
                and isinstance(pages, int) and not isinstance(pages, bool)
                and observed > 0 and observed == declared and pages > 0
            )

        # Prefer a fully checked workbench result, then the greatest observed
        # partial coverage. An earlier failed ID lookup cannot override the
        # final verified read for the installed app.
        local_detail = max(
            workbench_details,
            key=lambda detail: (
                _workbench_complete(detail),
                detail.get("verifiedCharacters")
                if type(detail.get("verifiedCharacters")) is int else 0,
            ),
            default=None,
        )
        local_complete = bool(
            local_detail is not None and _workbench_complete(local_detail)
        )
        segments = direct_segments
        auxiliary_coverage: dict[str, Any] = {}
        if local_detail is not None:
            reported_pages = local_detail.get("verifiedPages")
            reported_total = local_detail.get("declaredTotalCharacters")
            reported_chars = local_detail.get("verifiedCharacters")
            workbench_segments = {
                "fullImplementationVerified": local_complete,
                "coverage": "complete" if local_complete else "partial",
                "chunksObserved": reported_pages if type(reported_pages) is int else 0,
                "verifiedCharacters": reported_chars
                if type(reported_chars) is int else None,
                "totalLength": reported_total
                if type(reported_total) is int else None,
                "validationMethod": "local-source-workbench",
            }
            if local_complete or not direct_segments["fullImplementationVerified"]:
                segments = workbench_segments
                if direct_segments.get("chunksObserved", 0):
                    auxiliary_coverage["directChunkCoverage"] = direct_segments
            else:
                auxiliary_coverage["workbenchChunkCoverage"] = workbench_segments
        full = found and (
            direct_segments["fullImplementationVerified"] or local_complete
        )
        complete_requested = bool(re.search(
            r"(?i)\b(?:entire|complete|full(?:\s+source|\s+implementation)?|"
            r"all\s+(?:relevant\s+)?code\s+paths)\b", request,
        ))
        draft_message = str(getattr(outcome, "message", "") or "")
        synthesis_failed = source_analysis_failed(draft_message)
        method_gap = source_method_claim_gap(draft_message)
        coverage = {
            "domain": "source_code",
            "status": ("full-source-observed" if full else
                       "source-segment-observed" if found else "source-unverified"),
            "evidenceComplete": found,
            # Source retrieval is not completion of the requested
            # method-and-runtime investigation if synthesis failed.
            "objectiveSatisfied": bool(
                found and (full or not complete_requested)
                and not synthesis_failed and not method_gap
            ),
            "analysisAnswerVerified": not synthesis_failed,
            "analysisStatus": (
                "synthesis-failed-source-observed" if synthesis_failed
                else "model-admitted-relevant-methods-not-reviewed"
                if method_gap else "model-answer-present-not-method-certified"
            ),
            "fullSourceRequested": complete_requested,
            "sourceCoverage": source.to_dict(),
            "fullImplementationVerified": bool(full),
            "chunkCoverage": segments,
            **auxiliary_coverage,
            "methodBodyCoverage": {
                "status": (
                    "model-admitted-unreviewed-methods" if method_gap
                    else "not-certified-by-source-span-receipts"
                ),
                "note": "Whole-file retrieval does not independently certify "
                        "that every relevant method body, caller, or runtime "
                        "branch was reviewed by the model.",
            },
            "completionNote": (
                "Source text spans the declared full implementation length "
                "with no observed offset gap. Method and runtime coverage "
                "remain separate evidence obligations."
                if full else
                "Some source text was read, but full implementation coverage "
                "was not established. Do not infer that an unseen method is absent."
                if found else
                "No raw implementation source was verified this turn. "
                "Configuration, discovery and cached file references do not count."
            ),
        }
        message = (
            source_failure_summary(evidence) if synthesis_failed
            else draft_message
        )
        if not found:
            message += (
                "\n\n**Source evidence unavailable:** The current investigation "
                "did not retrieve verifiable Groovy implementation text. "
                "Its runtime method and expiry semantics remain unverified."
            )
        elif not full:
            message += (
                "\n\n**Partial source coverage:** Some implementation text "
                "was retrieved, but continuous coverage of the installed source "
                "was not verified. Unseen methods and code-level root causes "
                "must remain unverified."
            )
        return _CoverageOutcome(
            outcome, coverage,
            _safe_metrics(outcome, partial=(
                synthesis_failed or method_gap or not found
                or (complete_requested and not full)
            )),
            message,
        )
    # System-wide section and performance source checks have different proof
    # obligations from an individual historical ON/OFF investigation.
    system_audit = assess_system_audit_sources(
        str(getattr(outcome, "route", "") or ""), request, evidence,
    )
    if system_audit is not None:
        is_partial = bool(system_audit.pop("partial"))
        system_audit.pop("missing", None)
        metrics = _safe_metrics(outcome, partial=is_partial)
        message = str(getattr(outcome, "message", "") or "")
        missing = system_audit["sourceCoverage"]["missingSourceKinds"]
        if missing:
            message += (
                "\n\n**Audit source limitations:** These components were not "
                "checked in this request: " + ", ".join(missing)
                + ". Do not infer that their devices or automations are healthy."
            )
        return _CoverageOutcome(outcome, system_audit, metrics, message)
    if goal is None and not causal and not isinstance(prior, dict):
        return outcome
    if goal is not None:
        domain = goal.domain
        required = _known_source_requirements(domain)
    else:
        domain = "causal_provenance"
        required = CAUSAL_KINDS

    if isinstance(prior, dict):
        existing = deepcopy(prior)
    elif goal is not None:
        existing = assess_investigation(goal, evidence)
    else:
        existing = {}
    source_coverage = assess_task_source_coverage(required, evidence)
    integrity = _historical_integrity_issues(evidence)
    missing = list(source_coverage.missing)

    # Provenance is a separate proof obligation from checking a relevant
    # source. If the goal has a domain-specific observed-requirements contract
    # we retain it, rather than upgrading to complete when sources were read.
    domain_proof_complete = (
        existing.get("evidenceComplete") is True
        if "evidenceComplete" in existing else None
    )
    partial = bool(missing or integrity or domain_proof_complete is False)
    if causal:
        # A reporting bridge and a switch state are NOT evidence that an
        # upstream initiating command/automation was proven. We can certify
        # source classes, not resolve the causal question generically.
        partial = True

    coverage = {
        **existing,
        "domain": domain,
        "status": "partial-evidence" if partial else "source-checks-complete",
        "evidenceComplete": False if partial else domain_proof_complete,
        # A read-source category being checked does not answer a causal
        # question. Report these as separate, independently meaningful
        # dimensions so a successful probe cannot masquerade as diagnosis.
        "sourceChecksComplete": source_coverage.sources_checked,
        "rootCauseVerified": (
            False if domain == "device_telemetry" or causal else None
        ),
        "assessmentScope": "all-api-routes-read-only",
        "sourceCoverage": source_coverage.to_dict(),
        "sourceIntegrityWarnings": integrity,
        "causalInitiatorVerified": None,
        "completionNote": (
            "A successful tool request proves that a source was queried, not "
            "that the device was responsive or an upstream action occurred."
        ),
    }
    metrics = _safe_metrics(outcome, partial=partial)
    message = str(getattr(outcome, "message", "") or "")
    if domain == "device_telemetry":
        clock_check = assess_telemetry_clock_consistency(evidence)
        if clock_check is not None:
            coverage["telemetryClockConsistency"] = clock_check
            if clock_check["sourcesAgree"] is False:
                # This claim boundary must remain visible even when a
                # specialist finalizer replaces a model's original prose.
                if metrics.get("outcome") in (None, "success"):
                    metrics["outcome"] = "unresolved"
        # A direct device-ID-scoped mixed history is authoritative for which
        # Hubitat command/state events were *returned*. It can contain one
        # historical device-attributed attribute amongst many commands: the
        # earlier command-only summariser intentionally missed this case.
        normalized = normalize_target_device_history(evidence)
        if normalized is not None:
            coverage["normalizedDeviceHistory"] = normalized
            coverage["answerProjection"] = "target-scoped-mixed-event-evidence"
            message = render_target_device_evidence_answer(
                evidence, normalized,
            )
            metrics.setdefault("counters", {})[
                "typed_device_history_projections"
            ] = int(metrics["counters"].get(
                "typed_device_history_projections"
            ) or 0) + 1
            # A mixed sample does not certify watchdog evidence, lastSeen
            # timestamps, command acknowledgments or physical connectivity.
            if metrics.get("outcome") in (None, "success"):
                metrics["outcome"] = "unresolved"
        else:
            temporal = assess_recorded_telemetry_freshness(evidence)
            if temporal is not None:
                coverage["telemetryTimestampAssessment"] = temporal
                original_message = message
                projected = render_command_only_evidence_answer(
                    original_message, evidence, temporal,
                )
                if projected is not None:
                    # A command-only window has no physical lastSeen proof; rebuild
                    # the high-risk activity/conclusion sections from typed rows.
                    message, reconciled = projected, projected != original_message
                    coverage["answerProjection"] = "bounded-command-only-evidence"
                else:
                    message, reconciled = reconcile_telemetry_answer(
                        original_message, temporal,
                    )
                if reconciled:
                    counters = metrics.setdefault("counters", {})
                    counters["telemetry_claims_reconciled"] = int(
                        counters.get("telemetry_claims_reconciled") or 0
                    ) + 1
                    coverage["telemetryClaimsReconciled"] = True
                message += "\n\n" + render_temporal_qualification(
                    temporal, original_message,
                )
    if domain == "device_telemetry":
        clock_check = coverage.get("telemetryClockConsistency")
        if isinstance(clock_check, dict) and clock_check.get("sourcesAgree") is False:
            message = (
                render_telemetry_clock_qualification(clock_check)
                + "\n\n" + message
            )
    # Preserve explicitly requested, model-proposed alternatives even when
    # the safety-oriented typed evidence renderer replaces the model's prose.
    # A successful source-class read is NOT support, contradiction or proof
    # of an individual proposed explanation.
    proposed = coverage.get("hypothesisComparisons")
    if isinstance(proposed, list) and proposed:
        comparisons: list[str] = []
        for candidate in proposed[:3]:
            if not isinstance(candidate, dict):
                continue
            explanation = str(candidate.get("candidate") or "").strip()[:140]
            question = str(candidate.get("discriminating_question") or "").strip()[:180]
            checked = candidate.get("source_state") == "source-class-checked-verdict-unverified"
            required_origin = candidate.get("required_origin")
            if required_origin in ("upstream", "physical"):
                source_status = (
                    "Hubitat source category queried, but independent "
                    + required_origin + " evidence has NOT been verified"
                    if checked else
                    "requires independent " + required_origin
                    + " evidence; source category not yet checked"
                )
            elif checked:
                source_status = "relevant source class checked; discriminator and hypothesis still unverified"
            else:
                source_status = "relevant source class not checked"
            if explanation and question:
                comparisons.append(
                    "- **Possible explanation:** " + explanation
                    + "\n  **Distinguishing evidence:** " + question
                    + " (" + source_status + ")."
                )
        if len(comparisons) >= 2:
            message += (
                "\n\n**Competing explanations (provisional; not a causal verdict):**\n"
                + "\n".join(comparisons)
            )
    # Keep successful Groovy/driver-source retrieval visible after the safe
    # target-history projection replaces free-form model prose. This attests
    # only that source text was retrieved, never that the method's behaviour,
    # live MQTT transport or physical root cause was proven.
    if domain == "device_telemetry":
        source_receipts: list[dict[str, Any]] = []
        for row in evidence:
            if not isinstance(row, dict) or row.get("success") is not True:
                continue
            if row.get("sub_tool") != "hub_get_source":
                continue
            details = row.get("details")
            if not isinstance(details, dict) or details.get("sourceRetrieved") is not True:
                continue
            length, total = details.get("chunkLength"), details.get("totalLength")
            code_id = details.get("sourceCodeId")
            if (type(length) is int and type(total) is int
                    and total > 0 and 0 < length <= total
                    and isinstance(code_id, (int, str))
                    and str(code_id).isdigit()):
                source_receipts.append({
                    "codeId": str(code_id)[:20],
                    "verifiedOffsetUnits": length,
                    "declaredTotalOffsetUnits": total,
                    "fullSourceAtRead": (
                        details.get("offset") == 0 and length == total
                    ),
                    "methodBehaviourVerified": False,
                })
        if source_receipts:
            # The most informative successful read is retained; duplicates
            # must not inflate independent evidence claims.
            selected = max(source_receipts, key=lambda item: (
                item["fullSourceAtRead"], item["verifiedOffsetUnits"]
            ))
            coverage["additionalSourceCodeEvidence"] = selected
            message += (
                "\n\n**Retrieved implementation evidence:** "
                "Code ID " + selected["codeId"] + " — "
                + str(selected["verifiedOffsetUnits"]) + "/"
                + str(selected["declaredTotalOffsetUnits"])
                + " source-offset units returned. This proves source retrieval "
                  "only; a root cause requires analysing relevant method "
                  "branches and corroborating runtime/upstream evidence."
            )
    # The final reported outcome is separate from source/category completeness.
    # A successful source read must never convert an unresolved diagnosis to a
    # resolved physical/device cause.
    coverage["questionResolved"] = (
        False if metrics.get("outcome") == "unresolved" or domain == "device_telemetry"
        else None
    )
    if partial:
        limitations: list[str] = []
        if missing:
            limitations.append("unchecked source classes: " + ", ".join(missing))
        if integrity:
            limitations.append("unverified/truncated historical coverage")
        if causal:
            limitations.append(
                "upstream initiator not independently established by the "
                "shared source-class assessment"
            )
        if domain_proof_complete is False and not missing and not integrity and not causal:
            limitations.append(
                "one or more required domain-specific observations remain unverified"
            )
        if limitations:
            message += (
                "\n\n**Investigation completeness: partial.** "
                + "; ".join(limitations)
                + ". The reported observations remain available, but the "
                  "unresolved points must not be treated as confirmed."
            )
    return _CoverageOutcome(outcome, coverage, metrics, message)


__all__ = ["apply_shared_investigation_completion"]

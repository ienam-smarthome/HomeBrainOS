"""Explicit opt-in Investigation V2 model+MCP evaluation seam.

NOT registered with production chat routes, Home Assistant startup or any
background monitor. Uses the EXISTING provider chat callable, existing MCP
client and ToolExecutor. The caller must supply verified target IDs and
explicitly enable this run. No writes, no model-native tool calls.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from mcp_client import HubitatMCPClient
from tool_executor import ToolExecutor

from .model_adapter import Chat, V2ModelProposer
from .read_loop import InvestigationResult, run_read_only_investigation
from .synthesis import GroundedAnswer, synthesize_with_chat, assemble_grounded_answer
from .atomic_claims import ClaimReview, synthesize_atomic_with_chat
from .narrative import NarrativeAudit
from .temporal_scope import IncidentWindow
from .investigation_report import format_investigation_report
from .forensic_metrics import forensic_metrics
from .state_duration import is_state_duration_request, format_state_duration_report
from .factual_report import factual_report


@dataclass(frozen=True)
class V2Evaluation:
    investigation: InvestigationResult
    answer: GroundedAnswer
    atomic_claim_review: ClaimReview | None = None
    narrative_audit: NarrativeAudit | None = None
    report: str = ""
    incident_window: IncidentWindow | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation": self.investigation.to_dict(),
            "answer": {
                "text": self.answer.text,
                "displayed_record_ids": list(self.answer.displayed_record_ids),
                "omitted_material_record_ids": list(self.answer.omitted_material_record_ids),
                "validation_issues": list(self.answer.validation_issues),
                "root_cause_verified": self.answer.root_cause_verified,
                "human_review_required": self.answer.human_review_required,
            },
            "production_answer_used": False,
            "report": {"text": self.report or self.answer.text,
                       "technical_answer_retained": True},
            "forensic_metrics": forensic_metrics(self.investigation.case, self.incident_window),
            "atomic_claim_review": (self.atomic_claim_review.to_dict()
                                    if self.atomic_claim_review else None),
            "narrative_audit": ({
                "approved": len(self.narrative_audit.approved),
                "rejected": [x.reason for x in self.narrative_audit.rejected],
                "used_fallback": self.narrative_audit.used_fallback,
            } if self.narrative_audit else None),
        }


async def evaluate_v2_with_model(
    *,
    explicitly_authorised: bool = False,
    question: str,
    chat: Chat,
    mcp: HubitatMCPClient,
    executor: ToolExecutor,
    verified_entity_ids: Iterable[str],
    initial_receipts: Iterable[Mapping[str, Any]] = (),
    max_rounds: int = 3,
    max_total_reads: int = 8,
    enable_atomic_claim_validation: bool = False,
    enable_evidence_narrative: bool = False,
    incident_window: IncidentWindow | None = None,
    planning_timeout_seconds: float = 60.0,
    bootstrap_source_identity: bool = True,
    bootstrap_device_context: bool = False,
    verified_device_label: str | None = None,
    force_duration_mode: bool = False,
    semantic_unavailable_reason: str | None = None,
    factual_objective: str | None = None,
) -> V2Evaluation:
    """Run one explicit read-only experiment with the configured chat provider.

    Cannot run via default agent call. Proposals from the provider are checked
    by the host and do not confer target identity or tool authorization.
    """
    if explicitly_authorised is not True:
        raise PermissionError("Investigation V2 requires explicit experiment opt-in")
    if enable_evidence_narrative is True and enable_atomic_claim_validation is not True:
        raise ValueError("Evidence narrative requires atomic claim verification")
    if executor.mcp is not mcp:
        raise ValueError("MCP client/executor mismatch")
    tools = await mcp.list_tools()
    resolved_ids = tuple(verified_entity_ids)
    if factual_objective not in (None, "status", "history"):
        raise ValueError("Invalid factual objective")
    if factual_objective is not None and semantic_unavailable_reason is not None:
        raise ValueError("Conflicting factual and semantic fallback objectives")
    if semantic_unavailable_reason is not None:
        # The first model call already failed before investigation. Do not
        # repeatedly invoke the unavailable provider or invent an intent.
        # Host-gated context reads can still establish limited source facts.
        if semantic_unavailable_reason not in ("timeout", "invalid_plan", "provider_failure"):
            raise ValueError("Invalid semantic fallback reason")
        if len(resolved_ids) != 1:
            raise ValueError("Semantic fallback requires one verified device")

        async def propose(_case, _round):
            return {"hypotheses": [], "reads": [], "finish": True}
    elif factual_objective is not None:
        async def propose(_case, _round):
            raise AssertionError("Factual evidence must not invoke model planning")
    else:
        propose = V2ModelProposer(chat, tools, verified_entity_ids=resolved_ids,
                                  incident_window=incident_window)
    duration_intent = bool(incident_window is not None and
                           (force_duration_mode or is_state_duration_request(
                               question, incident_window)))
    result = await run_read_only_investigation(
        question=question, mcp=mcp, executor=executor, propose=propose,
        verified_entity_ids=resolved_ids,
        initial_receipts=initial_receipts,
        max_rounds=max_rounds, max_total_reads=max_total_reads,
        incident_window=incident_window,
        planning_timeout_seconds=planning_timeout_seconds,
        bootstrap_source_identity=bootstrap_source_identity,
        bootstrap_device_context=bootstrap_device_context,
        stop_after_incident_history=duration_intent,
        factual_objective=factual_objective,
    )
    if factual_objective is not None:
        narrative, displayed = factual_report(result.case, factual_objective,
                                               verified_device_label)
        grounded = GroundedAnswer(
            text=narrative, displayed_record_ids=displayed,
            omitted_material_record_ids=(),
            validation_issues=("factual_read_only_source_snapshot",
                               "historical_source_completeness_unverified")
            if factual_objective == "history" else
                              ("factual_read_only_source_snapshot",),
        )
        return V2Evaluation(
            investigation=result, answer=grounded,
            report=narrative, incident_window=incident_window,
        )
    if semantic_unavailable_reason is not None:
        # Do not upgrade this best-effort source collection into a model-based
        # investigation or pretend that the user intent was classified.
        result = replace(result, stopped_because="semantic_intent_unavailable")
        raw = assemble_grounded_answer(
            result.case, result.hypotheses,
            {"selected_record_ids": [r.record_id for r in result.case.records],
             "hypothesis_order": []},
        )
        issue = "semantic_plan_" + semantic_unavailable_reason
        answer = replace(
            raw,
            validation_issues=(*raw.validation_issues, issue,
                               "semantic_intent_unverified_host_only"),
        )
        report = (
            "**Limited evidence recovery — AI intent planning unavailable**\n"
            "The original question was not semantically classified. "
            "The single named device was independently verified against "
            "Hubitat inventory; only safe, read-only source evidence follows. "
            "This is not a full investigation or a verified root cause.\n\n"
            + format_investigation_report(
                result.case, result.hypotheses,
                result.stopped_because, incident_window,
            )
        )
        return V2Evaluation(
            investigation=result, answer=answer,
            report=report, incident_window=incident_window,
        )
    if duration_intent and incident_window is not None:
        # Calculations from validated event-time state transitions belong to
        # the host, not a generative model. Unknown boundaries remain unknown.
        narrative, displayed_ids = format_state_duration_report(
            result.case, incident_window, device_label=verified_device_label,
        )
        grounded = GroundedAnswer(
            text=narrative, displayed_record_ids=displayed_ids,
            omitted_material_record_ids=(),
            validation_issues=("state_duration_source_completeness_unverified",)
            if not any(c.source_complete is True for c in result.case.coverage)
            else (),
        )
        return V2Evaluation(
            investigation=result, answer=grounded,
            report=narrative, incident_window=incident_window,
        )
    # With read-time status but no authenticated timestamped records, the
    # host already knows every reportable observation. Another model-driven
    # atomic-claim pass cannot create source record IDs; it previously spent
    # expensive reasoning rounds making unsupported radio/mesh hypotheses.
    # Render the allowlisted source snapshot deterministically instead.
    if result.case.device_snapshots and not result.case.records:
        grounded = assemble_grounded_answer(
            result.case, [],
            {"selected_record_ids": [], "hypothesis_order": []},
        )
        grounded = replace(
            grounded, validation_issues=(*grounded.validation_issues,
                                        "current_snapshot_without_timed_history",
                                        "atomic_claim_selection_not_applicable"),
        )
        return V2Evaluation(
            investigation=result, answer=grounded,
            report=format_investigation_report(
                result.case, [], result.stopped_because, incident_window,
            ),
            incident_window=incident_window,
        )

    # If planning itself timed out or the transport failed, don't issue more
    # large model calls for atomic selection and repair. The host can still
    # render every authenticated event with no invented causal hypothesis.
    if result.stopped_because in ("planning_timeout", "planning_unavailable"):
        kept = assemble_grounded_answer(
            result.case, result.hypotheses,
            {"selected_record_ids": [r.record_id for r in result.case.records],
             "hypothesis_order": [h.hypothesis_id for h in result.hypotheses]},
        )
        kept = replace(
            kept, validation_issues=(*kept.validation_issues,
                                    "model_planner_unavailable_host_fallback"),
        )
        return V2Evaluation(
            investigation=result, answer=kept,
            report=format_investigation_report(result.case, result.hypotheses,
                                               result.stopped_because, incident_window),
            incident_window=incident_window,
        )
    # Once the host read budget is exhausted with an attested latest switch
    # command/state/motion chain, no model can acquire another discriminator.
    # Do not spend additional (potentially minutes-long) atomic/narrative
    # model calls to re-select facts the host can already cite. The concise
    # source-first report remains the primary answer, with gaps intact.
    if result.stopped_because == "source_backed_read_budget_reached":
        grounded = assemble_grounded_answer(
            result.case, [],
            {"selected_record_ids": [r.record_id for r in result.case.records],
             "hypothesis_order": []},
        )
        grounded = replace(
            grounded, validation_issues=(*grounded.validation_issues,
                                        "source_backed_read_budget_reached",
                                        "atomic_model_selection_not_needed"),
        )
        return V2Evaluation(
            investigation=result, answer=grounded,
            report=format_investigation_report(
                result.case, [], result.stopped_because, incident_window,
            ),
            incident_window=incident_window,
        )
    # When speculative model reads add no typed evidence, asking another
    # model to validate them creates latency and unsupported causal claims.
    # Preserve all actual event records, commands, and current snapshots;
    # do not promote hypotheses based only on MQTT client status or
    # self-generated health flapping.
    if result.stopped_because in (
            "no_new_usable_evidence", "no_approved_discriminating_reads"):
        grounded = assemble_grounded_answer(
            result.case, [],
            {"selected_record_ids": [r.record_id for r in result.case.records],
             "hypothesis_order": []},
        )
        grounded = replace(
            grounded, validation_issues=(*grounded.validation_issues,
                                        "model_reads_no_new_discriminator",
                                        "model_hypotheses_unverified"),
        )
        return V2Evaluation(
            investigation=result, answer=grounded,
            report=format_investigation_report(
                result.case, [], result.stopped_because, incident_window,
            ),
            incident_window=incident_window,
        )
    if enable_atomic_claim_validation is True:
        atomic = await synthesize_atomic_with_chat(
            case=result.case, hypotheses=result.hypotheses, chat=chat,
            enable_evidence_narrative=enable_evidence_narrative,
        )
        return V2Evaluation(
            investigation=result, answer=atomic.answer,
            atomic_claim_review=atomic.review,
            narrative_audit=atomic.narrative_audit,
            report=format_investigation_report(result.case, result.hypotheses,
                                               result.stopped_because, incident_window),
            incident_window=incident_window,
        )
    answer = await synthesize_with_chat(
        case=result.case, hypotheses=result.hypotheses, chat=chat,
    )
    return V2Evaluation(investigation=result, answer=answer,
                        report=format_investigation_report(result.case, result.hypotheses,
                                                           result.stopped_because, incident_window),
                        incident_window=incident_window)


__all__ = ["V2Evaluation", "evaluate_v2_with_model"]

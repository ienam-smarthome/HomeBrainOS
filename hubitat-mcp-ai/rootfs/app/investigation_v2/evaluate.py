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
    propose = V2ModelProposer(chat, tools, verified_entity_ids=resolved_ids,
                              incident_window=incident_window)
    result = await run_read_only_investigation(
        question=question, mcp=mcp, executor=executor, propose=propose,
        verified_entity_ids=resolved_ids,
        initial_receipts=initial_receipts,
        max_rounds=max_rounds, max_total_reads=max_total_reads,
        incident_window=incident_window,
        planning_timeout_seconds=planning_timeout_seconds,
        bootstrap_source_identity=bootstrap_source_identity,
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

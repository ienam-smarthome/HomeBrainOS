"""Explicit opt-in Investigation V2 model+MCP evaluation seam.

NOT registered with production chat routes, Home Assistant startup or any
background monitor. Uses the EXISTING provider chat callable, existing MCP
client and ToolExecutor. The caller must supply verified target IDs and
explicitly enable this run. No writes, no model-native tool calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from mcp_client import HubitatMCPClient
from tool_executor import ToolExecutor

from .model_adapter import Chat, V2ModelProposer
from .read_loop import InvestigationResult, run_read_only_investigation
from .synthesis import GroundedAnswer, synthesize_with_chat
from .atomic_claims import ClaimReview, synthesize_atomic_with_chat


@dataclass(frozen=True)
class V2Evaluation:
    investigation: InvestigationResult
    answer: GroundedAnswer
    atomic_claim_review: ClaimReview | None = None

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
            "atomic_claim_review": (self.atomic_claim_review.to_dict()
                                    if self.atomic_claim_review else None),
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
) -> V2Evaluation:
    """Run one explicit read-only experiment with the configured chat provider.

    Cannot run via default agent call. Proposals from the provider are checked
    by the host and do not confer target identity or tool authorization.
    """
    if explicitly_authorised is not True:
        raise PermissionError("Investigation V2 requires explicit experiment opt-in")
    if executor.mcp is not mcp:
        raise ValueError("MCP client/executor mismatch")
    tools = await mcp.list_tools()
    propose = V2ModelProposer(chat, tools)
    result = await run_read_only_investigation(
        question=question, mcp=mcp, executor=executor, propose=propose,
        verified_entity_ids=verified_entity_ids,
        initial_receipts=initial_receipts,
        max_rounds=max_rounds, max_total_reads=max_total_reads,
    )
    if enable_atomic_claim_validation is True:
        atomic = await synthesize_atomic_with_chat(
            case=result.case, hypotheses=result.hypotheses, chat=chat,
        )
        return V2Evaluation(
            investigation=result, answer=atomic.answer,
            atomic_claim_review=atomic.review,
        )
    answer = await synthesize_with_chat(
        case=result.case, hypotheses=result.hypotheses, chat=chat,
    )
    return V2Evaluation(investigation=result, answer=answer)


__all__ = ["V2Evaluation", "evaluate_v2_with_model"]

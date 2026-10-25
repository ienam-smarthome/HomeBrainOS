"""Bounded Investigation V2 read-only execution loop.

EXPLICIT INVOCATION ONLY: no production route, final-answer replacement, HA
startup task, or background reads. Model planning is supplied by a callback
which sees only the canonical case file. All IO goes through the established
ToolExecutor; V2 neither calls an MCP write gateway nor creates confirmations.

The host accepts observations and possible hypotheses, not model-declared facts
about completed device actions. This does not establish a root cause.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import time
from typing import Any, Awaitable, Callable, Iterable, Mapping

from mcp_client import HubitatMCPClient, MCPTool
from tool_executor import ToolExecutor
from tool_registry import ToolEffect, classify_tool_effect

from .evidence import CaseFile, build_case_file
from .planning import review_model_read_proposals
from .receipt_projection import project_read_receipt


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    explanation: str
    supporting_record_ids: tuple[str, ...]
    conflicting_record_ids: tuple[str, ...]
    missing_discriminator: str
    assessment: str  # model candidate; NEVER an assertion of proven root cause


@dataclass
class InvestigationResult:
    case: CaseFile
    hypotheses: list[Hypothesis]
    rounds: int
    executed_reads: int
    stopped_because: str
    rejected_proposals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        # No raw tool text, credentials, IPs or model transport responses.
        return {
            "case": self.case.to_dict(),
            "hypotheses": [asdict(item) for item in self.hypotheses],
            "rounds": self.rounds,
            "executed_reads": self.executed_reads,
            "stopped_because": self.stopped_because,
            "rejected_proposals": list(self.rejected_proposals),
            "root_cause_verified": False,
            "production_answer_used": False,
        }


ModelProposer = Callable[[CaseFile, int], Awaitable[Mapping[str, Any]]]


def _hypotheses(
    value: Any, case: CaseFile, existing: dict[str, Hypothesis],
) -> dict[str, Hypothesis]:
    if not isinstance(value, list):
        return existing
    valid_ids = {row.record_id for row in case.records}
    updated = dict(existing)
    for row in value[:8]:
        if not isinstance(row, dict):
            continue
        identifier = row.get("id")
        explanation = row.get("explanation")
        missing = row.get("missing_discriminator")
        positive = row.get("supporting_record_ids", [])
        negative = row.get("conflicting_record_ids", [])
        if (not isinstance(identifier, str) or not 0 < len(identifier) <= 80
                or not isinstance(explanation, str) or not 0 < len(explanation) <= 450
                or not isinstance(missing, str) or len(missing) > 350
                or not isinstance(positive, list) or not isinstance(negative, list)
                or len(positive) > 20 or len(negative) > 20):
            continue
        if (any(not isinstance(x, str) or x not in valid_ids for x in positive + negative)
                or set(positive) & set(negative)):
            continue
        updated[identifier] = Hypothesis(
            identifier, explanation, tuple(dict.fromkeys(positive)),
            tuple(dict.fromkeys(negative)), missing,
            "supported_candidate" if positive else "unsubstantiated_candidate",
        )
    return updated


async def run_read_only_investigation(
    *,
    question: str,
    mcp: HubitatMCPClient,
    executor: ToolExecutor,
    propose: ModelProposer,
    verified_entity_ids: Iterable[str],
    initial_receipts: Iterable[Mapping[str, Any]] = (),
    learned_operations: Mapping[str, set[str]] | None = None,
    max_rounds: int = 3,
    max_total_reads: int = 8,
    max_reads_per_round: int = 2,
    per_read_timeout_seconds: float = 20.0,
) -> InvestigationResult:
    """Run a limited investigative read-only session under existing host gates.

    The host must explicitly supply independently verified IDs and a proposer
    that returns structured AI plans (not an AI-authorized tool registry).
    No automatic registration with HomeBrain's production orchestrator.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Original investigation objective is required")
    if executor.mcp is not mcp:
        raise ValueError("Executor and MCP client must use the same session")
    if not callable(propose):
        raise ValueError("An explicit structured proposal provider is required")

    max_rounds = max(1, min(4, int(max_rounds)))
    max_total_reads = max(0, min(12, int(max_total_reads)))
    max_reads_per_round = max(1, min(3, int(max_reads_per_round)))
    per_read_timeout_seconds = max(1.0, min(30.0, float(per_read_timeout_seconds)))
    # list_tools() is the authoritative live tool list, not a model-generated
    # tool manifest. Missing/failed discovery aborts without any call.
    tools = await mcp.list_tools()
    registry = {t.name: t for t in tools if isinstance(t, MCPTool)}
    receipts = list(initial_receipts)
    case = build_case_file(question, receipts)
    known_ids = tuple(verified_entity_ids)
    prior_calls: list[tuple[str, Mapping[str, Any]]] = []
    hypotheses: dict[str, Hypothesis] = {}
    rejections: list[str] = []
    executed = 0
    rounds = 0
    reason = "round_budget_reached"

    for round_index in range(max_rounds):
        rounds += 1
        # Models can propose, not install credentials, tools or permissions.
        try:
            output = await propose(case, round_index)
        except (Exception, asyncio.CancelledError):
            # Preserve evidence already gathered. Cancellation of the hosting
            # request is not swallowed by read tasks below.
            reason = "planning_unavailable"
            break
        if not isinstance(output, dict):
            reason = "invalid_model_plan"
            break
        hypotheses = _hypotheses(output.get("hypotheses"), case, hypotheses)
        planned = output.get("reads", [])
        if not isinstance(planned, list):
            reason = "invalid_model_plan"
            break

        review = review_model_read_proposals(
            case, planned, registry.values(), verified_entity_ids=known_ids,
            learned_operations=learned_operations,
            previous_calls=prior_calls, max_total_reads=max_total_reads,
            max_reads_this_round=max_reads_per_round,
        )
        rejections.extend(x.reason for x in review.rejected)
        if not review.approved:
            reason = "model_finished" if output.get("finish") is True else "no_approved_discriminating_reads"
            break

        for item in review.approved:
            declared = registry.get(item.tool)
            if declared is None or classify_tool_effect(declared, item.arguments) is not ToolEffect.READ:
                rejections.append("read permission changed before execution")
                continue
            # An existing executor can serve local read handlers or real MCP
            # gateways; no V2-specific transport and no direct MCP mutations.
            prior_calls.append((item.tool, item.arguments))
            executed += 1
            try:
                execution = await asyncio.wait_for(
                    executor.execute(
                        item.tool, dict(item.arguments), tool=declared,
                        record_evidence=False,
                    ),
                    timeout=per_read_timeout_seconds,
                )
                accepted = (
                    execution.effect is ToolEffect.READ and
                    execution.success is True and execution.result is not None
                )
                result = execution.result if accepted else None
                if not accepted:
                    rejections.append("read failed or returned no authoritative result")
            except asyncio.TimeoutError:
                result = None
                rejections.append("bounded MCP read timed out")
            except asyncio.CancelledError:
                raise
            except Exception:
                result = None
                rejections.append("bounded MCP read failed")

            receipt = project_read_receipt(
                item.tool, item.arguments, result,
                source_request_id=f"v2-{round_index}-{executed}",
            )
            receipts.append(receipt)
            case = build_case_file(question, receipts)
        if executed >= max_total_reads:
            reason = "read_budget_reached"
            break

    return InvestigationResult(
        case=case, hypotheses=list(hypotheses.values()), rounds=rounds,
        executed_reads=executed, stopped_because=reason,
        rejected_proposals=rejections,
    )


__all__ = ["Hypothesis", "InvestigationResult", "run_read_only_investigation"]

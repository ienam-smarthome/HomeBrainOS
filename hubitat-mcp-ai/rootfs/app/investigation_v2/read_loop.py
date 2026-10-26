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
from .temporal_scope import IncidentWindow
from .hypothesis_temporal_integrity import hypothesis_clock_issues


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
    incident_window: IncidentWindow | None = None

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
            "requested_incident_window": (self.incident_window.to_dict()
                                          if self.incident_window else None),
        }


ModelProposer = Callable[[CaseFile, int], Awaitable[Mapping[str, Any]]]


def _hypotheses(
    value: Any, case: CaseFile, existing: dict[str, Hypothesis],
    incident_window: IncidentWindow | None = None,
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
        # Record IDs verify cited events, not the prose. Bare times may be
        # UTC conversions presented as local times. Require an explicit
        # timezone and an exact match to a cited source event.
        if hypothesis_clock_issues(explanation, case, positive + negative, incident_window):
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
    planning_timeout_seconds: float = 40.0,
    deadline_seconds: float = 170.0,
    incident_window: IncidentWindow | None = None,
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
    initial = list(initial_receipts)
    if any(not isinstance(row, dict) for row in initial):
        raise ValueError("Initial receipts must be trusted host receipt dictionaries")
    # Existing host receipts are useful only as READ observations. A previous
    # write confirmation or schema-less external snippet is not permission to
    # ground a V2 causal conclusion. Caller must pass trusted host receipts.
    initial = [row for row in initial
               if row.get("mutates") is False and row.get("effect") == "read"]

    max_rounds = max(1, min(4, int(max_rounds)))
    max_total_reads = max(0, min(12, int(max_total_reads)))
    max_reads_per_round = max(1, min(3, int(max_reads_per_round)))
    per_read_timeout_seconds = max(1.0, min(30.0, float(per_read_timeout_seconds)))
    planning_timeout_seconds = max(1.0, min(60.0, float(planning_timeout_seconds)))
    deadline = time.monotonic() + max(3.0, min(180.0, float(deadline_seconds)))
    # list_tools() is the authoritative live tool list, not a model-generated
    # tool manifest. Missing/failed discovery aborts without any call.
    tools = await asyncio.wait_for(
        mcp.list_tools(), timeout=min(20.0, max(0.1, deadline - time.monotonic())))
    registry = {t.name: t for t in tools if isinstance(t, MCPTool)}
    receipts = initial
    case = build_case_file(question, receipts)
    known_ids = tuple(verified_entity_ids)
    prior_calls: list[tuple[str, Mapping[str, Any]]] = []
    hypotheses: dict[str, Hypothesis] = {}
    rejections: list[str] = []
    executed = 0
    rounds = 0
    reason = "round_budget_reached"

    async def execute_checked_read(item: Any, round_index: int) -> None:
        nonlocal executed, case
        declared = registry.get(item.tool)
        if declared is None or classify_tool_effect(declared, item.arguments) is not ToolEffect.READ:
            rejections.append("read permission changed before execution")
            return
        prior_calls.append((item.tool, item.arguments))
        executed += 1
        try:
            execution = await asyncio.wait_for(
                executor.execute(
                    item.tool, dict(item.arguments), tool=declared,
                    record_evidence=False,
                ),
                timeout=min(per_read_timeout_seconds, max(0.1, deadline - time.monotonic())),
            )
            accepted = (
                execution.effect is ToolEffect.READ and
                execution.name == item.tool and execution.success is True and
                execution.result is not None and execution.result.name == item.tool
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
            incident_window=incident_window,
        )
        receipts.append(receipt)
        case = build_case_file(question, receipts)

    # Independent of model output: an explicit past incident with verified
    # targets must first obtain a relevant device-history page. This protects
    # against the model starting with generic rule lists or recent events.
    # Every seed passes the identical production host schema/effect/ID gate.
    if incident_window is not None and known_ids and max_total_reads:
        from .incident_retrieval import incident_first_proposals
        for limit in (150, 500):
            if executed >= min(max_total_reads, 2) or time.monotonic() >= deadline:
                break
            proposals = incident_first_proposals(
                registry.values(), known_ids, incident_window, limit=limit)
            if not proposals:
                rejections.append("incident-first source operation unavailable in live read manifest")
                break
            approved = review_model_read_proposals(
                case, proposals, registry.values(), verified_entity_ids=known_ids,
                learned_operations=learned_operations, previous_calls=prior_calls,
                max_total_reads=max_total_reads, max_reads_this_round=1,
                budget_used_reads=executed, incident_window=incident_window)
            rejections.extend(x.reason for x in approved.rejected)
            if not approved.approved:
                break
            await execute_checked_read(approved.approved[0], -1)
            cov = case.coverage[-1] if case.coverage else None
            # A page that reaches the start need not be retried. If it does
            # not, only a higher-limit read is potentially informative.
            if cov and cov.requested_window_reached is True:
                break
            if cov and not cov.succeeded:
                break
    for round_index in range(max_rounds):
        rounds += 1
        # Models can propose, not install credentials, tools or permissions.
        if time.monotonic() >= deadline:
            reason = "deadline_reached"
            break
        try:
            output = await asyncio.wait_for(
                propose(case, round_index),
                timeout=min(planning_timeout_seconds, max(0.1, deadline - time.monotonic())),
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            reason = "planning_timeout"
            # No additional MCP reads or model-authored conclusions are
            # permitted here. Preserve the incident observations for the
            # standalone source-linked report and explain this coverage gap.
            break
        except Exception:
            reason = "planning_unavailable"
            break
        if not isinstance(output, dict):
            reason = "invalid_model_plan"
            break
        hypotheses = _hypotheses(output.get("hypotheses"), case, hypotheses,
                                 incident_window=incident_window)
        planned = output.get("reads", [])
        if not isinstance(planned, list):
            reason = "invalid_model_plan"
            break

        review = review_model_read_proposals(
            case, planned, registry.values(), verified_entity_ids=known_ids,
            learned_operations=learned_operations,
            previous_calls=prior_calls, max_total_reads=max_total_reads,
            max_reads_this_round=max_reads_per_round,
            budget_used_reads=executed,
            incident_window=incident_window,
        )
        rejections.extend(x.reason for x in review.rejected)
        if not review.approved:
            reason = ("model_finished" if output.get("finish") is True and not review.rejected
                      else "no_approved_discriminating_reads")
            break

        before_records = {record.record_id for record in case.records}
        before_identity = dict(case.app_identities)
        for item in review.approved:
            if time.monotonic() >= deadline:
                reason = "deadline_reached"
                break
            await execute_checked_read(item, round_index)
        if reason == "deadline_reached":
            break
        if executed >= max_total_reads:
            reason = "read_budget_reached"
            break
        if (hypotheses and before_records == {record.record_id for record in case.records}
                and before_identity == case.app_identities):
            # Source operations that were 'successful' but returned no typed
            # observations/identities cannot inform another causal round.
            # Avoid recycling the same model prompt until planning_timeout.
            reason = "no_new_usable_evidence"
            break

    return InvestigationResult(
        case=case, hypotheses=list(hypotheses.values()), rounds=rounds,
        executed_reads=executed, stopped_because=reason,
        rejected_proposals=rejections, incident_window=incident_window,
    )


__all__ = ["Hypothesis", "InvestigationResult", "run_read_only_investigation"]

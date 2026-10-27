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
from .source_identity import source_identity_proposals, source_configuration_proposals
from .read_diagnostics import classify_exception, classify_execution
from .device_context import device_context_proposals
from .operation_discovery import discover_device_operations


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
    planning_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    history_comparison: dict[str, Any] = field(default_factory=dict)
    read_failures: list[dict[str, Any]] = field(default_factory=list)
    bootstrap_diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        # No raw tool text, credentials, IPs or model transport responses.
        return {
            "case": self.case.to_dict(),
            "hypotheses": [asdict(item) for item in self.hypotheses],
            "rounds": self.rounds,
            "executed_reads": self.executed_reads,
            "stopped_because": self.stopped_because,
            "rejected_proposals": list(self.rejected_proposals),
            "planning_diagnostics": list(self.planning_diagnostics),
            "history_comparison": dict(self.history_comparison),
            "read_failures": list(self.read_failures),
            "bootstrap_diagnostics": list(self.bootstrap_diagnostics),
            "root_cause_verified": False,
            "production_answer_used": False,
            "requested_incident_window": (self.incident_window.to_dict()
                                          if self.incident_window else None),
        }


ModelProposer = Callable[[CaseFile, int], Awaitable[Mapping[str, Any]]]


def scope_model_reads_to_verified_target(
    proposals: Any, verified_ids: Iterable[str],
) -> Any:
    """Complete omitted deviceId only from ONE host-verified target.

    Never override a model-supplied ID, never introduce a target for ambiguous
    multi-device requests, and never widen the allowed read operations.
    The ordinary manifest/schema/effect gate still authorises each proposal.
    """
    ids = tuple(str(x) for x in verified_ids if isinstance(x, (str, int))
                and str(x).isdecimal())
    if len(set(ids)) != 1 or not isinstance(proposals, list):
        return proposals
    ident = ids[0]
    repaired = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            repaired.append(proposal)
            continue
        arguments = proposal.get("arguments")
        if not isinstance(arguments, dict) or proposal.get("tool") != "hub_read_devices":
            repaired.append(proposal)
            continue
        if arguments.get("tool") not in ("hub_list_device_events", "hub_get_device"):
            repaired.append(proposal)
            continue
        inner = arguments.get("args")
        if not isinstance(inner, dict) or "deviceId" in inner:
            repaired.append(proposal)
            continue
        enriched = dict(proposal)
        enriched["arguments"] = dict(arguments)
        enriched["arguments"]["args"] = {**inner, "deviceId": ident}
        repaired.append(enriched)
    return repaired


def compare_history_samples(receipts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Detect historical API response drift, not source completeness.

    Only compare source-projected event fingerprints; no raw Hubitat payload,
    credentials or model-generated timestamps enter these metrics.
    """
    import json
    samples: list[set[str]] = []
    commands: list[int] = []
    for rec in receipts:
        if (rec.get("sub_tool") != "hub_list_device_events" or
                rec.get("success") is not True):
            continue
        details = rec.get("details")
        rows = details.get("events") if isinstance(details, dict) else None
        if not isinstance(rows, list):
            continue
        filtered = [row for row in rows if isinstance(row, dict)]
        samples.append({
            json.dumps(row, sort_keys=True, separators=(",", ":"))
            for row in filtered
        })
        commands.append(sum(str(row.get("name", "")).startswith("command-")
                            for row in filtered))
    if len(samples) < 2:
        return {"compared": False, "source_complete_verified": False}
    first, second = samples[0], samples[1]
    return {
        "compared": True,
        "first_event_count": len(first),
        "second_event_count": len(second),
        "first_command_count": commands[0],
        "second_command_count": commands[1],
        "first_only_event_count": len(first - second),
        "second_only_event_count": len(second - first),
        "different": first != second,
        "source_complete_verified": False,
    }


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
    bootstrap_source_identity: bool = False,
    bootstrap_device_context: bool = False,
    stop_after_incident_history: bool = False,
    factual_objective: str | None = None,
) -> InvestigationResult:
    """Run a limited investigative read-only session under existing host gates.

    The host must explicitly supply independently verified IDs and a proposer
    that returns structured AI plans (not an AI-authorized tool registry).
    No automatic registration with HomeBrain's production orchestrator.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Original investigation objective is required")
    if factual_objective not in (None, "status", "history"):
        raise ValueError("Unsupported factual evidence objective")
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
    planning_diagnostics: list[dict[str, Any]] = []
    read_failures: list[dict[str, Any]] = []
    bootstrap_diagnostics: list[dict[str, Any]] = []
    verified_operations: dict[str, set[str]] = {}
    for name, operations in (learned_operations or {}).items():
        if isinstance(name, str) and isinstance(operations, (set, frozenset)):
            verified_operations[name] = set(operations)
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
        started_read = time.monotonic()
        code: str | None = None
        try:
            execution = await asyncio.wait_for(
                executor.execute(
                    item.tool, dict(item.arguments), tool=declared,
                    record_evidence=False,
                ),
                timeout=min(per_read_timeout_seconds, max(0.1, deadline - time.monotonic())),
            )
            if execution.effect is not ToolEffect.READ:
                code = "read_permission_changed"
            else:
                code = classify_execution(execution, item.tool)
            # Even a successful wrapper can contain a protocol-level failure.
            result = execution.result if code is None else None
            if code is None and result is not None:
                from mcp_client import tool_succeeded
                if not tool_succeeded(result):
                    code = "mcp_result_unsuccessful"
                    result = None
        except asyncio.TimeoutError:
            code = "read_timeout"
            result = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            code = classify_exception(exc)
            result = None
        if code is not None:
            rejections.append("MCP read failed: " + code)
        receipt = project_read_receipt(
            item.tool, item.arguments, result,
            source_request_id=f"v2-{round_index}-{executed}",
            incident_window=incident_window,
        )
        if code is not None:
            # Local enum only: never propagate exception messages, raw URLs,
            # serialized MCP outputs or untrusted error fields.
            receipt["failure_code"] = code
            args = item.arguments.get("args", {})
            requested_id = args.get("appId", args.get("deviceId")) if isinstance(args, dict) else None
            read_failures.append({
                "source_request_id": receipt["source_request_id"],
                "tool": item.tool,
                "operation": str(item.arguments.get("tool", ""))[:80],
                "target_id": str(requested_id) if isinstance(requested_id, (str,int))
                          and str(requested_id).isdecimal() else None,
                "code": code,
                "elapsed_ms": min(200000, max(0, int((time.monotonic()-started_read)*1000))),
            })
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
                learned_operations=verified_operations, previous_calls=prior_calls,
                max_total_reads=max_total_reads, max_reads_this_round=1,
                budget_used_reads=executed, incident_window=incident_window)
            rejections.extend(x.reason for x in approved.rejected)
            if not approved.approved:
                break
            await execute_checked_read(approved.approved[0], -1)
            cov = case.coverage[-1] if case.coverage else None
            # A page that reaches the start need not be retried. If it does
            # not, only a higher-limit read is potentially informative.
            # A page reaching the requested start does NOT establish source
            # completeness. Take a second differently-sized bounded snapshot
            # for discrepancies, even when the first page reached the start.
            if cov and not cov.succeeded:
                break
    # A validated state-duration objective needs historical state transitions,
    # not causal hypothesis generation. The evaluator will compute an explicit
    # interval report without a slow model or unverifiable arithmetic.
    if stop_after_incident_history:
        return InvestigationResult(
            case=case, hypotheses=[], rounds=0, executed_reads=executed,
            stopped_because="state_duration_history_collected",
            rejected_proposals=rejections, incident_window=incident_window,
            planning_diagnostics=planning_diagnostics,
            history_comparison=compare_history_samples(receipts),
            read_failures=read_failures,
        )

    # Read-first V2 bootstrap: positive current-session discovery can fill
    # absent generic gateway enums; it never supersedes an explicit denial.
    if (bootstrap_device_context and incident_window is None
            and len(set(known_ids)) == 1 and not stop_after_incident_history):
        discovered, checks = await discover_device_operations(
            registry.values(), executor,
            deadline_remaining=max(0.0, min(12.0, deadline - time.monotonic())),
        )
        bootstrap_diagnostics.extend(checks)
        for name, ops in discovered.items():
            verified_operations.setdefault(name, set()).update(ops)
        for stage in (("current",) if factual_objective == "status"
                      else ("current", "history")):
            if executed >= max_total_reads or time.monotonic() >= deadline:
                bootstrap_diagnostics.append({
                    "stage": stage, "reason": "read_or_time_budget_exhausted"})
                break
            proposals = device_context_proposals(
                registry.values(), known_ids, case, stage=stage,
                learned_operations=verified_operations,
            )
            if not proposals:
                bootstrap_diagnostics.append({
                    "stage": stage, "reason": "no_authorised_live_operation_or_schema"})
                continue
            approved = review_model_read_proposals(
                case, proposals, registry.values(), verified_entity_ids=known_ids,
                learned_operations=verified_operations, previous_calls=prior_calls,
                max_total_reads=max_total_reads, max_reads_this_round=1,
                budget_used_reads=executed, incident_window=incident_window,
            )
            rejections.extend(x.reason for x in approved.rejected)
            if not approved.approved:
                bootstrap_diagnostics.append({
                    "stage": stage, "reason": "read_plan_rejected",
                    "validation": [r.reason for r in approved.rejected[:3]],
                })
            for item in approved.approved:
                before = len(read_failures)
                await execute_checked_read(item, -4 if stage == "current" else -5)
                bootstrap_diagnostics.append({
                    "stage": stage,
                    "status": ("read_attempt_failed" if len(read_failures) > before
                               else "read_attempt_completed"),
                })

    # Simple factual questions finish with source evidence, not hypotheses.
    # This branch is available only after independently verified identity and
    # an exact host factual contract; ambiguous/causal questions use AI.
    if factual_objective is not None:
        return InvestigationResult(
            case=case, hypotheses=[], rounds=0, executed_reads=executed,
            stopped_because="factual_" + factual_objective + "_collected",
            rejected_proposals=rejections, incident_window=incident_window,
            planning_diagnostics=planning_diagnostics,
            history_comparison=compare_history_samples(receipts),
            read_failures=read_failures,
            bootstrap_diagnostics=bootstrap_diagnostics,
        )

    # If an independently authorised, switch-filtered history request returned
    # zero source rows, try one bounded unfiltered read. A zero row response
    # from one query does NOT establish that no prior events occurred.
    if (bootstrap_device_context and incident_window is None
            and len(set(known_ids)) == 1
            and executed < max_total_reads and time.monotonic() < deadline):
        empty_switch = next((c for c in reversed(case.coverage)
                             if c.operation == "hub_list_device_events"
                             and c.succeeded
                             and c.requested_filters.get("attribute") == "switch"
                             and c.source_returned_rows == 0), None)
        if empty_switch is not None:
            proposals = device_context_proposals(
                registry.values(), known_ids, case, stage="history_unfiltered",
                learned_operations=verified_operations,
            )
            if proposals:
                approved = review_model_read_proposals(
                    case, proposals, registry.values(),
                    verified_entity_ids=known_ids,
                    learned_operations=verified_operations,
                    previous_calls=prior_calls,
                    max_total_reads=max_total_reads, max_reads_this_round=1,
                    budget_used_reads=executed, incident_window=incident_window,
                )
                rejections.extend(r.reason for r in approved.rejected)
                if not approved.approved:
                    bootstrap_diagnostics.append({
                        "stage": "history_unfiltered", "reason": "read_plan_rejected",
                        "validation": [r.reason for r in approved.rejected[:3]],
                    })
                for item in approved.approved:
                    prior = len(read_failures)
                    await execute_checked_read(item, -6)
                    bootstrap_diagnostics.append({
                        "stage": "history_unfiltered",
                        "status": ("read_attempt_failed" if len(read_failures) > prior
                                   else "read_attempt_completed"),
                    })
            else:
                bootstrap_diagnostics.append({
                    "stage": "history_unfiltered",
                    "reason": "read_schema_does_not_allow_unfiltered_events",
                })

    # An old device-reported lastSeen whose incident is missing from recent
    # event pages is a useful historical search anchor, not proof of contact.
    # Fetch at most ONE extra bounded source page before the model; never
    # rewrite the user's incident window or bypass schema/ID/effect review.
    if (bootstrap_device_context and factual_objective is None
            and incident_window is None and len(set(known_ids)) == 1
            and executed < max_total_reads and time.monotonic() < deadline):
        from .last_contact_anchor import last_contact_anchor_proposals
        proposals, strategy = last_contact_anchor_proposals(
            registry.values(), known_ids, case,
            learned_operations=verified_operations)
        bootstrap_diagnostics.append({
            "stage": "history_last_contact", "reason": strategy})
        if proposals:
            approved = review_model_read_proposals(
                case, proposals, registry.values(), verified_entity_ids=known_ids,
                learned_operations=verified_operations, previous_calls=prior_calls,
                max_total_reads=max_total_reads, max_reads_this_round=1,
                budget_used_reads=executed, incident_window=incident_window,
            )
            rejections.extend(x.reason for x in approved.rejected)
            if not approved.approved:
                bootstrap_diagnostics.append({
                    "stage": "history_last_contact", "reason": "host_read_plan_rejected",
                    "validation": [x.reason for x in approved.rejected[:3]],
                })
            for item in approved.approved:
                before = len(read_failures)
                await execute_checked_read(item, -7)
                cov = case.coverage[-1] if case.coverage else None
                bootstrap_diagnostics.append({
                    "stage": "history_last_contact",
                    "status": ("read_attempt_failed" if len(read_failures) > before
                               else "read_attempt_completed"),
                    # Source data are not assumed to have honoured since/until.
                    "source_returned_rows": (cov.source_returned_rows if cov else None),
                    "source_oldest_utc": (cov.oldest_utc if cov else None),
                    "source_complete_verified": (cov.source_complete is True
                                                 if cov else False),
                })

    # Provenance-first enrichment is a HOST-APPROVED optional READ, not a
    # replacement for model planning. It can make useful progress even when
    # the configured LLM takes too long to provide a structured proposal.
    if bootstrap_source_identity and executed < max_total_reads and time.monotonic() < deadline:
        proposals = source_identity_proposals(registry.values(), case)
        if proposals:
            approved = review_model_read_proposals(
                case, proposals, registry.values(), verified_entity_ids=known_ids,
                learned_operations=verified_operations, previous_calls=prior_calls,
                max_total_reads=max_total_reads, max_reads_this_round=1,
                budget_used_reads=executed, incident_window=incident_window,
            )
            rejections.extend(x.reason for x in approved.rejected)
            for item in approved.approved:
                await execute_checked_read(item, -2)

    # The catalogue may omit child apps even when their command issuer IDs
    # are attested by the device's own event records. One targeted, read-only
    # app-config lookup adds a potential discriminator before model latency.
    if bootstrap_source_identity and executed < max_total_reads and time.monotonic() < deadline:
        proposals = source_configuration_proposals(
            registry.values(), case, diagnostics=bootstrap_diagnostics)
        if proposals:
            approved = review_model_read_proposals(
                case, proposals, registry.values(), verified_entity_ids=known_ids,
                learned_operations=verified_operations, previous_calls=prior_calls,
                max_total_reads=max_total_reads, max_reads_this_round=1,
                budget_used_reads=executed, incident_window=incident_window,
            )
            rejections.extend(x.reason for x in approved.rejected)
            if not approved.approved:
                bootstrap_diagnostics.append({
                    "stage": "controller_config", "reason": "host_read_plan_rejected",
                    "validation": [r.reason for r in approved.rejected[:3]],
                })
            for item in approved.approved:
                before = len(read_failures)
                await execute_checked_read(item, -3)
                latest = receipts[-1] if receipts else {}
                projected = latest.get("details", {}) if isinstance(latest, dict) else {}
                readable = (isinstance(projected, dict)
                            and projected.get("settingsReadable") is True)
                fields_count = (sum(len(projected.get(key, []))
                                    for key in ("indexedFields", "controllerFields")
                                    if isinstance(projected.get(key), list))
                                if readable else 0)
                bootstrap_diagnostics.append({
                    "stage": "controller_config",
                    "status": ("read_attempt_failed" if len(read_failures) > before
                               else "read_attempt_completed"),
                    "settings_projection": (
                        "typed_fields_available" if fields_count
                        else "readable_no_supported_fields" if readable
                        else "settings_not_readable"),
                    "typed_settings_fields": min(96, fields_count),
                })

    for round_index in range(max_rounds):
        rounds += 1
        # Models can propose, not install credentials, tools or permissions.
        if time.monotonic() >= deadline:
            reason = "deadline_reached"
            break
        started = time.monotonic()
        planning_budget = min(planning_timeout_seconds, max(0.1, deadline - started))
        diag = {
            "round": round_index,
            "budget_ms": int(planning_budget * 1000),
            "case_records": len(case.records),
            "input_chars": None,
            "advertised_tools": getattr(propose, "advertised_tool_count", None),
            "elapsed_ms": None,
            "outcome": "not_started",
        }
        try:
            output = await asyncio.wait_for(
                propose(case, round_index),
                timeout=planning_budget,
            )
            diag["outcome"] = "returned"
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            reason = "planning_timeout"
            diag["outcome"] = "timeout"
            break
        except Exception:
            reason = "planning_unavailable"
            diag["outcome"] = "error"
            break
        finally:
            diag["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            chars = getattr(propose, "last_prompt_chars", None)
            diag["input_chars"] = chars if type(chars) is int and 0 <= chars <= 200000 else None
            planning_diagnostics.append(diag)
        if not isinstance(output, dict):
            reason = "invalid_model_plan"
            break
        hypotheses = _hypotheses(output.get("hypotheses"), case, hypotheses,
                                 incident_window=incident_window)
        planned = output.get("reads", [])
        if not isinstance(planned, list):
            reason = "invalid_model_plan"
            break

        planned = scope_model_reads_to_verified_target(planned, known_ids)
        review = review_model_read_proposals(
            case, planned, registry.values(), verified_entity_ids=known_ids,
            learned_operations=verified_operations,
            previous_calls=prior_calls, max_total_reads=max_total_reads,
            max_reads_this_round=max_reads_per_round,
            budget_used_reads=executed,
            incident_window=incident_window,
        )
        rejections.extend(x.reason for x in review.rejected)
        if not review.approved:
            if (review.rejected and round_index + 1 < max_rounds
                    and hasattr(propose, "set_validation_feedback")
                    and callable(getattr(propose, "set_validation_feedback"))):
                # Bounded, host-created validation classes, not model/tool text.
                # Give the AI one further chance with the same authoritative
                # live operation catalogue; it still cannot grant permission.
                feedback = [x.reason for x in review.rejected[:4]]
                propose.set_validation_feedback(feedback)
                continue
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
        planning_diagnostics=planning_diagnostics,
        history_comparison=compare_history_samples(receipts),
        read_failures=read_failures, bootstrap_diagnostics=bootstrap_diagnostics,
    )


__all__ = ["Hypothesis", "InvestigationResult", "run_read_only_investigation"]

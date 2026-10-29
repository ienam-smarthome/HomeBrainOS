"""Experimental V2 native MCP READ agent: no preselected device or question router.

The model sees a small, current tools/list read surface and chooses all reads.
The host alone validates gateway/operation/schema/effect, independently observed
target IDs and bounded sequential execution. No management tools, writes,
confirmations, credentials, or raw MCP responses reach this loop.

This is a separate explicit V2 experimental mode, never production Main Ask.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import re
import time
from typing import Any, Awaitable, Callable, Iterable, Mapping

from mcp_client import HubitatMCPClient, MCPTool, tool_succeeded
from tool_executor import ToolExecutor
from tool_registry import ToolEffect, classify_tool_effect
from .planning import _schema_problem
from .read_diagnostics import classify_execution, classify_exception
from .native_source_adapters import compact_logs, attested_source_ids, unwrapped
from .native_tool_protocol import operation_problem, guidance_for, source_highlights, evidence_fallback
from .native_entity_lookup import NAME as LOOKUP_NAME, lookup_tool, resolve_named_device
from .native_intent_handoff import (
    NAME as HANDOFF_NAME, handoff_tool, handoff_result)
from .native_evidence_focus import read_fingerprint, focused_highlights, focused_fallback, focused_model_view
from .native_device_projection import device_mode_evidence
from .native_read_scope import target_history_scope_problem
from .native_app_pages import app_pages_summary
from .native_causal_claim_audit import (
    incident_attribution_packet, unsupported_causal_ranking,
    evidence_safe_incident_explanation, incident_claim_ledger,
    source_bound_incident_required,
)
from .native_source_readiness import source_read_summary, repeated_broad_log_scope
from .native_source_followup import source_path_followup
from .native_focus_anchor import verified_device_focus
from .native_fact_ledger import factual_evidence_ledger
from .native_claim_verifier import claim_catalog, publish_verified_claims
from .native_answer_brief import evidence_readiness, evidence_brief
from .native_cross_source_brief import verified_source_cases, source_connected_brief
from .native_subject_relevance import subject_relevance_limit
from .native_room_evidence import natural_entity_answer, verified_room_inventory
from .native_room_catalog import source_room_catalog, question_room_matches
from .native_temporal_lead import (verified_temporal_lead,
                                   temporal_lead_brief,
                                   temporal_lead_short_answer)
from .native_history_recovery import (
    requested_history_bounds, normalize_selected_history_read)
from .native_incident_relevance import (
    dated_incident_evidence, natural_incident_gap_answer)
from .native_reasoned_assessment import (
    candidate_prompt, verify_natural_hypothesis)
from .native_operational_sequence import operational_sequence_brief
from .native_reasoning_policy import planning_system_prompt
from .native_controller_decision import controller_decision_followup, scoped_app_execution_lines
from .native_verified_prose import (
    verify_model_explanation, narrative_followup_eligible)
from .native_read_contracts import (read_contract_feedback,
                                    advertised_operation_contracts)
from .native_metrics_evidence import project_metrics, project_memory_history
from .native_runtime_stats import (
    project_log_runtime_stats, verified_caller_app_ids)
from .native_evidence_coverage import (
    gap_for_target, gateway_offers_operation,
    useful_discovery_fingerprint, repeated_log_evidence, repeated_event_evidence,
)
from .native_provenance import (source_identities, event_summary,
                                dependent_summary, driver_summary,
                                app_config_summary, source_metadata)
from evidence_gateway_contract import missing_required_read_fields

Chat = Callable[[list[dict[str, Any]], list[dict[str, Any]]],
                Awaitable[dict[str, Any]]]

_READ_PREFIXES = ("hub_get_", "hub_list_", "hub_read_", "hub_search_",
                  "hub_check_", "hub_find_")
_LIMIT = 12
_SYSTEM = planning_system_prompt()
_REDACT = re.compile(r"(?i)\b(?:token|secret|apikey|api_key|password|authorization"
                     r"|bearer|credential|access_key)\b\s*[:=]\s*[^\s,;]+")
_URL = re.compile(r"https?://[^\s<>]+", re.I)
_SECRET_KEY = re.compile(r"(?i)(?:token|secret|password|credential|api.?key"
                         r"|authorization|cookie|url|ipAddress|macAddress)")
_SAFE_KEYS = frozenset({
    "success", "online", "status", "health", "healthStatus", "networkStatus",
    "message", "error", "warning", "warnings", "errors", "alerts",
    "alert", "code", "reason", "suggestion", "name", "label", "id",
    "deviceId", "appId", "sourceId", "source", "sourceType", "type",
    "level", "date", "timestamp", "time", "elapsed_ms", "uptime",
    "uptimeSeconds", "freeMemory", "freeMemoryMb", "freeMemoryMB",
    "temperature", "temp", "cpu", "cpuLoad", "dbSize", "dbSizeMb",
    "safeMode", "value", "attribute", "events", "logs", "devices",
    "apps", "rules", "results", "matches", "gateway", "tool",
    "counts", "count", "total", "page", "offset", "limit",
    "truncated", "nextCursor", "response_too_large", "result",
    "data", "output", "details", "capabilities", "attributes",
    "producedBy", "switch", "motion", "battery", "lastActivity",
    "metrics", "healthAlerts", "health_alerts", "backupStatus",
    "firmware", "freeMem", "entries", "severity", "appName",
    "description", "msg", "event",
    "nodes", "mesh", "meshNodes", "health", "deviceHealth",
    "offline", "online", "unknown", "unavailable", "stale",
    "lastSeen", "lastSeenAt", "lastMessage", "lastContact",
    "duration", "age", "ageSeconds", "statusCount",
    "deviceCount", "offlineCount", "critical", "warning",
    "problems", "summary", "gatewayStatus", "zigbee", "zwave",
    "staleDevices", "unknownDevices", "recommendation",
    "hubMeshEnabled", "fullRefreshInterval", "peers", "sharedDevices",
    "localLinkedDevices", "availableLinkedDevices", "privateDeviceCount",
    "modeHubId", "sourceCoverage", "availableSections", "sectionRead",
})
_CONTROL_KEYS = frozenset({
    "command", "commands", "confirm", "confirmation", "action",
    "delete", "mutate", "newValue", "write", "execute",
})


def _text(value: Any, limit: int = 280) -> str:
    raw = str(value if value is not None else "")[:min(6000, max(1800, limit + 300))]
    raw = _URL.sub("[URL redacted]", raw)
    raw = _REDACT.sub("[credential redacted]", raw)
    raw = "".join(ch if ch.isprintable() and ch not in "<>\x60" else " "
                  for ch in raw)
    return " ".join(raw.split())[:limit]



def _answer_text(value: Any, limit: int = 4500) -> str:
    """Redact model prose without flattening readable headings and bullets."""
    if not isinstance(value, str):
        return ""
    raw = value[:limit+800]
    raw = _URL.sub("[URL redacted]", raw)
    raw = _REDACT.sub("[credential redacted]", raw)
    raw = "".join(ch if ch.isprintable() or ch in "\n\t" else " "
                  for ch in raw if ch not in "<>\x60")
    rows = [" ".join(line.split()) for line in raw.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(rows)).strip()[:limit]


def _project(value: Any, *, depth: int = 0) -> Any:
    """Conservative typed read summary; never forward arbitrary raw objects."""
    if depth > 5:
        return None
    if isinstance(value, dict):
        obj: dict[str, Any] = {}
        for k, v in list(value.items())[:65]:
            if (not isinstance(k, str) or _SECRET_KEY.search(k)
                    or k not in _SAFE_KEYS):
                continue
            piece = _project(v, depth=depth + 1)
            if piece is not None:
                obj[k] = piece
        return obj
    if isinstance(value, list):
        return [_project(item, depth=depth + 1) for item in value[:80]]
    if isinstance(value, (str, int, float, bool)) and not isinstance(value, complex):
        return _text(value, 600) if isinstance(value, str) else value
    return None


def _group_logs(data: Mapping[str, Any]) -> dict[str, Any] | None:
    """Compatibility projection; single implementation lives in source adapters."""
    summary = compact_logs(data)
    if summary is None:
        return None
    return {
        **summary,
        "groups": summary["warning_error_groups"],
        "group_count": summary["warning_error_group_count"],
    }

def _payload(result: Any, operation: str, *, read_filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = result.data if isinstance(result.data, dict) else {}
    for key in ("result", "data", "output"):
        child = data.get(key)
        if isinstance(child, dict) and any(
                k in child for k in ("logs", "devices", "alerts", "events", "results")):
            data = child
            break
    projected = _project(data)
    if not isinstance(projected, dict):
        projected = {}
    # "success": true with all actual mesh/health measurements discarded is
    # NOT a useful evidence projection. Detect unhandled source fields even
    # if common status flags were projected.
    raw_fields = unwrapped(data)
    unmapped = [
        k for k in list(raw_fields)[:50]
        if isinstance(k, str) and len(k) <= 50
        and not _SECRET_KEY.search(k) and k not in projected
        and k not in ("result", "data", "output")
    ]
    if unmapped and operation != "hub_get_logs":
        projected["projection_incomplete"] = True
        projected["unmapped_source_fields"] = unmapped[:25]
        projected["source_field_names"] = unmapped[:25]
        if set(projected).issubset({
            "success", "status", "projection_incomplete",
            "unmapped_source_fields", "source_field_names",
        }):
            projected["projection_empty"] = True
    if operation == "hub_get_device":
        projected.update(device_mode_evidence(data))
    elif operation == "hub_list_rooms":
        # The source lists room NAMES, not verified members or device states.
        catalog = source_room_catalog(data)
        if catalog is not None:
            projected = catalog
    elif operation == "hub_list_device_events":
        event_evidence = event_summary(data)
        if event_evidence is not None:
            projected = event_evidence
    elif operation == "hub_list_device_dependents":
        refs = dependent_summary(data)
        if refs is not None:
            projected = refs
    elif operation == "hub_list_drivers":
        refs = driver_summary(data)
        if refs is not None:
            projected = refs
    elif operation == "hub_get_app_config":
        # Nested source settingsPage.app is not part of the generic safe-key
        # projection; retain whitelisted metadata instead of empty labels.
        projected = app_config_summary(data)
    elif operation == "hub_list_app_pages":
        projected = app_pages_summary(data)
    elif operation in ("hub_get_metrics", "hub_get_performance_stats"):
        projected.update(project_metrics(data))
    elif operation == "hub_get_memory_history":
        projected = project_memory_history(data)
    elif operation == "hub_get_source":
        # No raw Groovy, settings or executable source enters model context.
        # Complete source produces lexical method evidence only; a successful
        # empty read is explicitly *not* an implementation inspection.
        projected = source_read_summary(data)
    if operation == "hub_get_logs":
        # Logs-page Device/App Stats are *not* severity log rows.
        # The upstream server exposes them under hub_get_logs modes and
        # removed the old hub_get_performance_stats operation.
        stats = project_log_runtime_stats(data)
        if stats is not None:
            projected = {"runtime_stats": stats, "source_complete": False}
        else:
            log_groups = compact_logs(data)
            if log_groups is not None:
                projected = {"log_summary": log_groups, "source_complete": False}
                app = str((read_filters or {}).get("appId") or "")
                if app.isdecimal():
                    execution = scoped_app_execution_lines(data, app)
                    if execution:
                        projected["app_execution_lines"] = execution
                        projected["execution_time_zone_verified"] = False
    if not projected:
        # Successful gateway does not prove we understood its data.
        projected = {
            "projection_empty": True,
            "source_field_names": [
                k for k in list(unwrapped(data))[:30]
                if isinstance(k, str) and len(k) <= 50
                and not _SECRET_KEY.search(k)
            ],
            "source_complete": False,
        }
    return projected


def _oversized_hint(result: Any) -> str | None:
    """Treat a typed size-limit envelope as a narrower-read instruction.

    Never retry the same expensive query and never execute source-supplied
    suggestions. The model may propose a new READ, which is revalidated.
    """
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return None
    candidate = data.get("error")
    nested = candidate if isinstance(candidate, dict) else {}
    code = nested.get("code") or data.get("code")
    if code != "response_too_large":
        return None
    suggestion = nested.get("suggestion") or data.get("suggestion")
    return _text(suggestion, 200) or "Use narrower filters, pagination or a shorter time range"


def _read_manifest(tools: Iterable[MCPTool]) -> dict[str, MCPTool]:
    admitted: dict[str, MCPTool] = {}
    for tool in tools:
        if not isinstance(tool, MCPTool):
            continue
        if not (tool.name.startswith("hub_read_")
                or tool.name in ("hub_get_info", "hub_search_tools")):
            continue
        annotations = tool.annotations if isinstance(tool.annotations, dict) else {}
        if (annotations.get("readOnlyHint") is False
                or annotations.get("mutates") is True
                or annotations.get("destructiveHint") is True
                or classify_tool_effect(tool, {}) is not ToolEffect.READ):
            continue
        admitted[tool.name] = tool
    return dict(list(admitted.items())[:24])


def _model_tools(manifest: Mapping[str, MCPTool]) -> list[dict[str, Any]]:
    result = []
    for tool in manifest.values():
        schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
        schema = json.loads(json.dumps(schema))  # independent projection
        if tool.name.startswith("hub_read_"):
            entry = schema.get("properties", {}).get("tool")
            if isinstance(entry, dict) and isinstance(entry.get("enum"), list):
                entry["enum"] = [op for op in entry["enum"]
                                 if isinstance(op, str) and op.startswith(_READ_PREFIXES)]
        # The live gateway often exposes an unconstrained nested args object.
        # Supply only contract notes for *enumerated, live-offered* read
        # operations, so the model knows which required args to generate.
        # These are documentation, never a schema/permission change.
        allowed_ops = schema.get("properties", {}).get("tool", {}).get("enum")
        contract_hint = (advertised_operation_contracts(allowed_ops)
                         if isinstance(allowed_ops, list) else "")
        description = _text(tool.description or tool.name, 350)
        if contract_hint:
            description += " | Nested READ contracts: " + contract_hint
        result.append({"type": "function", "function": {
            "name": tool.name,
            "description": description,
            "parameters": schema,
        }})
    return result


def _arguments(call: Any) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(call, dict):
        return None
    fn = call.get("function")
    if not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
        return None
    args = fn.get("arguments")
    if isinstance(args, str) and len(args) <= 10000:
        try:
            args = json.loads(args)
        except (ValueError, TypeError):
            return None
    if not isinstance(args, dict):
        return None
    try:
        if len(json.dumps(args)) > 10000:
            return None
    except (TypeError, ValueError):
        return None
    return fn["name"], args


def _ids_from_read(op: str, data: Any) -> set[str]:
    """Compatibility entry point for the common source-attestation adapter."""
    return attested_source_ids(op, data)

def _observed_operations(result: Any, manifest: Mapping[str, MCPTool]) -> dict[str, set[str]]:
    """Only exact, structured same-session hub_search_tools mappings count."""
    data = result.data if isinstance(result.data, dict) else {}
    if isinstance(data.get("result"), dict):
        data = data["result"]
    entries = data.get("results", data.get("matches"))
    verified: dict[str, set[str]] = {}
    if not isinstance(entries, list):
        return verified
    for row in entries[:100]:
        if not isinstance(row, dict):
            continue
        gateway, op = row.get("gateway"), row.get("tool")
        if (not isinstance(gateway, str) or gateway not in manifest
                or not gateway.startswith("hub_read_")
                or not isinstance(op, str) or not op.startswith(_READ_PREFIXES)):
            continue
        if classify_tool_effect(manifest[gateway], {"tool": op}) is ToolEffect.READ:
            verified.setdefault(gateway, set()).add(op)
    return verified


def _contains_control_key(value: Any, depth: int = 0) -> bool:
    if depth > 6:
        return True
    if isinstance(value, dict):
        return any(
            isinstance(key, str) and key in _CONTROL_KEYS
            or _contains_control_key(inner, depth+1)
            for key, inner in value.items()
        )
    if isinstance(value, list):
        return any(_contains_control_key(item, depth+1) for item in value[:50])
    return False


def _verified_gateways_for_operation(
    op: str, inner: Mapping[str, Any],
    manifest: Mapping[str, MCPTool],
    discovered: Mapping[str, set[str]],
) -> list[str]:
    """Only suggest actual live READ mappings, never infer a gateway.

    Suggestions are not tool permissions; the model's next proposal passes
    the normal effect, identity, scope and schema guards independently.
    """
    if not isinstance(op, str) or not op.startswith(_READ_PREFIXES):
        return []
    matches = []
    for name, tool in manifest.items():
        if not name.startswith("hub_read_"):
            continue
        enum = tool.input_schema.get("properties", {}).get("tool", {}).get("enum")
        attested = ((isinstance(enum, list) and op in enum)
                    or op in discovered.get(name, set()))
        if (attested and classify_tool_effect(
                tool, {"tool": op, "args": dict(inner)}) is ToolEffect.READ):
            matches.append(name)
    return sorted(matches)[:5]


def _guard(name: str, args: dict[str, Any],
           manifest: Mapping[str, MCPTool],
           discovered: Mapping[str, set[str]], verified_ids: set[str],
           verified_typed: Mapping[str, set[str]] | None = None) -> str | None:
    tool = manifest.get(name)
    if tool is None:
        return "tool_not_on_live_read_manifest"
    if classify_tool_effect(tool, args) is not ToolEffect.READ:
        return "tool_is_not_read_only"
    if _contains_control_key(args):
        return "write_argument_rejected"
    if name.startswith("hub_read_"):
        op = args.get("tool")
        if not isinstance(op, str) or not op.startswith(_READ_PREFIXES):
            return "unsafe_or_missing_operation"
        enum = tool.input_schema.get("properties", {}).get("tool", {}).get("enum")
        if (not isinstance(enum, list) or op not in enum) and op not in discovered.get(name, set()):
            return "operation_not_independently_discovered"
        inner = args.get("args", {})
        if not isinstance(inner, dict) or _contains_control_key(inner):
            return "unsafe_arguments"
    else:
        inner = args
    for id_key in ("deviceId", "appId"):
        value = inner.get(id_key)
        category = "device" if id_key == "deviceId" else "app"
        allowed = (verified_ids if verified_typed is None
                   else verified_typed.get(category, set()))
        if value is not None and (type(value) not in (str, int)
                                 or str(value) not in allowed):
            return "target_id_not_verified_from_live_source"
    if verified_typed is not None and args.get("tool") == "hub_get_source":
        source_kind = inner.get("type")
        source_id = inner.get("id")
        if source_id is not None:
            if source_kind not in ("app", "driver"):
                return "source_type_not_attested"
            if (type(source_id) not in (str, int)
                    or str(source_id) not in verified_typed.get(source_kind, set())):
                return "target_id_not_verified_from_live_source"
    contract_issue = operation_problem(name, args)
    if contract_issue:
        return contract_issue
    if missing_required_read_fields(name, args):
        # The thin gateway schema does not express concrete operation
        # requirements. Fail before ToolExecutor and teach the model to
        # obtain independently verified identity rather than sending a
        # device read with no deviceId.
        return "missing_required_operation_fields"
    err = _schema_problem(args, tool.input_schema)
    if err:
        return "live_schema_rejected"
    return None


async def run_native_read_agent(
    *, question: str, chat: Chat, mcp: HubitatMCPClient,
    executor: ToolExecutor, max_rounds: int = 6, max_reads: int = _LIMIT,
    max_seconds: float = 165.0, model_timeout: float = 28.0,
    per_read_timeout: float = 20.0,
    enable_verified_narrative: bool = False,
    enable_model_reasoned_assessment: bool = False,
) -> dict[str, Any]:
    """Execute bounded, sequential model-chosen READ calls with an evidence trail."""
    if executor.mcp is not mcp:
        raise ValueError("MCP/executor mismatch")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question required")
    max_rounds = max(1, min(8, int(max_rounds)))
    max_reads = max(1, min(16, int(max_reads)))
    started = time.monotonic()
    deadline = started + max(10, min(180.0, float(max_seconds)))
    tools = await asyncio.wait_for(mcp.list_tools(), timeout=15)
    manifest = _read_manifest(tools)
    if not manifest:
        raise ValueError("No live read-only MCP tools verified")
    # Every native question, including a possible write, is interpreted by
    # the normal model planning pass. The model may select a *local*
    # navigation-only handoff; actual tool execution is READ-only regardless
    # of model intent or output.
    offered = [handoff_tool()] + _model_tools(manifest) + [lookup_tool()]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": question},
    ]
    verified_ids: set[str] = set()
    verified_typed: dict[str, set[str]] = {"device": set(), "app": set(), "driver": set()}
    discovered: dict[str, set[str]] = {}
    prior: set[str] = set()
    timed_out_operations: set[tuple[str, str]] = set()
    failed_scoped_reads: dict[tuple[str, str], int] = {}
    blocked_repeat_errors = 0
    final_synthesis_skipped_reason: str | None = None
    recovery_rejections = 0
    invalid_contract_attempts: dict[str, int] = {}
    rejected_scope_history_reads = 0
    normalized_history_reads: list[dict[str, Any]] = []
    witnesses: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    attempted = 0
    rounds = 0
    identity_lookup_attempted = False
    named_identity_lookups: list[dict[str, Any]] = []
    room_inventories: list[dict[str, Any]] = []
    room_name_catalogs: list[dict[str, Any]] = []
    focus_ids: set[str] = set()
    verified_focus_receipts: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    redundant_evidence_reads = 0
    redundant_snapshot_reads = 0
    redundant_log_subsets = 0
    redundant_event_subsets = 0
    identity_lookup_ms = 0
    synthesis_status = "not_needed"
    coverage_challenge_used = False
    causal_coverage_challenge_used = False
    upstream_decision_challenge_used = False
    causal_coverage_gap: dict[str, Any] | None = None
    repeated_discovery = 0
    discovery_fingerprints: set[tuple[str, ...]] = set()
    synthesis_elapsed_ms = 0
    answer_text = ""
    model_claim_proposal: Any = None
    model_reasoned_proposal: Any = None
    # Harvest drafts from the existing reasoning/tool loop. This avoids
    # paying for a separate tools-free model request when the model has
    # already authored a suitable answer.
    candidate_narrative: Any = None
    planning_model_ms = 0
    planning_model_calls = 0
    reason = "round_budget_reached"
    for round_no in range(max_rounds + 1):
        if round_no >= max_rounds:
            # One model-chosen follow-up chance when warning evidence lacks
            # source-attested command actor provenance.
            causal_coverage_gap = gap_for_target(
                witnesses, sorted(focus_ids),
                can_read_events=gateway_offers_operation(
                    manifest, discovered, "hub_list_device_events"),
            )
            if (causal_coverage_challenge_used or causal_coverage_gap is None
                    or attempted >= max_reads
                    or deadline - time.monotonic() <= 4):
                break
            causal_coverage_challenge_used = True
            if causal_coverage_gap.get("kind") == "target_generic_warning_origin_unverified":
                if causal_coverage_gap.get("candidate_read") is None:
                    instruction = (
                        "The target-specific WARN log has already been sampled "
                        "and app callers were independently observed at other "
                        "times. The generic warning remains causally "
                        "unattributed. Do not retry the same WARN scope with "
                        "a larger limit. Choose only independently grounded "
                        "new evidence (a distinct supported historical window, "
                        "attested source, or runtime data), or finish with the "
                        "verified limits. No read is required to justify an "
                        "unknown root cause.")
                else:
                    instruction = (
                        "The device's app command issuers are already verified, "
                        "but no command in the bounded sample is linked to this "
                        "separate generic load-warning interval. Do not claim "
                        "the device's callers are unknown. A target-specific "
                        "WARN read or independent source/performance evidence "
                        "could discriminate mechanisms, without proving them.")
            elif causal_coverage_gap.get("kind") == "target_driver_execution_mechanism_unverified":
                instruction = (
                    "The device event history ALREADY attests calling apps "
                    "in the warning period. Do NOT claim the caller is unknown "
                    "or invent command-<internal driver method> as an event "
                    "filter. The driver callback mechanism is unverified. "
                    "Consider a permitted source-attested app configuration "
                    "read for one known caller before searching the entire "
                    "driver catalogue. Do not assert causal proof.")
            else:
                instruction = (
                    "A scoped device event read is insufficient if its "
                    "returned timestamps miss the warning window or do not "
                    "establish a relevant issuer. If material, choose a bounded "
                    "history read with supported hoursBack/attribute filters. "
                    "No command history is complete merely because a read succeeded.")
            messages.append({"role": "user", "content":
                "Evidence coverage assessment from typed source observations. "
                + instruction + " Candidate evidence: "
                + json.dumps(causal_coverage_gap, default=str)[:2500]})
        rounds += 1
        left = deadline - time.monotonic()
        if left <= 1:
            reason = "deadline_reached"
            break
        start_planning = time.monotonic()
        planning_model_calls += 1
        try:
            reply = await asyncio.wait_for(
                chat(messages, offered),
                timeout=min(max(1.0, model_timeout), left),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            reason = "model_unavailable"
            break
        finally:
            planning_model_ms += round(
                (time.monotonic() - start_planning) * 1000)
        if not isinstance(reply, dict):
            reason = "invalid_model_reply"
            break
        # This is a *proposal*, never answer authority. The entire draft
        # still goes through the independent final evidence/source verifier.
        # Tool replies may carry a candidate without extra inference calls.
        content = reply.get("content")
        if enable_verified_narrative and isinstance(content, str):
            try:
                proposed = json.loads(content) if len(content) <= 7500 else None
            except (ValueError, TypeError):
                proposed = None
            if isinstance(proposed, dict) and isinstance(
                    proposed.get("findings"), list):
                candidate_narrative = {"findings": proposed["findings"]}
        calls = reply.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            # A model may finish after finding which app changed the actuator
            # without checking why the app made that decision. Ask once for
            # independent upstream decision evidence when the live READ
            # manifest can provide it. This NEVER executes a read for the
            # model, and never grants a new identity or tool permission.
            pending_decision = controller_decision_followup(
                witnesses, sorted(focus_ids),
                dated_incident_evidence(question, witnesses, sorted(focus_ids)),
                app_logs_offered=bool(_verified_gateways_for_operation(
                    "hub_get_logs", {}, manifest, discovered)),
                question=question)
            if (enable_model_reasoned_assessment
                    and pending_decision is not None
                    and not upstream_decision_challenge_used
                    and round_no + 1 < max_rounds
                    and attempted < max_reads
                    and deadline - time.monotonic() > 5):
                upstream_decision_challenge_used = True
                messages.append({"role": "assistant",
                                 "content": _text(reply.get("content"), 450)})
                messages.append({"role": "user", "content":
                    "Your current observations establish the actuator's "
                    "controlling command, not the controller's decision "
                    "inputs. Before finishing, decide whether an independent "
                    "READ of this verified issuer's execution history is "
                    "available and useful. You may choose a live-offered "
                    "read with source-attested app ID, or explain why it "
                    "cannot be obtained. Do not repeat configuration "
                    "metadata as historical execution evidence. Evidence: "
                    + json.dumps(pending_decision,ensure_ascii=True)[:2200]})
                continue
            # General evidence-coverage critique, not question-word routing.
            # A model must not call a noisy INFO page a log error audit.
            # One bounded extra model opportunity can request a better read.
            severity_read_completed = any(
                w.get("operation") == "hub_get_logs"
                and str(w.get("read_filters", {}).get("level", "")).lower()
                in ("warn", "error")
                for w in witnesses
            )
            unfiltered_log_gap = not severity_read_completed and any(
                isinstance(w.get("source_data"), dict)
                and isinstance(w["source_data"].get("log_summary"), dict)
                and w["source_data"]["log_summary"].get(
                    "warning_error_group_count") == 0
                and w.get("read_filters", {}).get("level") is None
                # An app-specific INFO decision trace is not a request for
                # whole-hub WARN/ERROR auditing. Its absence of warnings
                # must not trigger an irrelevant severity-read challenge.
                and w.get("read_filters", {}).get("appId") is None
                and w["source_data"]["log_summary"].get(
                    "level_counts_in_returned_rows", {}).get("INFO", 0) > 0
                for w in witnesses
            )
            if (unfiltered_log_gap and not coverage_challenge_used
                    and round_no + 1 < max_rounds
                    and attempted < max_reads
                    and deadline - time.monotonic() > 3):
                coverage_challenge_used = True
                messages.append({"role": "assistant",
                                 "content": _text(reply.get("content"), 450)})
                messages.append({"role": "user", "content":
                                 "Evidence coverage check: the returned log "
                                 "page contains INFO but no WARN/ERROR, and "
                                 "you have not made a severity-filtered log "
                                 "read. Do not infer no problems from that "
                                 "sample. Choose an independently permitted "
                                 "discriminating MCP read or explicitly state "
                                 "this limitation."})
                continue
            # The claim selector has an independent strict top-level
            # contract; strip a separately validated explanatory draft so
            # the presence of findings cannot invalidate genuine claim IDs.
            selected = reply.get("content")
            if isinstance(selected, str):
                try:
                    full = json.loads(selected) if len(selected) <= 7500 else None
                except (ValueError, TypeError):
                    full = None
                if isinstance(full, dict) and isinstance(
                        full.get("claims"), list):
                    selected = json.dumps({"claims": full["claims"]})
            in_loop_incident = (
                dated_incident_evidence(question, witnesses, sorted(focus_ids))
                if enable_model_reasoned_assessment else None)
            if (in_loop_incident is not None
                    and in_loop_incident["material_event_count"] >= 2):
                # A reasoning-enabled model may finish using the planning
                # transcript. Reuse an already structured proposal without
                # another model call; otherwise request the *separate*
                # evidence-linked final reasoning contract. Never publish
                # the raw in-loop natural prose or a claim count instead.
                try:
                    parsed_draft = (json.loads(selected)
                                    if isinstance(selected, str)
                                    and len(selected) <= 7500 else None)
                except (ValueError, TypeError):
                    parsed_draft = None
                if isinstance(parsed_draft, dict) and parsed_draft.get("hypothesis"):
                    model_reasoned_proposal = selected
                    answer_text = _answer_text(selected, 4500)
                else:
                    answer_text = ""
            else:
                model_claim_proposal = selected
                answer_text = _answer_text(reply.get("content"), 4500)
            reason = "model_finished"
            break
        # Native assistant calls are written back to the model's transcript
        # only as data, not as permissions or physical state proof.
        messages.append({"role": "assistant", "content": _text(reply.get("content"), 500),
                         "tool_calls": calls[:2]})
        accepted_this_round = 0
        for call in calls[:2]:
            parsed = _arguments(call)
            if parsed is None:
                failures.append({"code": "invalid_tool_call"})
                messages.append({"role": "tool", "content": json.dumps(
                    {"error": "invalid_tool_call"})})
                continue
            name, args = parsed
            key = json.dumps([name, args], sort_keys=True, default=str)
            if name == HANDOFF_NAME:
                # Model-led semantic refusal is not Hubitat authority. The
                # tool is host-local and never reaches the MCP executor.
                # Explicitly preserve any earlier READ count if the model
                # made a suboptimal late handoff.
                if args != {}:
                    failures.append({"tool": name, "code": "invalid_handoff_args"})
                    messages.append({"role": "tool", "content":
                                     '{"error":"invalid_handoff_args"}'})
                    continue
                return handoff_result(
                    reads_executed=attempted,
                    successful_reads=len(witnesses),
                    planning_model_calls=planning_model_calls,
                    elapsed_ms=round((time.monotonic() - started)*1000),
                )
            if name == LOOKUP_NAME:
                # The model chooses WHEN a device label needs resolution.
                # This is a bounded host-local READ, never forwarded as an MCP
                # command. Only one unique match is authorised for follow-up.
                if (set(args) != {"name"} or not isinstance(args["name"], str)
                        or len(args["name"]) > 120):
                    failures.append({"tool": name, "code": "invalid_identity_query"})
                    messages.append({"role": "tool", "content": json.dumps({
                        "status": "invalid_identity_query", "matches": []})})
                    continue
                if key in prior or len(named_identity_lookups) >= 3:
                    failures.append({"tool": name, "code": "duplicate_or_excess_identity_lookup"})
                    messages.append({"role": "tool", "content": json.dumps({
                        "status": "lookup_budget_exhausted", "matches": []})})
                    continue
                prior.add(key)
                accepted_this_round += 1
                identity_lookup_attempted = True
                start_identity = time.monotonic()
                found = await resolve_named_device(
                    mcp, args["name"],
                    timeout=min(6.0, max(0.1, deadline-time.monotonic())),
                )
                identity_lookup_ms += round(
                    (time.monotonic()-start_identity)*1000)
                if found["status"] == "unique":
                    verified_ids.add(found["matches"][0]["id"])
                    verified_typed["device"].add(found["matches"][0]["id"])
                    focus_ids.add(found["matches"][0]["id"])
                if found["status"] == "candidate_group":
                    # Every candidate was returned by current authoritative
                    # identity, but no candidate is automatically selected
                    # or considered a verified room/group member. This only
                    # permits model-chosen, separately guarded READs.
                    for item in found["matches"]:
                        verified_ids.add(item["id"])
                        verified_typed["device"].add(item["id"])
                named_identity_lookups.append({
                    "query": _text(args["name"], 100),
                    "status": found["status"],
                    "count": len(found["matches"]),
                    "candidate_ids": (
                        [m["id"] for m in found["matches"]]
                        if found["status"] == "candidate_group" else []),
                })
                messages.append({"role": "tool", "content": json.dumps({
                    **found, "authority": "fresh_complete_hubitat_identity",
                    "read_only": True,
                }, ensure_ascii=True)})
                continue
            # Only the model's already chosen READ operation may have a
            # unique source-attested device and explicit incident date
            # normalized; subsequent host guard verifies the full result.
            args, repair = normalize_selected_history_read(
                name, args, focus_ids=focus_ids,
                verified_device_ids=verified_typed["device"], question=question)
            if repair is not None:
                normalized_history_reads.append(repair)
                key = json.dumps([name, args], sort_keys=True, default=str)
            issue = _guard(name, args, manifest, discovered, verified_ids,
                           verified_typed)
            op_requested = args.get("tool") if name.startswith("hub_read_") else name
            if (name, str(op_requested)) in timed_out_operations:
                issue = "operation_prior_timeout"
            inner = args.get("args", args)
            target = (str(inner.get("deviceId") or inner.get("appId") or "")
                      if isinstance(inner, dict) else "")
            scoped_key = (str(op_requested), target)
            if (target and failed_scoped_reads.get(scoped_key, 0) >= 2
                    and issue is None):
                blocked_repeat_errors += 1
                issue = "repeated_target_read_error"
            if issue == "target_id_not_verified_from_live_source":
                # Lookup happens only when the model proposes a target-specific
                # READ whose ID was not already attested in a source receipt.
                # Use cached or one-shot live context instead of mandatory
                # full 20s inventory; failed lookup never authorises a call.
                inner = args.get("args", args)
                unknown = {
                    str(inner[k]) for k in ("deviceId",)
                    if isinstance(inner, dict) and type(inner.get(k)) in (str, int)
                    and str(inner[k]).isdecimal()
                }
                lookup = getattr(mcp, "get_device_identities", None)
                if unknown and callable(lookup) and not identity_lookup_attempted:
                    identity_lookup_attempted = True
                    before_identity = time.monotonic()
                    try:
                        identities = await asyncio.wait_for(
                            lookup(),
                            timeout=min(6.0, max(0.1, deadline - time.monotonic())),
                        )
                        confirmed_devices = {
                            str(row.get("id") or row.get("deviceId"))
                            for row in identities[:800]
                            if isinstance(row, dict)
                            and str(row.get("id") or row.get("deviceId") or "").isdecimal()
                        }
                        verified_ids.update(confirmed_devices)
                        verified_typed["device"].update(confirmed_devices)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        pass
                    finally:
                        identity_lookup_ms += round(
                            (time.monotonic() - before_identity) * 1000)
                    issue = _guard(name, args, manifest, discovered, verified_ids,
                           verified_typed)
            # When live identity has already provided a bounded list of
            # possible named devices, another unscoped full-device inventory
            # cannot help resolve *those* IDs. Decline that expensive
            # fallback without consuming a READ or a 20s gateway timeout;
            # offer the independently attested candidate IDs instead.
            if (issue is None and op_requested == "hub_list_devices"
                    and any(isinstance(row, dict)
                            and row.get("status") == "candidate_group"
                            and row.get("candidate_ids")
                            for row in named_identity_lookups)):
                issue = "bounded_identity_candidates_available"
            # A returned Hubitat room catalogue can identify a room named in
            # the original question. With a live-offered targeted room READ,
            # an unfiltered whole-hub inventory is not a useful substitute.
            # This is based on independently retrieved room names, not a
            # keyword-controlled question route or inferred device identity.
            if (issue is None and op_requested == "hub_list_devices"
                    and any(question_room_matches(question, row)
                            for row in room_name_catalogs)
                    and _verified_gateways_for_operation(
                        "hub_get_room", {}, manifest, discovered)):
                issue = "bounded_room_catalog_available"
            if issue is None and isinstance(inner, dict):
                issue = target_history_scope_problem(
                    str(op_requested), inner, sorted(focus_ids), witnesses)
            if (issue is None and op_requested == "hub_get_logs"
                    and isinstance(inner, dict)
                    and repeated_broad_log_scope(inner, witnesses)):
                issue = "repeated_broad_log_scope"
            if key in prior:
                issue = "duplicate_read"
            rejected_key = str(op_requested) if issue in (
                "missing_required_operation_fields",
                "target_device_history_scope_missing",
            ) else None
            if rejected_key and invalid_contract_attempts.get(rejected_key, 0) >= 2:
                issue = "repeated_invalid_read_proposal"
            if issue is not None:
                failures.append({"tool": name[:80], "operation": op_requested,
                                 "code": issue})
                if rejected_key:
                    invalid_contract_attempts[rejected_key] = (
                        invalid_contract_attempts.get(rejected_key, 0) + 1)
                if issue == "target_device_history_scope_missing":
                    rejected_scope_history_reads += 1
                hint = guidance_for(issue) or "Choose a different verified read"
                if issue == "bounded_room_catalog_available":
                    rooms = list(dict.fromkeys(
                        name for catalog in room_name_catalogs
                        for name in question_room_matches(question, catalog)))
                    hint = (
                        "The actual Hubitat room catalogue already lists "
                        + ", ".join(rooms[:5]) + ". The user question names "
                        "a source-attested room. Prefer a separately authorised "
                        "hub_get_room read for that exact room, then guarded "
                        "individual hub_get_device reads for its reported "
                        "members. Room names do not establish membership "
                        "or device state. No whole-hub inventory was executed.")
                if issue == "bounded_identity_candidates_available":
                    groups = [
                        row for row in named_identity_lookups
                        if isinstance(row, dict)
                        and row.get("status") == "candidate_group"
                        and row.get("candidate_ids")
                    ]
                    candidates = groups[-1]["candidate_ids"][:8]
                    hint = (
                        "Current authoritative identity already returned "
                        "candidate device IDs " + ", ".join(candidates)
                        + ". Request model-selected hub_get_device READs "
                        "with those exact IDs individually; name-prefix "
                        "matches do not prove membership or actual state. "
                        "The unscoped full-device listing is unnecessary.")
                if (issue in ("missing_required_operation_fields",
                              "target_device_history_scope_missing")
                        and len(focus_ids) == 1):
                    # A model can omit the same required ID repeatedly even
                    # after resolving it. Supply only the already verified
                    # subject to the model; never auto-insert/execute a call.
                    hint += (" The independently verified current target is "
                             "deviceId=" + next(iter(focus_ids)) +
                             ". Explicitly supply that deviceId to the "
                             "relevant read operation; the host will not "
                             "insert it or execute the rejected proposal.")
                contract = (read_contract_feedback(
                    name, args, verified_typed, focus_ids=sorted(focus_ids))
                    if issue in ("missing_required_operation_fields",
                                 "target_device_history_scope_missing")
                    else None)
                gateway_choices = (
                    _verified_gateways_for_operation(
                        str(op_requested),
                        inner if isinstance(inner, dict) else {},
                        manifest, discovered)
                    if issue == "operation_not_independently_discovered"
                    else [])
                messages.append({"role": "tool", "content": json.dumps({
                    "error": issue, "hint": hint,
                    **({"verified_read_gateways": gateway_choices}
                       if issue == "operation_not_independently_discovered"
                       else {}),
                    **({"required_read_contract": contract}
                       if contract is not None else {}),
                })})
                continue
            if attempted >= max_reads:
                reason = "read_budget_reached"
                messages.append({"role": "tool", "content": '{"error":"read_budget_reached"}'})
                break
            if deadline - time.monotonic() <= 0.5:
                reason = "deadline_reached"
                break
            attempted += 1
            accepted_this_round += 1
            prior.add(key)
            op = args.get("tool") if name.startswith("hub_read_") else name
            before = time.monotonic()
            result = None
            error = None
            execution = None
            try:
                execution = await asyncio.wait_for(
                    executor.execute(name, args, tool=manifest[name],
                                     record_evidence=False),
                    timeout=min(max(1.0, per_read_timeout),
                                max(0.1, deadline - time.monotonic())),
                )
                error = classify_execution(execution, name)
                if (execution.effect is not ToolEffect.READ
                        or not execution.success
                        or execution.result is None
                        or not tool_succeeded(execution.result)):
                    error = error or "mcp_tool_reported_error"
                else:
                    result = execution.result
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                error = "read_timeout"
            except Exception as exc:
                error = classify_exception(exc)
            if error:
                if target:
                    failed_scoped_reads[scoped_key] = (
                        failed_scoped_reads.get(scoped_key, 0) + 1
                    )
                if error == "read_timeout":
                    timed_out_operations.add((name, str(op)))
                hint = (_oversized_hint(execution.result)
                        if execution is not None and execution.name == name
                        else None)
                safe_error = "response_too_large" if hint else error
                # Preserve only bounded, non-secret scope fields from
                # failed READ proposals. The failed configuration attempt
                # is a real source-path limit, not an untried option.
                safe_failure_filters = {
                    k: inner[k] for k in ("deviceId", "appId", "mode")
                    if isinstance(inner, dict) and k in inner
                    and type(inner[k]) in (str, int)
                    and len(str(inner[k])) <= 32
                }
                failures.append({"tool": name, "operation": op,
                                 "code": safe_error,
                                 "read_filters": safe_failure_filters,
                                 "elapsed_ms":
                                 round((time.monotonic()-before)*1000)})
                messages.append({"role": "tool", "content": json.dumps({
                    "error": safe_error, "source_complete": False,
                    **({"suggestion": hint} if hint else {}),
                    **({"hint": guidance_for(safe_error)}
                       if guidance_for(safe_error) else {}),
                })})
                continue
            assert result is not None
            verified_ids.update(attested_source_ids(op, result.data))
            # A source-verified room response establishes membership only,
            # not current device state. Authorise its actual member IDs for
            # individually model-selected, guarded READs.
            room_receipt = (
                verified_room_inventory(
                    result.data, inner.get("room"), read=attempted)
                if op == "hub_get_room" and isinstance(inner, dict)
                else None)
            if room_receipt is not None:
                room_inventories.append(room_receipt)
                verified_typed["device"].update(room_receipt["member_ids"])
                verified_ids.update(room_receipt["member_ids"])
            # The read receipts attest app and driver identities separately.
            # Event issuers become trusted app IDs only for a device-scoped
            # read already approved by the host; no app identifier is guessed.
            typed = source_identities(
                op, result.data,
                scoped_device_id=(
                    target if isinstance(inner, dict)
                    and inner.get("deviceId") is not None
                    and target in verified_typed["device"]
                    else None
                ),
            )
            for entity_type, identities in typed.items():
                verified_typed[entity_type].update(identities)
                verified_ids.update(identities)
            if name == "hub_search_tools":
                for gateway, ops in _observed_operations(result, manifest).items():
                    discovered.setdefault(gateway, set()).update(ops)
            summary = _payload(result, op, read_filters=inner)
            if op == "hub_list_rooms" and isinstance(summary, dict) and isinstance(
                    summary.get("rooms"), list):
                room_name_catalogs.append(summary)
            # hub_get_device may precede the optional named-lookup tool.
            # Anchor only after an independently allowed, successful READ
            # returned matching target identity and the user referenced it.
            if isinstance(inner, dict) and isinstance(summary, dict):
                anchored = verified_device_focus(
                    question, str(op), inner, summary,
                    verified_typed["device"])
                if anchored and anchored["device_id"] not in focus_ids:
                    focus_ids.add(anchored["device_id"])
                    verified_focus_receipts.append({
                        "read": attempted,
                        "device_id": anchored["device_id"],
                        "identity_basis": anchored["identity_basis"],
                        **({"source_kind": anchored["source_kind"]}
                           if anchored.get("source_kind") else {}),
                    })
            if op == "hub_get_source" and isinstance(inner, dict):
                requested_type = inner.get("type")
                requested_id = str(inner.get("id") or "")
                if (requested_type in ("app", "driver") and requested_id
                        in verified_typed[requested_type]):
                    # The actual response must still be independently
                    # checked for a matching ID and full source coverage.
                    # Prior source-backed named-method WARNs provide
                    # lexical focus only; no execution is inferred. An app
                    # source may only use warnings from that app, and a
                    # driver read may use the currently verified device's
                    # method warnings. Never synthesize a command.
                    named_methods = []
                    for prior_read in witnesses:
                        if prior_read.get("operation") != "hub_get_logs":
                            continue
                        groups = prior_read.get("source_data", {}).get(
                            "log_summary", {}).get("warning_error_groups", [])
                        for group in groups:
                            if not isinstance(group, dict):
                                continue
                            observed_id = str(group.get("source_id") or "")
                            kind = str(group.get("source_type") or "")
                            eligible = (
                                requested_type == "app"
                                and kind == "app" and observed_id == requested_id
                            ) or (
                                requested_type == "driver"
                                and kind in ("dev", "device")
                                and observed_id in focus_ids
                            )
                            if not eligible:
                                continue
                            for match in re.finditer(
                                r"\bmethod\s+([A-Za-z_][A-Za-z0-9_]*)\b",
                                str(group.get("message") or ""), re.I,
                            ):
                                method = match.group(1)
                                if method not in named_methods:
                                    named_methods.append(method)
                    summary = source_read_summary(
                        result.data, requested_type=requested_type,
                        requested_id=requested_id,
                        focus_methods=named_methods[:12])
            if op == "hub_get_app_config" and isinstance(inner, dict):
                arg_id = str(inner.get("appId") or "")
                if arg_id in verified_typed["app"]:
                    summary["requested_app_id"] = arg_id
                    summary["requested_app_id_verified"] = True
                    source_id = summary.get("id") or summary.get("appId")
                    if source_id is not None:
                        summary["source_app_id_matches_request"] = (
                            str(source_id) == arg_id)
            if name == "hub_search_tools":
                found_keys = useful_discovery_fingerprint(summary)
                if found_keys and found_keys in discovery_fingerprints:
                    repeated_discovery += 1
                if found_keys:
                    discovery_fingerprints.add(found_keys)
            fingerprint = read_fingerprint(op, summary)
            repeat_snapshot = bool(fingerprint and fingerprint in seen_fingerprints)
            repeat_log = (op == "hub_get_logs"
                          and repeated_log_evidence(witnesses, summary))
            repeat_events = (
                op == "hub_list_device_events"
                and repeated_event_evidence(
                    witnesses, summary,
                    scoped_device_id=str(inner.get("deviceId"))
                    if isinstance(inner, dict) and inner.get("deviceId") is not None
                    else None)
            )
            repeated_evidence = repeat_snapshot or repeat_log or repeat_events
            if fingerprint:
                seen_fingerprints.add(fingerprint)
            if repeated_evidence:
                redundant_evidence_reads += 1
            if repeat_snapshot:
                redundant_snapshot_reads += 1
            if repeat_log:
                redundant_log_subsets += 1
            if repeat_events:
                redundant_event_subsets += 1
            witness = {
                "read": attempted,
                "tool": name, "operation": op,
                "read_filters": {
                    k: v for k, v in (
                        args.get("args") if isinstance(args.get("args"), dict)
                        else args
                    ).items()
                    if k in ("level", "limit", "mode", "deviceId", "appId",
                             "id", "type", "since", "until", "cursor",
                             "pattern", "attribute", "hoursBack", "room")
                    and type(v) in (str, int) and len(str(v)) < 50
                },
                "elapsed_ms": round((time.monotonic()-before)*1000),
                "source_data": summary,
                "source_complete": False,
                "redundant_evidence": repeated_evidence,
            }
            witnesses.append(witness)
            view = ({"read_id": attempted, "operation": op,
                     "no_new_evidence": True,
                     "hint": ("This log sample is already contained in previous "
                              "target WARN/ERROR evidence. Read a different "
                              "source or historical incident window."
                              if repeat_log else
                              "This event-history sample is already contained "
                              "in a prior device-scoped read; investigate the "
                              "verified command issuer or driver mechanism."
                              if repeat_events else
                              "The same device attributes were already retrieved. "
                              "Choose an independent discriminator or finish.")}
                    if repeated_evidence else {
                        "read_id": attempted, "operation": op,
                        "source_data": focused_model_view(
                            op, summary, sorted(focus_ids),
                            caller_app_ids=sorted(verified_caller_app_ids(
                                witnesses, focus_ids))),
                        "source_complete": False,
                    })
            if op == "hub_list_rules" and isinstance(summary, dict):
                rules = summary.get("rules")
                if isinstance(rules, list) and any(
                    isinstance(rule, dict)
                    and str(rule.get("type")) == "Rule-5.1"
                    for rule in rules[:100]
                ):
                    view["rule_engine_inspection_hint"] = (
                        "The source returned Rule-5.1 (Rule Machine) apps. "
                        "For an independently verified Rule-5.1 app ID, "
                        "inspect its live-offered hub_get_app_config / "
                        "app page or Rule Machine read operation. "
                        "hub_get_custom_rule refers to a different custom "
                        "rule engine; an empty custom-rule response does "
                        "not establish absence of Rule Machine actions.")
            if op == "hub_list_rooms" and room_name_catalogs:
                catalog = room_name_catalogs[-1]
                matched = question_room_matches(question, catalog)
                view["verified_room_name_catalog"] = {
                    "names": catalog["rooms"],
                    "returned_room_count": catalog["returned_room_count"],
                    "name_catalog_complete": catalog["name_catalog_complete"],
                    "room_membership_verified": False,
                    "question_matched_rooms": matched,
                    "next_read": (
                        "Model may choose a LIVE-advertised hub_get_room "
                        "with args.room equal to a source-attested name; "
                        "then individually read source-verified device IDs. "
                        "Do not use an unbounded hub_list_devices read."
                        if matched else "Choose only needed targeted reads"),
                }
            if room_receipt is not None:
                view["verified_room_inventory"] = {
                    "name": room_receipt["name"],
                    "members": room_receipt["members"],
                    "inventory_complete": room_receipt["inventory_complete"],
                    "read_only": True,
                    "state_not_covered": "Individually read any relevant room device state",
                }
            if focus_ids and op in ("hub_list_device_events", "hub_get_logs",
                                    "hub_get_app_config"):
                decision = controller_decision_followup(
                    witnesses, sorted(focus_ids),
                    dated_incident_evidence(question, witnesses, sorted(focus_ids)),
                    app_logs_offered=bool(_verified_gateways_for_operation(
                        "hub_get_logs", {}, manifest, discovered)),
                    question=question)
                if decision is not None:
                    view["upstream_controller_decision_gap"] = decision
                if op == "hub_get_logs" and summary.get("app_execution_lines"):
                    # Bring the independently matched source-log anchors back
                    # into the planning context, not merely the final report.
                    linked = dated_incident_evidence(
                        question, witnesses, sorted(focus_ids))
                    if linked is not None:
                        view["user_incident_evidence_coverage"] = linked
            if focus_ids and op == "hub_list_device_events":
                if str(inner.get("deviceId")) in focus_ids:
                    # Make the already observed bounded source window explicit
                    # before a model asks for a narrower overlapping read.
                    # The model may still select a legitimate distinct read.
                    view["event_read_frontier"] = {
                        "deviceId": str(inner["deviceId"]),
                        "read_id": attempted,
                        "source_returned_rows": summary.get("count"),
                        "projected_rows": summary.get("returned_event_rows"),
                        "oldest_returned": summary.get("oldest_returned"),
                        "newest_returned": summary.get("newest_returned"),
                        "history_complete": False,
                        "requested_user_window": requested_history_bounds(question),
                        "advice": (
                            "These individual source events have already "
                            "been observed. A narrower interval with the "
                            "same returned rows is not independent evidence. "
                            "If investigating a distinct historical period, "
                            "choose a read scope capable of reaching that "
                            "period, or select a different verified app, "
                            "device, performance or source read. Do not "
                            "treat bounded events as complete history."),
                    }
                incident_relevance = dated_incident_evidence(
                    question, witnesses, sorted(focus_ids))
                if incident_relevance is not None:
                    # Separate relevant event coverage from a large count
                    # of events from later, unrelated days. The model,
                    # not the host, chooses any follow-up READ.
                    view["user_incident_evidence_coverage"] = incident_relevance
                packet = incident_attribution_packet(
                    witnesses, sorted(focus_ids))
                if packet is not None:
                    view["incident_attribution_evidence"] = packet
            if focus_ids and op in ("hub_list_device_events", "hub_get_device"):
                lead = verified_temporal_lead(witnesses, sorted(focus_ids))
                if lead is not None:
                    view["verified_command_time_lead"] = {
                        **lead,
                        "next_read_hint": (
                            "A command and source-reported contact timestamp are "
                            "close, but execution and mechanism are unverified. "
                            "Use independently discovered READs of the issuer "
                            "app configuration and device communication evidence "
                            "to distinguish possible causes. Never infer a "
                            "physical power cut solely from this timestamp."),
                    }
            if focus_ids and op in ("hub_list_device_events", "hub_get_logs", "hub_get_device"):
                gap = gap_for_target(
                    witnesses, sorted(focus_ids),
                    can_read_events=gateway_offers_operation(
                        manifest, discovered, "hub_list_device_events"),
                )
                if gap and (op == "hub_list_device_events" or repeat_snapshot):
                    # Evidence-specific guidance immediately after the source
                    # read, while model rounds remain. Suggestions never grant
                    # a read or execute a Hubitat command.
                    view["evidence_coverage_hint"] = {
                        k: gap[k] for k in (
                            "kind", "observed_calling_app_ids", "warning_window",
                            "candidate_read", "candidate_filters", "materiality",
                            "limitation",
                        ) if k in gap
                    }
            if focus_ids and op in (
                "hub_list_device_events", "hub_get_device", "hub_get_source",
            ):
                # Evidence-derived next action only. The model is free to
                # choose another READ; all proposed operations are checked by
                # the same host safety/identity contracts before execution.
                next_source = source_path_followup(
                    witnesses, sorted(focus_ids), verified_typed["driver"],
                    failures=failures)
                if next_source is not None:
                    view["source_path_followup"] = next_source
            if witnesses and not (enable_model_reasoned_assessment and focus_ids):
                # The reasoning-model planning phase needs actual source
                # evidence, not a distracting catalog of command counts.
                # Preserve the legacy catalog for non-incident/readiness
                # paths; final publication checks are unchanged.
                view["source_claim_catalog"] = [
                    {"id": c["id"], "statement": c["statement"],
                     "evidence_reads": c["evidence_reads"]}
                    for c in claim_catalog(witnesses, sorted(focus_ids), limit=28)
                ]
            if name == "hub_search_tools" and repeated_discovery > 0:
                view["discovery_advice"] = (
                    "This search repeats a previously seen tool set. "
                    "Prefer a targeted evidence read instead.")
            # Put the claim IDs before large event summaries so the
            # bounded tool transcript does not truncate the only useful
            # selection vocabulary. Never trust model-supplied claim text.
            if "source_claim_catalog" in view:
                view = {"source_claim_catalog": view.pop("source_claim_catalog"),
                        **view}
            if "user_incident_evidence_coverage" in view:
                # When tool JSON is bounded, the event sequence nearest
                # the question's own time is more useful than recent
                # telemetry or general fact catalogs. Preserve raw receipt
                # in diagnostics, but show this summary first to the AI.
                view = {"user_incident_evidence_coverage":
                        view.pop("user_incident_evidence_coverage"), **view}
            messages.append({"role": "tool", "content":
                             json.dumps(view, ensure_ascii=True)[:12000]})
        if redundant_snapshot_reads >= 2 and focus_ids:
            reason = "no_new_source_evidence"
            break
        if attempted >= max_reads:
            reason = "read_budget_reached"
            break
        if accepted_this_round == 0:
            if any(count >= 2 for count in invalid_contract_attempts.values()):
                reason = "repeated_invalid_proposal"
                break
            recovery_rejections += 1
            # One bounded repair round after malformed arguments is useful;
            # repeated disallowed or duplicate operations must never loop.
            if recovery_rejections >= 2 or round_no + 1 >= max_rounds:
                reason = "no_approved_reads"
                break
        else:
            recovery_rejections = 0
    causal_coverage_gap = gap_for_target(
        witnesses, sorted(focus_ids),
        can_read_events=gateway_offers_operation(
            manifest, discovered, "hub_list_device_events"),
    )
    source_readiness = source_path_followup(
        witnesses, sorted(focus_ids), verified_typed["driver"],
        failures=failures)
    # The source-authoritative generic-warning report supersedes an
    # unverified model-only synthesis. Skip that costly call only when
    # the actual WARN and target-scoped device-event evidence both exist.
    # This does not affect model-controlled read selection or other topics.
    preliminary_incident = incident_attribution_packet(
        witnesses, sorted(focus_ids))
    # Evidence-class diversity is a measurable signal that a final extra
    # model-only JSON claim selection is unlikely to add new source facts.
    # Only apply after an explicit READ budget boundary, and only after
    # at least two distinct read operations and two fact classes.
    incident_relevance = dated_incident_evidence(
        question, witnesses, sorted(focus_ids))
    incident_gap = natural_incident_gap_answer(
        question, witnesses, named_identity_lookups, sorted(focus_ids))
    readiness = evidence_readiness(
        witnesses, claim_catalog(witnesses, sorted(focus_ids)),
        stop_reason=reason,
        incident_evidence_present=(None if incident_relevance is None
            else incident_relevance["incident_answer_evidence_present"]))
    # A complete, independently ID-joined device group already contains the
    # entire bounded answer vocabulary. Do not spend up to eight seconds
    # requesting a second model-only claim selection which could only select
    # a subset of source facts or return malformed JSON. The model remains
    # responsible for choosing the names and all READ operations.
    complete_group_evidence = (
        natural_entity_answer(named_identity_lookups, witnesses, room_inventories)
        if not focus_ids and
        not (preliminary_incident is not None
             and source_bound_incident_required(preliminary_incident))
        else None)
    if (not answer_text and complete_group_evidence is not None
            and complete_group_evidence.get("room_unread_count", 0) == 0
            and complete_group_evidence.get("room_inventory_complete", True)):
        final_synthesis_skipped_reason = "complete_verified_entity_group"
    if (not answer_text and preliminary_incident is not None
            and source_bound_incident_required(preliminary_incident)
            and preliminary_incident.get("scoped_event_history_available")):
        final_synthesis_skipped_reason = "host_authoritative_incident_evidence"
    # If the model exhausted planning after collecting both a subject's
    # current-state read and target-specific warnings, another expensive
    # model-only pass is often futile. Keep the host-attested conclusion
    # immediately available rather than losing eight seconds to a timeout.
    def _has_independent_target_evidence() -> bool:
        if not focus_ids:
            return False
        current = any(
            w.get("operation") == "hub_get_device"
            and str(w.get("source_data", {}).get("id")) in focus_ids
            for w in witnesses
        )
        warnings = any(
            w.get("operation") == "hub_get_logs"
            and any(
                isinstance(g, dict) and str(g.get("source_id")) in focus_ids
                for g in w.get("source_data", {}).get("log_summary", {})
                          .get("warning_error_groups", [])
            )
            for w in witnesses
        )
        return current and warnings
    if (not answer_text and reason == "repeated_invalid_proposal"
            and focus_ids
            and any(
                w.get("operation") == "hub_get_logs"
                and any(isinstance(g, dict)
                        and str(g.get("source_id")) in focus_ids
                        for g in w.get("source_data", {}).get("log_summary", {})
                                  .get("warning_error_groups", []))
                for w in witnesses
            )):
        # Invalid model proposals add no new knowledge. A source-backed
        # partial answer is preferable to waiting on another doomed
        # synthesis call; keep uncertainty and incomplete coverage visible.
        final_synthesis_skipped_reason = "repeated_invalid_reads_with_target_warnings"
    if (not answer_text and final_synthesis_skipped_reason is None
            and reason in (
            "round_budget_reached", "no_approved_reads", "no_new_source_evidence",
            "read_budget_reached")
            and _has_independent_target_evidence()
            and (rounds >= max_rounds or blocked_repeat_errors
                 or sum(failed_scoped_reads.values()) >= 2
                 or redundant_evidence_reads >= 2)):
        final_synthesis_skipped_reason = "source_evidence_at_investigation_limit"
    reasoned_incident_eligible = (
        enable_model_reasoned_assessment
        and incident_relevance is not None
        and incident_relevance["material_event_count"] >= 2
        and len(focus_ids) == 1)
    # A general factual-catalog shortcut must not suppress model reasoning
    # on a dated incident when there is actual material source evidence.
    if (witnesses and not answer_text
            and final_synthesis_skipped_reason is None
            and readiness["host_factual_brief_ready"]
            and not reasoned_incident_eligible):
        final_synthesis_skipped_reason = "multi_source_factual_brief_ready"
    if (witnesses and not answer_text and final_synthesis_skipped_reason is None
            and deadline - time.monotonic() > 2):
        # The read loop may end at a budget, repeated proposal or source gap.
        # Request ONE final answer with tools=[], not another planning pass.
        # Feed only bounded, redacted witness projections. The host report
        # below still separates model interpretation from actual source data.
        synthesis_start = time.monotonic()
        # Condense all source reads BEFORE the model request; dumping full
        # event lists into 15 KB pushed the material lastSeen/offline data out.
        final_witnesses = (focused_highlights(witnesses, sorted(focus_ids))
                           if focus_ids else source_highlights(witnesses))
        try:
            response = await asyncio.wait_for(
                chat([
                    {"role": "system", "content":
                     candidate_prompt() if reasoned_incident_eligible else
                     "Answer the user's question using only verified source "
                     "observations provided. Reference read IDs. Distinguish "
                     "WARN and ERROR from INFO, source reporting from physical "
                     "state, confirmed cause from hypothesis. Do not rank "
                     "physical failure causes without discriminating source "
                     "evidence. Device telemetry clocks may differ. Do not assert "
                     "an error-free hub without suitable WARN/ERROR coverage. "
                     "Disclose missing data, failures and time limits. No "
                     "tool calls. Respond ONLY with structured JSON claims "
                     "selecting provided source claim IDs, never free prose. "
                     "Any claims without independent read receipts must be "
                     "omitted. The host renders the resulting statements."},
                    {"role": "user", "content": json.dumps({
                        "question": question,
                        "source_evidence": final_witnesses,
                        "incident_evidence": incident_relevance
                        if reasoned_incident_eligible else None,
                        "failed_or_rejected_reads": failures[-12:],
                        "source_complete": False,
                        "source_claim_catalog": (
                            [] if reasoned_incident_eligible else [
                            {"id": c["id"], "statement": c["statement"],
                             "evidence_reads": c["evidence_reads"]}
                            for c in claim_catalog(witnesses, sorted(focus_ids), limit=32)
                        ]),
                    }, ensure_ascii=True, default=str)[:15000]},
                ], []),
                timeout=min(14.0, max(1.0, deadline - time.monotonic())),
            )
            if isinstance(response, dict) and not response.get("tool_calls"):
                candidate = response.get("content")
                if isinstance(candidate, str) and candidate.strip():
                    if reasoned_incident_eligible:
                        model_reasoned_proposal = candidate
                    else:
                        model_claim_proposal = candidate
                    answer_text = _answer_text(candidate, 4500)
                    synthesis_status = "completed"
                else:
                    synthesis_status = "empty_response"
            else:
                synthesis_status = "invalid_response"
        except asyncio.CancelledError:
            raise
        except Exception:
            synthesis_status = "unavailable"
        finally:
            synthesis_elapsed_ms = round((time.monotonic() - synthesis_start) * 1000)
    if not witnesses:
        answer_text = ("No verified MCP evidence was recovered. "
                       "The question cannot be answered from live sources.")
    elif not answer_text:
        answer_text = (focused_fallback(witnesses, failures, sorted(focus_ids))
                       if focus_ids else None) or evidence_fallback(witnesses, failures)
        synthesis_status = "host_evidence_fallback"
    # Independent post-answer claim audit: a model may offer a fluent
    # speculative ranking even while admitting causality is unverified.
    # Do not publish such a ranking as the incident conclusion when the
    # source-backed temporal packet says no cause is attributed.
    causal_packet = incident_attribution_packet(
        witnesses, sorted(focus_ids))
    rejected_causal_ranking = unsupported_causal_ranking(
        answer_text, causal_packet)
    # Do not depend on a fixed list of model phrasings ("offender",
    # "contributor", "lead", "driven chiefly", etc.). For an unattributed
    # generic incident the model is the *investigator*, not the authority
    # to publish a cause. The separately derived claim ledger controls
    # which observations may enter the final causal assessment. The
    # free-form text is not atomically verified and is not released.
    source_bound_incident = source_bound_incident_required(causal_packet)
    claim_ledger = (incident_claim_ledger(causal_packet)
                    if source_bound_incident and causal_packet else [])
    factual_ledger = factual_evidence_ledger(witnesses, sorted(focus_ids))
    if source_bound_incident and causal_packet is not None:
        answer_text = evidence_safe_incident_explanation(causal_packet)
        synthesis_status = "source_bound_unattributed_incident"
    # Publication authority is independent of the model's wording.
    # Source-classified unattributed warnings retain the existing special
    # source-bound report; every other investigation receives a general
    # claim-gated, host-authored response, including legacy model prose.
    validated_catalog = claim_catalog(witnesses, sorted(focus_ids))
    if source_bound_incident:
        # No model selection is necessary or used for the source-authoritative
        # incident assessment. A skipped model synthesis is NOT a failed
        # structured-claim response and must not be reported as one.
        publication = {
            "validation": {
                "status": "host_authoritative_incident",
                "accepted": [], "rejected": [],
            },
            "fallback": False, "published_claims": [],
            "limits": (
                "Host-authored generic incident report uses independently "
                "verified source receipts; no model claims are published."
            ),
        }
    else:
        publication = publish_verified_claims(
            model_claim_proposal, validated_catalog)
    # Model synthesis and publication validation are distinct diagnostic
    # stages. Preserve the former for replay/latency comparisons while only
    # the independently checked publication reaches the final report.
    if not source_bound_incident and witnesses:
        answer_text = publication["text"]
    # Make uncertainty prominent even when the model produces a fluent answer.
    # A recent all-INFO log sample is not a severity-filtered error audit.
    log_audits = [
        w["source_data"]["log_summary"]
        for w in witnesses
        if isinstance(w.get("source_data"), dict)
        and isinstance(w["source_data"].get("log_summary"), dict)
    ]
    info_only_logs = bool(log_audits) and all(
        a.get("warning_error_group_count") == 0
        and a.get("level_counts_in_returned_rows", {}).get("INFO", 0) > 0
        for a in log_audits
    )
    projections_empty = [
        w["operation"] for w in witnesses
        if isinstance(w.get("source_data"), dict)
        and w["source_data"].get("projection_empty") is True
    ]
    # Keep the user-facing answer short, while retaining every verified
    # detail, failed read and confidence limit in the technical report.
    # A named/independently verified target's detailed incident analysis
    # is already source-scoped and may contain causally important issuer
    # receipts. The general cross-source triage must NEVER replace it.
    connected_brief = (
        source_connected_brief(witnesses)
        if not source_bound_incident and not focus_ids else "")
    # One bounded optional model-authored explanation pass. Only a narrowly
    # source-verifiable subset of language can replace the existing host
    # summary. The model never receives a tool, grant or write permission.
    verified_narrative = {"accepted": False, "reason": "not_attempted"}
    narrative_synthesis_ms = 0
    cases = (verified_source_cases(witnesses)[:3]
             if connected_brief and not focus_ids and not source_bound_incident
             else [])
    if enable_verified_narrative and cases and candidate_narrative is not None:
        # A model-authored proposal was already paid for during the original
        # investigation; never need a separate inference call if it passes.
        verified_narrative = verify_model_explanation(
            candidate_narrative, cases)
        if verified_narrative.get("accepted") is True:
            verified_narrative["reason"] = "verified_from_read_loop"
    # Do not impose a hard 6s extra delay on an already slow model. The
    # real provider's measured planning latency, not question vocabulary,
    # determines whether an optional final draft has a reasonable chance
    # to finish in the old 6s budget.
    planning_average_ms = (planning_model_ms / planning_model_calls
                           if planning_model_calls else 0)
    # Once a proposed explanation has been independently checked, do not
    # ask the same model to rewrite rejected prose. Preserve the trusted
    # source-backed answer instead of adding another inference request.
    can_afford_extra = (
        candidate_narrative is None
        and narrative_followup_eligible(
            planning_model_ms, planning_model_calls,
            deadline - time.monotonic()))
    if (enable_verified_narrative and cases
            and verified_narrative.get("accepted") is not True
            and can_afford_extra):
        cases = verified_source_cases(witnesses)[:3]
        start_narrative = time.monotonic()
        try:
            request = {
                "question": question,
                "cases": [{
                    "source_id": c["source_id"], "name": c["name"],
                    "warning_rows": c["warning_rows_in_returned_sample"],
                    "warning_levels": c["warning_levels"],
                    "status": c["status"],
                    "reads": c["evidence_reads"],
                } for c in cases],
            }
            response = await asyncio.wait_for(
                chat([
                    {"role": "system", "content":
                     "Write a brief natural-language Hubitat explanation "
                     "using only the exact independently returned facts. "
                     "Return ONLY JSON: {\"findings\":[{\"source_id\":"
                     "\"<exact provided ID>\",\"explanation\":\"...\","
                     "\"next_check\":\"...\"}]}. "
                     "For each item, mention its exact source name, "
                     "an exact number of WARN/ERROR log rows and/or a "
                     "literal returned status such as healthStatus=offline. "
                     "For example: 'Mesh outlet has 29 WARN rows and "
                     "healthStatus=offline in the reported readings; this "
                     "is worth checking.' Use ONLY simple neutral words. "
                     "For each next_check begin with Check/Verify/Inspect/"
                     "Confirm/Review/Compare/Test/Investigate/Examine. "
                     "No commands, changes or factual assumptions. "
                     "Never assert physical connectivity, faults, driver "
                     "execution, causality, unsupported timestamps, "
                     "fixes or any source values not supplied. "
                     "No code, source instructions or extra fields."},
                    {"role": "user", "content":
                     json.dumps(request, ensure_ascii=True)[:5500]},
                ], []),
                timeout=min(6.0, max(1.0,
                                     deadline - time.monotonic() - 1)),
            )
            candidate = (response.get("content")
                         if isinstance(response, dict)
                         and not response.get("tool_calls") else None)
            verified_narrative = verify_model_explanation(candidate, cases)
        except asyncio.CancelledError:
            raise
        except Exception:
            verified_narrative = {
                "accepted": False, "reason": "model_unavailable"}
        finally:
            narrative_synthesis_ms = round(
                (time.monotonic() - start_narrative) * 1000)
    if (enable_verified_narrative and cases
            and verified_narrative.get("accepted") is not True
            and not can_afford_extra and candidate_narrative is None):
        verified_narrative["reason"] = (
            "extra_call_skipped_slow_model"
            if planning_model_calls and planning_average_ms > 3000
            else "extra_call_skipped_time_budget")
    relevance_blocker = subject_relevance_limit(
        named_identity_lookups, witnesses,
        focus_ids=sorted(focus_ids), failures=failures)
    # Complete candidate groups already have independently attested,
    # source-ID-matched state for every requested entity. Compose one
    # concise entity-aware comparison rather than a first-N attributes
    # fallback that can omit later devices entirely. Never replace a
    # targeted incident, a warning-based causal report or a blocked subject.
    grouped_answer = (
        natural_entity_answer(named_identity_lookups, witnesses, room_inventories)
        if not source_bound_incident and not focus_ids
        and relevance_blocker is None else None)
    temporal_lead = (
        verified_temporal_lead(witnesses, sorted(focus_ids))
        if not source_bound_incident and relevance_blocker is None else None)
    model_reasoned_result = (
        verify_natural_hypothesis(
            model_reasoned_proposal, coverage=incident_relevance,
            observed_source_names=[question])
        if (reasoned_incident_eligible and not source_bound_incident
            and relevance_blocker is None and incident_gap is None)
        else {"accepted": False, "reason": "not_eligible",
              "model_prose_published": False})
    # Fallback to an actual verified control->state chronology when the
    # reasoning model produces plain text, invalid JSON or times out. Do
    # not replace a valid model explanation and do not claim that a
    # correlated thermostat event proves which TRV made the decision.
    focused_name = next((str(w["source_data"].get("label") or
                             w["source_data"].get("name") or "")
                         for w in witnesses
                         if w.get("operation") == "hub_get_device"
                         and str(w.get("source_data", {}).get("id")) in focus_ids
                         and isinstance(w.get("source_data"), dict)), "")
    if not focused_name:
        focused_name = next((str(row["query"])
                             for row in named_identity_lookups
                             if row.get("status") == "unique"
                             and row.get("query")), "the device")
    verified_operating_sequence = (
        operational_sequence_brief(incident_relevance, focused_name)
        if not source_bound_incident and relevance_blocker is None
        else None)
    host_sequence_published = (
        verified_operating_sequence is not None
        and model_reasoned_result.get("accepted") is not True
        and verified_narrative.get("accepted") is not True)
    concise_answer = (
        model_reasoned_result["text"]
        if model_reasoned_result.get("accepted") is True
        else verified_operating_sequence["text"] if host_sequence_published
        else
        verified_narrative["text"]
        if verified_narrative.get("accepted") is True
        else grouped_answer["text"] if grouped_answer is not None
        else temporal_lead_short_answer(temporal_lead) if temporal_lead is not None
        else connected_brief)
    # A dated why-question cannot be answered by a catalog of unrelated
    # later command counts. Explain the specific missing incident evidence
    # in ordinary language and retain the full technical receipts below.
    if incident_gap is not None and relevance_blocker is None:
        concise_answer = incident_gap[0]
    if (not concise_answer and not source_bound_incident
            and readiness["host_factual_brief_ready"]):
        concise_answer = evidence_brief(validated_catalog)
    if relevance_blocker is not None:
        # A correct observation about a different device is NOT an answer
        # about the named subject. Keep all evidence in the technical
        # report; never publish a general hub-status fallback as the answer.
        concise_answer = relevance_blocker["text"]
    lines = []
    if relevance_blocker is not None:
        lines.extend([
            "**Requested subject was not verified**",
            relevance_blocker["text"], "",
            "The following returned hub evidence is retained for audit "
            "but does not answer this requested subject.", "",
        ])
    if info_only_logs:
        lines.extend([
            "**Evidence limitation: hub log severity not verified**",
            "Only INFO records appeared in the sampled log reads. This is "
            "not proof that there are no WARN/ERROR entries elsewhere. "
            "A dedicated severity-filtered log read is still required.", "",
        ])
    if causal_coverage_gap is not None:
        warning_window = causal_coverage_gap.get("warning_window", {})
        if causal_coverage_gap.get("kind") == "target_generic_warning_origin_unverified":
            app_ids = causal_coverage_gap.get("observed_calling_app_ids", [])
            lines.extend([
                "**Verified device callers; generic warning origin unresolved**",
                "App IDs " + ", ".join(map(str, app_ids)) +
                " issued commands to the device, but the returned commands "
                "do not coincide with the generic warning at " +
                str(warning_window.get("oldest", "unknown")) + " to " +
                str(warning_window.get("newest", "unknown")) +
                ". No source-backed causal link to an issuing app or "
                "particular driver callback is established.",
                "",
            ])
        elif causal_coverage_gap.get("kind") == "target_driver_execution_mechanism_unverified":
            app_ids = causal_coverage_gap.get("observed_calling_app_ids", [])
            lines.extend([
                "**Verified callers; internal driver mechanism unresolved**",
                "App IDs " + ", ".join(map(str, app_ids)) +
                " issued device commands during the reported slow-method warning period. "
                "The WARN method " + str(causal_coverage_gap.get("method", "unknown")) +
                " has no matching command event in the bounded sample; it "
                "must not be assumed to be an API command. Source timing "
                "correlation does not establish which driver callback stalled."
                + ((" Separate generic load warnings from "
                    + str(causal_coverage_gap["unattributed_generic_warning_window"].get("oldest"))
                    + " to "
                    + str(causal_coverage_gap["unattributed_generic_warning_window"].get("newest"))
                    + " remain unattributed by this event sample.")
                   if causal_coverage_gap.get("unattributed_generic_warning_window")
                   else ""),
                "",
            ])
        else:
            checked = causal_coverage_gap.get("event_windows_checked", [])
            sample = checked[0] if checked else {}
            lines.extend([
                "**Evidence gap: event history does not establish the warning-window caller**",
                "Warning period: " + str(warning_window.get("oldest", "unknown")) +
                " to " + str(warning_window.get("newest", "unknown")) +
                ". Event sample: " + str(sample.get("oldest", "not read")) +
                " to " + str(sample.get("newest", "not read")) +
                ". Relevant issuing apps are unverified; source clocks may use "
                "different zones, and a source window is not guaranteed complete.",
                "",
            ])
    driver_blocker_lines = []
    if (source_readiness is not None and source_readiness.get("status")
            == "driver_configuration_read_failed"):
        driver_blocker_lines = [
            "**Driver configuration source blocked**",
            "A read-only configuration read for the independently verified "
            "device failed at the upstream gateway ("
            + _text(source_readiness.get("failure_code"), 65)
            + "). No device driver ID or complete driver implementation "
            "was returned; this is a failed inspection, not proof that the "
            "driver has no code.", "",
        ]
    if (source_readiness is not None and source_readiness.get("status")
            == "driver_source_unavailable_no_attested_id"):
        driver_blocker_lines = [
            "**Verified driver-source blocker**",
            "The target's configuration (Read #"
            + str(source_readiness.get("evidence_read"))
            + ") reports driver source unavailable and supplies no "
            "independently attested driver code ID. The internal "
            "implementation was not inspected; no method or CPU cause "
            "can be derived from source code in this investigation.", "",
        ]
    if projections_empty:
        lines.extend([
            "**Uninterpreted source fields**",
            "Gateway reads returned data not yet understood by the "
            "evidence adapter: " + ", ".join(projections_empty[:5]) + ".", "",
        ])
    # Lead broad, multi-source answers with a short source-grounded brief.
    # The full validated claim list remains available below. Do not replace
    # a targeted causal incident assessment with a general template.
    if (not source_bound_incident
            and readiness["distinct_verified_fact_kinds"] >= 2):
        lead = connected_brief or evidence_brief(validated_catalog)
        if lead:
            lines.extend([lead, ""])
    lines.extend([
        ("**Incident assessment — source-bound evidence**"
         if source_bound_incident
         else "**Independent claim validation — source-bound evidence**"),
        answer_text, "",
    ])
    # Keep the complete chronology in the technical report, while the
    # primary answer stays short and plainly distinguishes likely causes.
    if temporal_lead is not None:
        lines.extend(["**Detailed verified event chronology**",
                      temporal_lead_brief(temporal_lead), ""])
    # The supported answer comes first; a source-code blocker is a limit
    # on deeper attribution, not the primary answer to the question.
    lines.extend(driver_blocker_lines)
    lines.append("**Verified read coverage**")
    for witness in witnesses[:12]:
        op = _text(witness["operation"], 64)
        details = witness["source_data"]
        if isinstance(details, dict) and "log_summary" in details:
            report = details["log_summary"]
            groups=report.get("warning_error_groups",[])
            if focus_ids:
                groups=[g for g in groups if isinstance(g,dict)
                        and str(g.get("source_id")) in focus_ids]
            lines.append(
                f"- Read #{witness['read']}: {op}: "
                f"{report['returned_rows']} returned log rows; "
                f"{len(groups) if focus_ids else report['warning_error_group_count']} "
                + ("target " if focus_ids else "")+
                "WARN/ERROR groups; full historical coverage unverified."
            )
            lines.append("  - Sample levels"
                         + (" (all sources)" if focus_ids else "")
                         + ": " + str(
                report.get("level_counts_in_returned_rows", {})))
            lines.append("  - Returned time range: " + str(
                report.get("oldest_returned") or "unknown") + " to " + str(
                report.get("newest_returned") or "unknown")
                + " (timezone not verified).")
            if not groups:
                lines.append(
                    "  - No " + ("target " if focus_ids else "")+
                    "WARN/ERROR in returned sample; this does NOT "
                    "establish that historical target/hub logs are clear."
                )
            for group in groups[:5]:
                lines.append(
                    f"  - {group['level']} / {group['source_name']}: "
                    f"{group['message']} ({group['count']} rows)"
                )
        else:
            lines.append(f"- Read #{witness['read']}: {op} returned typed source data "
                         "(not proof of complete historical coverage).")
            if isinstance(details, dict):
                for key in ("alerts", "errors", "warnings"):
                    value = details.get(key)
                    if isinstance(value, list):
                        for item in value[:5]:
                            lines.append("  - Source " + key + ": " + _text(item, 180))
                for key in ("safeMode", "uptime", "freeMemory", "temperature", "dbSize"):
                    if key in details:
                        lines.append(f"  - Source {key}: " + _text(details[key], 80))
    if failures:
        lines.extend(["", "**Unavailable or rejected reads**"])
        for fail in failures[:8]:
            lines.append("- " + _text(fail.get("operation") or fail.get("tool")
                                       or "tool", 80) + ": "
                         + _text(fail.get("code"), 80))
    lines.extend(["", "**Evidence limits:** source results may be capped or stale; "
                  "reported state is not independent physical confirmation. "
                  "No Hubitat writes were performed."])
    text = "\n".join(lines)
    # The model's optional fact-selection protocol is NOT the authority for
    # a separately proof-joined room/device answer. Report the authority of
    # the ACTUAL displayed answer, while retaining model claim-validation
    # failures independently in the detailed diagnostic trace.
    host_group_published = (
        grouped_answer is not None
        and relevance_blocker is None
        and verified_narrative.get("accepted") is not True
    )
    model_reasoning_published = model_reasoned_result.get("accepted") is True
    host_incident_gap_published = (
        incident_gap is not None and relevance_blocker is None)
    host_temporal_lead_published = (
        temporal_lead is not None
        and not model_reasoning_published
        and not host_group_published
        and relevance_blocker is None
        and verified_narrative.get("accepted") is not True
    )
    validation_issues = (
        ["model_reasoning_cited_source_events",
         "semantic_causation_not_independently_verified"]
        if model_reasoning_published
        else ["requested_incident_evidence_missing"]
        if host_incident_gap_published
        else ["source_verified_room_and_device_readings"]
        if host_group_published and grouped_answer["room_membership_verified"]
        else ["source_verified_device_readings"]
        if host_group_published
        else ["source_verified_temporal_command_lead",
              "physical_causation_unverified"]
        if host_temporal_lead_published
        else [
            "structured_claims_validated" if publication["validation"]["accepted"]
            else "unstructured_or_unsupported_claims_withheld"
        ]
    )
    if (publication["validation"]["rejected"]
            and not host_group_published and not host_temporal_lead_published):
        validation_issues.append("model_claims_withheld")
    if not witnesses:
        validation_issues.append("no_verified_reads")
    elif host_temporal_lead_published:
        validation_issues.append("historical_coverage_unverified")
    elif host_group_published:
        if grouped_answer["room_unread_count"]:
            validation_issues.append("some_room_member_states_unread")
        if not grouped_answer["room_inventory_complete"]:
            validation_issues.append("room_membership_completeness_unverified")
    else:
        validation_issues.append("historical_coverage_unverified")
    if info_only_logs:
        validation_issues.append("warning_error_log_coverage_unverified")
    if projections_empty:
        validation_issues.append("gateway_projection_incomplete")
    if rejected_causal_ranking:
        validation_issues.append("unsupported_causal_ranking_withheld")
    if source_bound_incident:
        validation_issues.append(
            "unattributed_incident_model_narrative_withheld"
            if model_claim_proposal is not None
            else "source_authoritative_unattributed_incident")
    if causal_coverage_gap is not None:
        gap_kind = causal_coverage_gap.get("kind")
        validation_issues.append(
            "generic_warning_cause_unverified" if gap_kind == "target_generic_warning_origin_unverified"
            else "driver_execution_cause_unverified"
            if gap_kind == "target_driver_execution_mechanism_unverified"
            else "warning_window_actor_provenance_unverified"
        )
    return {
        "answer_mode": "native_mcp_investigation",
        "answer": {"text": concise_answer or text,
                   "displayed_record_ids": [],
                   "omitted_material_record_ids": [],
                   "validation_issues": validation_issues,
                   "root_cause_verified": False,
                   "human_review_required": bool(
                       failures or not witnesses or info_only_logs
                       or projections_empty or rejected_causal_ranking
                       or source_bound_incident)},
        "report": {"text": text, "technical_answer_retained": True},
        "native_diagnostics": {
            "rounds": rounds, "reads_executed": attempted,
            "successful_reads": len(witnesses),
            "model_tool_calls_allowed": bool(offered),
            "verified_source_ids": len(verified_ids),
            "verified_typed_ids": {kind: sorted(ids) for kind, ids in verified_typed.items()},
            "lazy_identity_lookup_attempted": identity_lookup_attempted,
            "named_identity_lookups": named_identity_lookups,
            "verified_room_name_catalogs": [
                {"returned_room_count": row["returned_room_count"],
                 "reported_room_count": row["reported_room_count"],
                 "name_catalog_complete": row["name_catalog_complete"],
                 "question_matched_rooms": question_room_matches(question, row)}
                for row in room_name_catalogs],
            "verified_room_inventories": [
                {k: entry[k] for k in ("name", "member_ids", "read",
                                       "reported_count", "inventory_complete")}
                for entry in room_inventories],
            "subject_relevance": (
                {k: v for k, v in relevance_blocker.items() if k != "text"}
                if relevance_blocker else {"status": "not_blocked"}),
            "verified_focus_receipts": verified_focus_receipts,
            "lazy_identity_lookup_ms": identity_lookup_ms,
            "coverage_challenge_used": coverage_challenge_used,
            "upstream_decision_challenge_used": upstream_decision_challenge_used,
            "causal_coverage_challenge_used": causal_coverage_challenge_used,
            "causal_coverage_gap": causal_coverage_gap,
            "source_path_readiness": source_readiness,
            "incident_attribution_evidence": causal_packet,
            "incident_claim_ledger": claim_ledger,
            "factual_evidence_ledger": factual_ledger,
            "structured_claim_catalog": validated_catalog,
            "claim_publication": {
                "used_for_display_answer": not (
                    host_group_published or host_temporal_lead_published
                    or host_incident_gap_published or model_reasoning_published
                    or host_sequence_published),
                "authority": (
                    "host_incident_receipts" if source_bound_incident
                    else "validated_model_selection"),
                "status": publication["validation"]["status"],
                "accepted_count": len(publication["validation"]["accepted"]),
                "rejected_reasons": publication["validation"]["rejected"][:20],
                "fallback": publication["fallback"],
                "published_fact_ids": [
                    c["fact_ids"] for c in publication["published_claims"]],
                "model_prose_published": model_reasoning_published,
                "limits": publication["limits"],
            },
            "model_narrative_withheld_for_unattributed_incident": source_bound_incident,
            "unsupported_causal_ranking_withheld": rejected_causal_ranking,
            "repeated_discovery": repeated_discovery,
            "blocked_repeat_errors": blocked_repeat_errors,
            "failed_scoped_operations": [
                {"operation": op, "target": target, "failures": count}
                for (op, target), count in sorted(failed_scoped_reads.items())
            ],
            "final_synthesis_skipped_reason": final_synthesis_skipped_reason,
            "general_evidence_readiness": readiness,
            "model_reasoned_assessment": model_reasoned_result,
            "verified_operating_sequence": verified_operating_sequence,
            "requested_incident_evidence_coverage": incident_relevance,
            "source_grounded_brief_published": bool(
                not source_bound_incident
                and not host_incident_gap_published
                and not model_reasoning_published
                and not host_sequence_published
                and readiness["host_factual_brief_ready"]
                and validated_catalog),
            "concise_answer_source": (
                "model_cited_incident_assessment" if model_reasoning_published
                else "source_attested_operating_sequence" if host_sequence_published
                else "requested_incident_evidence_gap" if host_incident_gap_published
                else "unresolved_named_subject_evidence" if relevance_blocker
                else "model_authored_independently_checked" if
                verified_narrative.get("accepted") is True
                else "verified_entity_group_comparison" if grouped_answer
                else "source_verified_temporal_lead" if temporal_lead is not None
                else "cross_source_verified_case_graph" if connected_brief
                else "host_verified_claim_catalog" if concise_answer
                else "full_source_report"),
            "verified_temporal_lead": temporal_lead,
            "entity_group_summary": (
                {k: v for k, v in grouped_answer.items() if k != "text"}
                if grouped_answer else None),
            "cross_source_case_count": len(verified_source_cases(witnesses)),
            "cross_source_connected_count": sum(
                1 for c in verified_source_cases(witnesses)
                if c["source_correlated"]),
            "verified_narrative_accepted": (
                verified_narrative.get("accepted") is True),
            "verified_narrative_result": verified_narrative.get("reason"),
            "verified_narrative_ms": narrative_synthesis_ms,
            "planning_model_ms": planning_model_ms,
            "planning_model_calls": planning_model_calls,
            "planning_model_average_ms": round(planning_average_ms),
            "narrative_draft_in_read_loop": candidate_narrative is not None,
            "timed_out_operations": [f"{name}:{operation}"
                                     for name, operation in sorted(timed_out_operations)],
            "source_highlights": (focused_highlights(witnesses, sorted(focus_ids))
                                  if focus_ids else source_highlights(witnesses)),
            "focus_ids": sorted(focus_ids),
            "redundant_evidence_reads": redundant_evidence_reads,
            "redundant_snapshot_reads": redundant_snapshot_reads,
            "redundant_log_subsets": redundant_log_subsets,
            "redundant_event_subsets": redundant_event_subsets,
            "rejected_scope_history_reads": rejected_scope_history_reads,
            "normalized_history_reads": normalized_history_reads[:8],
            "invalid_contract_attempts": dict(sorted(
                invalid_contract_attempts.items())),
            "final_synthesis": synthesis_status,
            "final_synthesis_ms": synthesis_elapsed_ms,
            "discovered_operations": {k: sorted(v) for k, v in discovered.items()},
            "stop_reason": reason,
            "failures": failures[:20],
            "read_summaries": witnesses[:12],
            "total_elapsed_ms": round((time.monotonic()-started)*1000),
        },
        "resolved_devices": sorted(focus_ids),
        "resolution_method": "model_native_mcp_reads",
        "test_mode": "explicit_read_only",
    }


__all__ = ["run_native_read_agent", "_guard", "_read_manifest",
           "_observed_operations", "_group_logs"]

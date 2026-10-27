"""Investigation V2: bounded validation of MODEL-PROPOSED discriminating reads.

This is a host-side permission/planning boundary, not an LLM, MCP executor or
keyword router. The model proposes a specific missing question and tool call;
only this module admits reads that are already present in a live MCP manifest.
No call is ever performed here. V1 writes/confirmation remain untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect

from .evidence import CaseFile
from .receipt_projection import PROJECTED_V2_READ_OPERATIONS
from .temporal_scope import IncidentWindow
from datetime import datetime, timezone


@dataclass(frozen=True)
class ApprovedRead:
    tool: str
    arguments: dict[str, Any]
    discriminator: str
    hypothesis_ids: tuple[str, ...]
    information_gain: str


@dataclass(frozen=True)
class RejectedRead:
    index: int
    reason: str


@dataclass
class ReadPlan:
    approved: list[ApprovedRead]
    rejected: list[RejectedRead]
    budget_remaining: int


def _json_key(tool: str, args: Mapping[str, Any]) -> str:
    return json.dumps([tool, args], sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _type_ok(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_type_ok(value, member) for member in expected)
    if not isinstance(expected, str):
        return False
    return {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "boolean": lambda: type(value) is bool,
        "integer": lambda: type(value) is int,
        "number": lambda: type(value) in (int, float),
        "null": lambda: value is None,
    }.get(expected, lambda: False)()


def _schema_problem(value: Any, schema: Any, path: str = "arguments", depth: int = 0) -> str | None:
    """Validate the supported inputSchema subset; refuse unknown branches.

    This is preflight validation only. The actual MCP executor must still apply
    its own full schema, source identity and permission checks.
    """
    if not isinstance(schema, dict) or depth > 10:
        return f"{path}: invalid schema"
    if "type" in schema and not _type_ok(value, schema["type"]):
        return f"{path}: type mismatch"
    if "enum" in schema and (not isinstance(schema["enum"], list) or value not in schema["enum"]):
        return f"{path}: value not in advertised enum"
    if "const" in schema and value != schema["const"]:
        return f"{path}: constant mismatch"
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            return f"{path}: invalid property schema"
        required = schema.get("required", [])
        if not isinstance(required, list):
            return f"{path}: invalid required properties"
        for key in required:
            if not isinstance(key, str) or key not in value:
                return f"{path}: required field missing"
        for key, member in value.items():
            if not isinstance(key, str):
                return f"{path}: nonstring property"
            if key in props:
                if (error := _schema_problem(member, props[key], path + "." + key, depth + 1)):
                    return error
            elif schema.get("additionalProperties") is False:
                return f"{path}: undisclosed property"
            elif isinstance(schema.get("additionalProperties"), dict):
                if (error := _schema_problem(member, schema["additionalProperties"],
                                             path + "." + key, depth + 1)):
                    return error
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        if len(value) > 100:
            return f"{path}: excessive array"
        for index, member in enumerate(value):
            if (error := _schema_problem(member, schema["items"], f"{path}[{index}]", depth + 1)):
                return error
    for choice in ("oneOf", "anyOf"):
        if choice in schema:
            branches = schema[choice]
            if not isinstance(branches, list) or not branches:
                return f"{path}: invalid {choice}"
            matches = sum(_schema_problem(value, branch, path, depth + 1) is None for branch in branches)
            valid = matches > 0 if choice == "anyOf" else matches == 1
            if not valid:
                return f"{path}: {choice} mismatch"
    return None


def _read_tool_advertised(tool: MCPTool, args: Mapping[str, Any],
                          learned_operations: Mapping[str, set[str]]) -> str | None:
    name = tool.name
    if (name.startswith("hub_manage_") or name.startswith("hub_set_")
            or name.startswith("hub_update_")):
        return "management/write gateways are excluded from V2 investigation"
    if not (name.startswith("hub_read_") or name.startswith("homebrain_")
            or name in {"hub_get_info", "hub_get_tool_guide", "hub_search_tools"}):
        return "tool is not an allowed read entry point"
    annotations = tool.annotations if isinstance(tool.annotations, dict) else {}
    if (annotations.get("mutates") is True or annotations.get("destructiveHint") is True
            or annotations.get("readOnlyHint") is False):
        return "tool advertises mutation or lacks read permission"
    if classify_tool_effect(tool, dict(args)) is not ToolEffect.READ:
        return "tool effect is not read-only"
    if name.startswith("hub_read_"):
        operation = args.get("tool")
        if not isinstance(operation, str) or not operation:
            return "gateway sub-operation is required"
        # Do not allow a malicious read gateway payload to invoke a mutator.
        if not operation.startswith(("hub_get_", "hub_list_", "hub_read_",
                                     "hub_search_", "hub_check_", "hub_find_")):
            return "sub-operation is not read-only"
        props = tool.input_schema.get("properties", {}) if isinstance(tool.input_schema, dict) else {}
        operation_prop = props.get("tool", {}) if isinstance(props, dict) else {}
        choices = operation_prop.get("enum") if isinstance(operation_prop, dict) else None
        allowed = (set(choices) if isinstance(choices, list) else set()) | learned_operations.get(name, set())
        if operation not in allowed:
            return "sub-operation absent from verified live manifest/discovery"
        if operation not in PROJECTED_V2_READ_OPERATIONS:
            return "operation has no reviewed V2 typed evidence projection"
    return None


def _same_native_page(cov: Any, tool: str, args: Mapping[str, Any]) -> bool:
    """Bound pointless hoursBack growth for capped non-paginated history.

    Only treat expanding the time horizon as redundant when a previous successful
    query was explicitly truncated at the SAME limit and attribute, with no
    next cursor. Increasing the page limit or changing the attribute is allowed.
    """
    inner = args.get("args")
    if not isinstance(inner, dict):
        return False
    if (cov.tool != tool or cov.operation != args.get("tool")
            or not cov.succeeded or cov.truncated is not True
            or cov.pagination_cursor is not None or cov.returned_rows == 0
            or cov.query_target_id != str(inner.get("deviceId", ""))):
        return False
    previous = cov.requested_filters
    current = inner
    if previous.get("attribute") != current.get("attribute") or previous.get("limit") != current.get("limit"):
        return False
    old_h = previous.get("hoursBack")
    new_h = current.get("hoursBack")
    return (type(old_h) in (int, float) and type(new_h) in (int, float)
            and new_h > old_h)


def review_model_read_proposals(
    case: CaseFile,
    proposals: Iterable[Mapping[str, Any]],
    available_tools: Iterable[MCPTool],
    *,
    verified_entity_ids: Iterable[str] = (),
    learned_operations: Mapping[str, set[str]] | None = None,
    previous_calls: Iterable[tuple[str, Mapping[str, Any]]] = (),
    max_total_reads: int = 8,
    max_reads_this_round: int = 3,
    budget_used_reads: int | None = None,
    incident_window: IncidentWindow | None = None,
) -> ReadPlan:
    """Approve only information-seeking, manifest-matched, scoped safe reads.

    The caller supplies independently verified target IDs and operations learned
    from actual MCP discovery, NEVER a model assertion. This function does not
    resolve identities, infer hypothesis truth, execute reads or grant writes.
    """
    manifest = {t.name: t for t in available_tools if isinstance(t, MCPTool)}
    known_ids = {str(value) for value in verified_entity_ids
                 if isinstance(value, (str, int)) and str(value).isdecimal()}
    # Previous query arguments are NOT identity verification. A successful
    # read of an arbitrary model-supplied ID must not whitelist that ID.
    known_ids.update(e.producer_id for e in case.records if e.producer_id)
    known_ids.update(e.target_id for e in case.records
                     if e.target_id and e.stage == "config_stored")
    prior = set()
    for name, args in previous_calls:
        if isinstance(name, str) and isinstance(args, dict):
            try:
                prior.add(_json_key(name, args))
            except (TypeError, ValueError):
                continue
    # Executed attempts already appear in case.coverage. Do not charge
    # each read twice merely because its signature is also in prior_calls.
    # A V2 test may start with prior host evidence (a large case). Those
    # trusted observations must not exhaust THIS run's MCP read allowance.
    # The explicit caller count is authoritative only for new V2 executions.
    consumed = (max(0, int(budget_used_reads)) if budget_used_reads is not None
                else max(len(case.coverage), len(prior)))
    remaining = max(0, min(30, int(max_total_reads)) - consumed)
    batch = min(remaining, max(0, min(6, int(max_reads_this_round))))
    approved: list[ApprovedRead] = []
    rejected: list[RejectedRead] = []
    seen = set(prior)
    seen_discriminators: set[str] = set()
    learned = learned_operations or {}
    for index, proposal in enumerate(proposals):
        if len(approved) >= batch:
            rejected.append(RejectedRead(index, "read budget exhausted"))
            continue
        if not isinstance(proposal, dict):
            rejected.append(RejectedRead(index, "proposal must be an object"))
            continue
        name = proposal.get("tool")
        args = proposal.get("arguments")
        discriminator = proposal.get("discriminator")
        gain = proposal.get("information_gain")
        ids = proposal.get("hypothesis_ids", [])
        if (not isinstance(name, str) or not isinstance(args, dict)
                or not isinstance(discriminator, str) or not discriminator.strip()
                or not isinstance(gain, str) or not gain.strip()
                or not isinstance(ids, list)
                or len(ids) > 8 or any(not isinstance(x, str) or len(x) > 100 for x in ids)):
            rejected.append(RejectedRead(index, "missing structured discriminator, tool, arguments or gain"))
            continue
        if len(discriminator) > 350 or len(gain) > 500:
            rejected.append(RejectedRead(index, "proposal rationale exceeds limit"))
            continue
        tool = manifest.get(name)
        if tool is None:
            rejected.append(RejectedRead(index, "tool not in live MCP manifest"))
            continue
        if (error := _read_tool_advertised(tool, args, learned)) is not None:
            rejected.append(RejectedRead(index, error))
            continue
        if (error := _schema_problem(args, tool.input_schema)) is not None:
            rejected.append(RejectedRead(index, error))
            continue
        inner = args.get("args") if isinstance(args.get("args"), dict) else args
        scopes = [(k, inner[k]) for k in ("deviceId", "appId") if k in inner]
        if any((isinstance(v, bool) or not isinstance(v, (int, str))
                or str(v) not in known_ids) for _, v in scopes):
            rejected.append(RejectedRead(index, "target ID has no independent verified scope"))
            continue
        # The user's explicit historical date is a host-owned objective.
        # A current-event page cannot answer an earlier incident. Require
        # a bounded target-specific read that actually reaches the start.
        if incident_window is not None and args.get("tool") == "hub_list_device_events":
            if not inner.get("deviceId"):
                rejected.append(RejectedRead(index, "historical read requires verified deviceId"))
                continue
            since = inner.get("since")
            hours = inner.get("hoursBack")
            covers = False
            if isinstance(since, str):
                try:
                    began = datetime.fromisoformat(since.replace("Z","+00:00"))
                    start = datetime.fromisoformat(incident_window.start_utc)
                    covers = began.tzinfo is not None and began <= start
                except ValueError:
                    covers = False
            elif type(hours) in (int,float):
                covers = hours >= incident_window.minimum_hours_back(now=datetime.now(timezone.utc))
            if not covers:
                rejected.append(RejectedRead(index, "read does not cover requested incident start"))
                continue
            until = inner.get("until")
            if isinstance(until,str):
                try:
                    ended = datetime.fromisoformat(until.replace("Z","+00:00"))
                    if ended.tzinfo is None or ended < datetime.fromisoformat(incident_window.end_utc):
                        rejected.append(RejectedRead(index, "read ends before requested incident window"))
                        continue
                except ValueError:
                    rejected.append(RejectedRead(index, "invalid historical read end time"))
                    continue
        # No hidden control arguments, even if an upstream permissive schema
        # happens to allow additional properties.
        if any(key in inner for key in ("confirm", "command", "commands", "action", "mutate", "delete", "newValue")):
            rejected.append(RejectedRead(index, "control/write argument in read proposal"))
            continue
        try:
            key = _json_key(name, args)
        except (TypeError, ValueError):
            rejected.append(RejectedRead(index, "arguments are not JSON serializable"))
            continue
        if key in seen or discriminator.strip().casefold() in seen_discriminators:
            rejected.append(RejectedRead(index, "duplicate read or discriminator"))
            continue
        if any(_same_native_page(c, name, args) for c in case.coverage):
            rejected.append(RejectedRead(index, "same capped history page; increase limit or change discriminator"))
            continue
        seen.add(key)
        seen_discriminators.add(discriminator.strip().casefold())
        approved.append(ApprovedRead(
            name, dict(args), discriminator.strip(), tuple(ids), gain.strip()))
    return ReadPlan(approved, rejected, batch - len(approved))


__all__ = ["ApprovedRead", "RejectedRead", "ReadPlan", "review_model_read_proposals"]

"""Optional provenance-driven V2 pre-planning identity read.

A source is examined only when an independent Hubitat event explicitly named
its producer ID. No question keyword classification or hard-coded device/rule
IDs: gate the read using the actual live MCP suboperation/schema and the same
host review/executor path. An unavailable catalogue is not a failed model plan.
"""
from __future__ import annotations
from typing import Iterable
from .causal_evidence import focused_switch_command
from .transition_links import incident_links
from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect
from .evidence import CaseFile


def source_identity_proposals(tools: Iterable[MCPTool], case: CaseFile) -> list[dict]:
    unexplained = {
        row.producer_id for row in case.records
        if row.stage == "command_issued" and row.producer_id
        and row.producer_id not in case.app_identities
    }
    if not unexplained:
        return []
    gateway = next((t for t in tools if isinstance(t, MCPTool)
                    and t.name == "hub_read_apps_code"
                    and classify_tool_effect(t, {}) is ToolEffect.READ
                    and isinstance(t.annotations, dict)
                    and t.annotations.get("readOnlyHint") is not False
                    and t.annotations.get("mutates") is not True
                    and t.annotations.get("destructiveHint") is not True), None)
    if gateway is None:
        return []
    schema = gateway.input_schema if isinstance(gateway.input_schema, dict) else {}
    props = schema.get("properties", {})
    op_field = props.get("tool", {}) if isinstance(props, dict) else {}
    ops = op_field.get("enum", []) if isinstance(op_field, dict) else []
    if not isinstance(ops, list) or "hub_list_apps" not in ops:
        return []
    nested = props.get("args", {}) if isinstance(props, dict) else {}
    required = nested.get("required", []) if isinstance(nested, dict) else []
    if required:
        # Never invent values to satisfy unknown required fields.
        return []
    return [{
        "tool": "hub_read_apps_code",
        "arguments": {"tool": "hub_list_apps", "args": {}},
        "discriminator": "Match historical command issuer IDs to current installed-app names",
        "information_gain": "Name verified producers before an AI chooses follow-up reads",
        "hypothesis_ids": [],
    }]


def source_configuration_proposals(
    tools: Iterable[MCPTool], case: CaseFile, *,
    diagnostics: list[dict[str, str]] | None = None,
    verified_target_ids: Iterable[str] = (),
) -> list[dict]:
    """One read of an event-attested command issuer's stored app config.

    The historical event's producer ID is a read scope, not permission to
    execute code or assume its current settings were effective then.
    """
    # Knowing an issuer's NAME does not establish its configuration.
    # Inspect one event-attested command issuer even when the app catalogue
    # already provided its friendly name. The normal read review still gates
    # this request by live manifest, args schema, and read-only permission.
    candidates = {
        row.producer_id for row in case.records
        if row.stage == "command_issued" and row.producer_id
    }
    if not candidates:
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "no_event_attested_command_issuer"})
        return []
    gateway = next((t for t in tools if isinstance(t, MCPTool)
                    and t.name == "hub_read_apps_code"
                    and classify_tool_effect(t, {}) is ToolEffect.READ
                    and isinstance(t.annotations, dict)
                    and t.annotations.get("readOnlyHint") is not False
                    and t.annotations.get("mutates") is not True
                    and t.annotations.get("destructiveHint") is not True), None)
    if gateway is None:
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "safe_read_gateway_unavailable"})
        return []
    schema = gateway.input_schema if isinstance(gateway.input_schema, dict) else {}
    props = schema.get("properties", {})
    field = props.get("tool", {}) if isinstance(props, dict) else {}
    ops = field.get("enum", []) if isinstance(field, dict) else []
    if not isinstance(ops, list) or "hub_get_app_config" not in ops:
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "operation_not_in_live_enum"})
        return []
    nested = props.get("args", {}) if isinstance(props, dict) else {}
    if not isinstance(nested, dict) or nested.get("type") not in (None, "object"):
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "unsupported_args_schema"})
        return []
    required = nested.get("required", [])
    if (not isinstance(required, list)
            or any(field not in ("appId",) for field in required)):
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "unsupported_required_args"})
        return []
    properties = nested.get("properties", {})
    # Some genuine live MCP gateways expose a generic, open object for
    # operation-specific args. JSON Schema permits appId in that case even
    # when the name is missing from properties; the host still validates
    # the complete proposal and independently attests the issuer ID.
    declared = isinstance(properties, dict) and "appId" in properties
    open_args = (isinstance(properties, dict) and not declared
                 and nested.get("additionalProperties") is not False)
    if not (declared or open_args):
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "app_id_missing_from_live_schema"})
        return []
    scoped = {str(x) for x in verified_target_ids
              if type(x) in (str, int) and str(x).isdecimal()}
    if scoped:
        # New V2 host path: independently verified IDs focus the most recent
        # attested switch transition, never a historic network incident.
        focused, focus_basis = focused_switch_command(
            case, verified_target_ids=scoped)
        if diagnostics is not None:
            diagnostics.append({
                "stage": "controller_config", "incident_focus": focus_basis,
                "paired_command_id": focused.record_id if focused else None,
            })
        if focused is None or not focused.producer_id:
            return []
        ident = focused.producer_id
    else:
        # Backward-compatible unscoped standalone evidence helper:
        # retain its historical adverse-event exploration behaviour.
        # Production V2 always supplies verified_target_ids.
        related = incident_links(case)
        distances: dict[str, float] = {}
        for link in related:
            issuer = link.command.producer_id
            if issuer:
                distances[issuer] = min(
                    distances.get(issuer, float("inf")),
                    link.seconds_to_adverse)
        def rank(issuer: str) -> tuple[int, float, int, int]:
            count = sum(row.stage == "command_issued"
                        and row.producer_id == issuer for row in case.records)
            return (0 if issuer in distances else 1,
                    distances.get(issuer, float("inf")), -count, int(issuer))
        ident = min(candidates, key=rank)
    # For an open generic gateway, check any additionalProperties subschema
    # before proposing the field; the same final host reviewer then validates
    # the *entire* live tool manifest, argument shape and source identity.
    if open_args and isinstance(nested.get("additionalProperties"), dict):
        from .planning import _schema_problem
        if _schema_problem({"appId": ident}, nested) is not None:
            if diagnostics is not None:
                diagnostics.append({"stage": "controller_config", "reason": "open_args_value_rejected"})
            return []
    # The upstream app-config read defaults to excluding settings. Request
    # them only when the same live read schema accepts the optional boolean.
    # Otherwise preserve the original narrow read, never bypassing validation.
    from .planning import _schema_problem
    config_args: dict[str, str | bool] = {"appId": ident}
    if _schema_problem({**config_args, "includeSettings": True}, nested) is None:
        config_args["includeSettings"] = True
    if diagnostics is not None:
        diagnostics.append({
            "stage": "controller_config", "status": "verified_issuer_proposal",
            "issuer_id": ident,
            "argument_basis": "declared_app_id" if declared else "open_args_schema",
            "settings_requested": "true" if config_args.get("includeSettings") is True else "false",
        })
    return [{
        "tool": "hub_read_apps_code",
        "arguments": {"tool": "hub_get_app_config", "args": config_args},
        "discriminator": "Read stored settings for event-confirmed command issuer",
        "information_gain": "Find currently stored controller settings without inferring historical execution",
        "hypothesis_ids": [],
    }]


__all__ = ["source_identity_proposals", "source_configuration_proposals"]

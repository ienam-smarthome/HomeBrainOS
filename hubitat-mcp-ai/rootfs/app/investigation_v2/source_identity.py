"""Optional provenance-driven V2 pre-planning identity read.

A source is examined only when an independent Hubitat event explicitly named
its producer ID. No question keyword classification or hard-coded device/rule
IDs: gate the read using the actual live MCP suboperation/schema and the same
host review/executor path. An unavailable catalogue is not a failed model plan.
"""
from __future__ import annotations
from typing import Iterable
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
    required = nested.get("required", []) if isinstance(nested, dict) else []
    if any(field not in ("appId",) for field in required):
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "unsupported_required_args"})
        return []
    properties = nested.get("properties", {}) if isinstance(nested, dict) else {}
    if not isinstance(properties, dict) or "appId" not in properties:
        if diagnostics is not None:
            diagnostics.append({"stage": "controller_config", "reason": "app_id_missing_from_live_schema"})
        return []
    # Choose the most frequently seen unlabelled command issuer without
    # relying on particular device names or hard-coded app IDs.
    ranking = sorted(candidates, key=lambda ident: (
        -sum(row.producer_id == ident and row.stage == "command_issued"
             for row in case.records), int(ident),
    ))
    ident = ranking[0]
    if diagnostics is not None:
        diagnostics.append({"stage": "controller_config", "status": "verified_issuer_proposal", "issuer_id": ident})
    return [{
        "tool": "hub_read_apps_code",
        "arguments": {"tool": "hub_get_app_config", "args": {"appId": ident}},
        "discriminator": "Read stored settings for event-confirmed command issuer",
        "information_gain": "Find currently stored controller settings without inferring historical execution",
        "hypothesis_ids": [],
    }]


__all__ = ["source_identity_proposals", "source_configuration_proposals"]

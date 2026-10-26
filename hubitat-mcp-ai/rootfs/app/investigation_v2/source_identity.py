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


__all__ = ["source_identity_proposals"]

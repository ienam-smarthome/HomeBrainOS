"""Manifest-gated, incident-first historical reads.

The user's explicitly requested dates and independently verified Hubitat IDs
form a host-side scope, NOT a device-name keyword router. These proposals
still require normal ToolExecutor and planning approval before any IO.
"""
from __future__ import annotations
from typing import Iterable
from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect
from .temporal_scope import IncidentWindow


def incident_first_proposals(
    tools: Iterable[MCPTool], verified_ids: Iterable[str],
    window: IncidentWindow, *, limit: int = 150,
) -> list[dict]:
    if limit not in (150, 500):
        return []
    gateway = next((t for t in tools if isinstance(t, MCPTool)
        and t.name == "hub_read_devices"
        and classify_tool_effect(t, {}) is ToolEffect.READ
        and isinstance(t.annotations, dict)
        and t.annotations.get("readOnlyHint") is not False
        and t.annotations.get("mutates") is not True
        and t.annotations.get("destructiveHint") is not True), None)
    if gateway is None:
        return []
    schema = gateway.input_schema if isinstance(gateway.input_schema, dict) else {}
    properties = schema.get("properties", {})
    op = properties.get("tool", {}) if isinstance(properties, dict) else {}
    allowed = op.get("enum", []) if isinstance(op, dict) else []
    if not isinstance(allowed, list) or "hub_list_device_events" not in allowed:
        return []
    from datetime import datetime, timezone
    hours = window.minimum_hours_back(now=datetime.now(timezone.utc))
    if hours > 168:
        return []
    # Never seed an unverified entity supplied by the model.
    ids = tuple(str(x) for x in verified_ids if str(x).isdecimal())[:1]
    if not ids:
        return []
    args = {"deviceId": ids[0], "hoursBack": hours, "limit": limit}
    # Some verified read manifests require a named attribute, while others
    # support an unfiltered event page (needed to retain issued commands).
    nested = properties.get("args", {}) if isinstance(properties, dict) else {}
    required = nested.get("required", []) if isinstance(nested, dict) else []
    if isinstance(required, list) and "attribute" in required:
        fields = nested.get("properties", {})
        field = fields.get("attribute", {}) if isinstance(fields, dict) else {}
        choices = field.get("enum", []) if isinstance(field, dict) else []
        if isinstance(choices, list) and choices and "switch" not in choices:
            return []
        args["attribute"] = "switch"
    return [{
        "tool": gateway.name,
        "arguments": {"tool": "hub_list_device_events",
                      "args": args},
        "discriminator": f"Incident source coverage for verified target {ids[0]} at page size {limit}",
        "information_gain": "Retain target-period commands and reported states before drawing hypotheses",
        "hypothesis_ids": [],
    }]


__all__ = ["incident_first_proposals"]

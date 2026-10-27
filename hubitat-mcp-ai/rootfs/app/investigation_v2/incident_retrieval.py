"""Manifest-validated incident-first historical reads for independently verified IDs.

Calendar windows may be older than seven days. The live read schema, not an
arbitrary age cutoff, determines whether a bounded window can be retrieved.
No historical page is proof of source completeness; every read still passes
the normal host ID/schema/effect gates before reaching ToolExecutor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect

from .device_context import _accepts_field, _args_schema
from .planning import _schema_problem
from .temporal_scope import IncidentWindow


def incident_first_proposals(
    tools: Iterable[MCPTool], verified_ids: Iterable[str],
    window: IncidentWindow, *, limit: int = 150,
) -> list[dict]:
    if limit not in (150, 500):
        return []
    ids = {str(x) for x in verified_ids
           if type(x) in (str, int) and str(x).isdecimal()}
    if len(ids) != 1:
        return []  # no ambiguous or model-guessed device scope
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

    nested = _args_schema(gateway)
    required = nested.get("required", [])
    fields = nested.get("properties", {})
    fields = fields if isinstance(fields, dict) else {}
    if (not isinstance(required, list) or
            not _accepts_field(nested, "deviceId") or
            not _accepts_field(nested, "limit")):
        return []

    args: dict[str, str | int] = {"deviceId": next(iter(ids))}
    maximum = fields.get("limit", {}).get("maximum")
    proposed_limit = (min(limit, maximum) if type(maximum) is int and maximum > 0
                      else limit)
    if proposed_limit <= 0:
        return []
    args["limit"] = proposed_limit

    # Prefer an exact bounded interval whenever the CURRENT live schema
    # permits both endpoints. Providers may still ignore these inputs; the
    # receipt tracks actual source timestamps and never assumes completeness.
    bounded = (_accepts_field(nested, "since")
               and _accepts_field(nested, "until"))
    if bounded:
        args["since"] = window.start_utc
        args["until"] = window.end_utc

    # Some upstream gateways need hoursBack even when the window is given.
    # Respect its live maximum. If the requested date is beyond that maximum,
    # an exact since/until read may still work when hoursBack is optional.
    hours = window.minimum_hours_back(now=datetime.now(timezone.utc))
    if _accepts_field(nested, "hoursBack"):
        cap = fields.get("hoursBack", {}).get("maximum")
        if type(cap) in (int, float) and cap > 0 and hours > cap:
            if "hoursBack" in required or not bounded:
                return []
        else:
            args["hoursBack"] = hours
    elif not bounded:
        return []

    if "attribute" in required:
        attr = fields.get("attribute", {})
        choices = attr.get("enum", []) if isinstance(attr, dict) else []
        if isinstance(choices, list) and choices and "switch" not in choices:
            return []
        args["attribute"] = "switch"
    if any(field not in args for field in required):
        return []
    proposal = {"tool": "hub_list_device_events", "args": args}
    if _schema_problem(proposal, schema) is not None:
        return []  # no widening a closed manifest or guessing input types

    return [{
        "tool": gateway.name,
        "arguments": proposal,
        "discriminator": ("Historical incident window for verified target "
                          f"{args['deviceId']} at page size {args['limit']}"),
        "information_gain": ("Recover source-timed commands and states "
                             "before causal planning, without assuming completeness"),
        "hypothesis_ids": [],
    }]


__all__ = ["incident_first_proposals"]

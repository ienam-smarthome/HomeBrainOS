"""Manifest-gated, domain-neutral V2 device-context reads.

The host selects source *types*, never a device identity or root cause. Every
proposal must still pass the existing read-only, schema and verified-ID gate.
No network request, write or trusted inference happens in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Iterable

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect
from .evidence import CaseFile


def _gateway(tools: Iterable[MCPTool], operation: str) -> MCPTool | None:
    for tool in tools:
        if not isinstance(tool, MCPTool) or tool.name != "hub_read_devices":
            continue
        if classify_tool_effect(tool, {}) is not ToolEffect.READ:
            continue
        ann = tool.annotations if isinstance(tool.annotations, dict) else {}
        if ann.get("readOnlyHint") is False or ann.get("mutates") is True or ann.get("destructiveHint") is True:
            continue
        props = tool.input_schema.get("properties", {}) if isinstance(tool.input_schema, dict) else {}
        op_schema = props.get("tool", {}) if isinstance(props, dict) else {}
        if operation in op_schema.get("enum", []):
            return tool
    return None


def _args_schema(tool: MCPTool) -> dict[str, Any]:
    props = tool.input_schema.get("properties", {}) if isinstance(tool.input_schema, dict) else {}
    value = props.get("args", {}) if isinstance(props, dict) else {}
    return value if isinstance(value, dict) else {}


def _proposal(tool: MCPTool, operation: str, args: dict[str, Any], why: str) -> dict[str, Any]:
    return {
        "tool": tool.name,
        "arguments": {"tool": operation, "args": args},
        "discriminator": why,
        "information_gain": "Get verified target evidence before drawing causal conclusions",
        "hypothesis_ids": [],
    }


def _safe_identifier(identities: Iterable[str]) -> str | None:
    ids = {str(i) for i in identities if isinstance(i, (str, int)) and str(i).isdecimal()}
    return next(iter(ids)) if len(ids) == 1 else None


def _last_reported_age_hours(case: CaseFile, ident: str) -> int | None:
    """A device-reported clock can guide retrieval, never prove a last event."""
    for snap in reversed(case.device_snapshots):
        if snap.get("deviceId") != ident:
            continue
        attrs = snap.get("attributes", {})
        if not isinstance(attrs, dict):
            continue
        for key in ("lastSeen", "lastMessage", "lastActivity"):
            stamp = attrs.get(key)
            if not isinstance(stamp, str):
                continue
            try:
                moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if moment.tzinfo is None:
                    continue
                age = (datetime.now(timezone.utc) - moment.astimezone(timezone.utc)).total_seconds()
                if 0 <= age <= 31 * 86400:
                    return min(744, max(24, math.ceil(age / 3600) + 24))
            except ValueError:
                continue
    return None


def device_context_proposals(
    tools: Iterable[MCPTool], verified_ids: Iterable[str], case: CaseFile, *,
    stage: str,
) -> list[dict[str, Any]]:
    """Suggest one scope-bound read when the current live manifest permits it."""
    ident = _safe_identifier(verified_ids)
    if ident is None:
        return []
    if stage == "current":
        gateway = _gateway(tools, "hub_get_device")
        if gateway is None:
            return []
        schema = _args_schema(gateway)
        fields = schema.get("properties", {})
        fields = fields if isinstance(fields, dict) else {}
        required = schema.get("required", [])
        if not isinstance(required, list) or "deviceId" not in fields:
            return []
        args: dict[str, Any] = {"deviceId": ident}
        if "mode" in required:
            modes = fields.get("mode", {}).get("enum", [])
            if isinstance(modes, list) and "status" in modes:
                args["mode"] = "status"
            else:
                return []
        if any(field not in args for field in required):
            return []
        return [_proposal(gateway, "hub_get_device", args,
                          "Current device status and source-reported last contact")]
    if stage == "history":
        gateway = _gateway(tools, "hub_list_device_events")
        if gateway is None:
            return []
        schema = _args_schema(gateway)
        fields = schema.get("properties", {})
        fields = fields if isinstance(fields, dict) else {}
        required = schema.get("required", [])
        if not isinstance(required, list) or "deviceId" not in fields:
            return []
        args = {"deviceId": ident}
        if "hoursBack" in fields:
            lookback = _last_reported_age_hours(case, ident) or 168
            constraint = fields["hoursBack"].get("maximum")
            if type(constraint) is int and constraint > 0:
                lookback = min(lookback, constraint)
            args["hoursBack"] = lookback
        if "limit" in fields:
            limit = 500
            bound = fields["limit"].get("maximum")
            if type(bound) is int and bound > 0:
                limit = min(limit, bound)
            args["limit"] = limit
        # For devices with a currently reported switch, filter periodic health
        # flapping so underlying ON/OFF transitions have a chance to surface.
        has_switch = any(snap.get("deviceId") == ident and
                         isinstance(snap.get("attributes"), dict) and
                         "switch" in snap["attributes"]
                         for snap in case.device_snapshots)
        if "attribute" in fields and (has_switch or "attribute" in required):
            choices = fields["attribute"].get("enum", [])
            if isinstance(choices, list) and choices and "switch" not in choices:
                return []
            args["attribute"] = "switch"
        if any(field not in args for field in required):
            return []
        return [_proposal(gateway, "hub_list_device_events", args,
                          "Recover state transitions without repeated health-status noise")]
    return []


__all__ = ["device_context_proposals"]

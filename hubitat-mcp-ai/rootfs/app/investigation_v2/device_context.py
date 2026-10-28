"""Manifest-gated, domain-neutral V2 device-context reads.

The host selects source *types*, never a device identity or root cause. Every
proposal must still pass the existing read-only, schema and verified-ID gate.
No network request, write or trusted inference happens in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import math
from typing import Any, Iterable, Mapping

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect
from .evidence import CaseFile


def _gateway(
    tools: Iterable[MCPTool], operation: str, *,
    learned_operations: Mapping[str, set[str]] | None = None,
) -> MCPTool | None:
    """Require positive live schema enum or exact same-session discovery.

    Gateway names or static operation knowledge are never sufficient. An
    explicit live enum that excludes the operation is authoritative even if
    fuzzy discovery returned a conflicting result.
    """
    learned = learned_operations or {}
    for tool in tools:
        if not isinstance(tool, MCPTool) or tool.name != "hub_read_devices":
            continue
        if classify_tool_effect(tool, {}) is not ToolEffect.READ:
            continue
        ann = tool.annotations if isinstance(tool.annotations, dict) else {}
        if (ann.get("readOnlyHint") is False or ann.get("mutates") is True
                or ann.get("destructiveHint") is True):
            continue
        props = (tool.input_schema.get("properties", {})
                 if isinstance(tool.input_schema, dict) else {})
        op_schema = props.get("tool", {}) if isinstance(props, dict) else {}
        explicit = op_schema.get("enum") if isinstance(op_schema, dict) else None
        if isinstance(explicit, list):
            if operation in explicit:
                return tool
        elif operation in learned.get(tool.name, set()):
            return tool
    return None


def _accepts_field(schema: dict[str, Any], field: str) -> bool:
    fields = schema.get("properties", {})
    return (isinstance(fields, dict) and field in fields
            or schema.get("additionalProperties") is not False
            and schema.get("type") in ("object", None))



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
                try:
                    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    # Hubitat can expose human-readable BST/GMT values.
                    # Only accept exact, locally verifiable clock suffixes.
                    parts = stamp.rsplit(" ", 2)
                    if len(parts) != 3 or parts[1] not in ("BST", "GMT"):
                        continue
                    raw = parts[0] + " " + parts[2]
                    naive = datetime.strptime(raw, "%a %b %d %H:%M:%S %Y")
                    zone = ZoneInfo("Europe/London")
                    moment = naive.replace(tzinfo=zone)
                    if moment.tzname() != parts[1]:
                        continue
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
    stage: str, learned_operations: Mapping[str, set[str]] | None = None,
) -> list[dict[str, Any]]:
    """Suggest one scope-bound read when the current live manifest permits it."""
    ident = _safe_identifier(verified_ids)
    if ident is None:
        return []
    if stage == "current":
        gateway = _gateway(tools, "hub_get_device", learned_operations=learned_operations)
        if gateway is None:
            return []
        schema = _args_schema(gateway)
        fields = schema.get("properties", {})
        fields = fields if isinstance(fields, dict) else {}
        required = schema.get("required", [])
        if not isinstance(required, list) or not _accepts_field(schema, "deviceId"):
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
    if stage in ("history", "history_unfiltered", "history_command_context"):
        gateway = _gateway(tools, "hub_list_device_events", learned_operations=learned_operations)
        if gateway is None:
            return []
        schema = _args_schema(gateway)
        fields = schema.get("properties", {})
        fields = fields if isinstance(fields, dict) else {}
        required = schema.get("required", [])
        if not isinstance(required, list) or not _accepts_field(schema, "deviceId"):
            return []
        args = {"deviceId": ident}
        if _accepts_field(schema, "hoursBack"):
            lookback = _last_reported_age_hours(case, ident) or 168
            constraint = fields.get("hoursBack", {}).get("maximum")
            if type(constraint) is int and constraint > 0:
                lookback = min(lookback, constraint)
            args["hoursBack"] = lookback
        if _accepts_field(schema, "limit"):
            limit = 50
            bound = fields.get("limit", {}).get("maximum")
            if type(bound) is int and bound > 0:
                limit = min(limit, bound)
            args["limit"] = limit
        # For devices with a currently reported switch, filter periodic health
        # flapping so underlying ON/OFF transitions have a chance to surface.
        has_switch = any(snap.get("deviceId") == ident and
                         isinstance(snap.get("attributes"), dict) and
                         "switch" in snap["attributes"]
                         for snap in case.device_snapshots)
        if stage in ("history_unfiltered", "history_command_context"):
            # In a causal investigation, switch-only history excludes
            # separate command-off/on events. Even a NONEMPTY switch-only
            # page does not establish absence of command issuance.
            if "attribute" in required:
                return []
            if stage == "history_command_context":
                # Prefer an event window around the latest attested switch
                # transition if the live schema accepts BOTH bounds. No
                # invented incident clock or broad whole-home reads.
                from datetime import timedelta
                instants = []
                for record in case.records:
                    if (record.target_id == ident
                            and record.stage == "state_reported"
                            and record.action == "switch"
                            and str(record.value).lower() == "off"):
                        try:
                            instant = datetime.fromisoformat(record.timestamp_utc)
                            if instant.utcoffset() is not None:
                                instants.append(instant.astimezone(timezone.utc))
                        except (ValueError, TypeError, OverflowError):
                            continue
                if (instants and "hoursBack" not in required
                        and _accepts_field(schema, "since")
                        and _accepts_field(schema, "until")):
                    target_time = max(instants)
                    args.pop("hoursBack", None)
                    args["since"] = (target_time-timedelta(hours=2)).isoformat()
                    args["until"] = (target_time+timedelta(hours=2)).isoformat()
                if "limit" in args:
                    bound = fields.get("limit", {}).get("maximum")
                    args["limit"] = min(150, bound) if type(bound) is int and bound > 0 else 150
            elif "limit" in args:
                args["limit"] = min(args["limit"], 50)
        elif _accepts_field(schema, "attribute") and (has_switch or "attribute" in required):
            choices = fields.get("attribute", {}).get("enum", [])
            if isinstance(choices, list) and choices and "switch" not in choices:
                return []
            args["attribute"] = "switch"
        if any(field not in args for field in required):
            return []
        return [_proposal(gateway, "hub_list_device_events", args,
                          ("Recover bounded unfiltered history after verified empty switch results"
                           if stage == "history_unfiltered" else
                           "Recover command events excluded by the switch-only history filter"
                           if stage == "history_command_context" else
                           "Recover state transitions without repeated health-status noise"))]
    return []


__all__ = ["device_context_proposals"]

"""Source-first controller dependency and log-coverage READ proposals.

Never infer a sensor from a name, prose, app label, event 'triggered' list,
or a number in an unrelated configuration field. Only ID-matched CURRENT
settings of event-attested command issuers can scope secondary device reads.
The existing V2 host reviewer is always authoritative.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Iterable, Mapping

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect
from .device_context import _gateway, _args_schema, _accepts_field
from .evidence import CaseFile
from .causal_evidence import focused_switch_command
from .planning import _schema_problem


def _issuer_last_command(case: CaseFile, app_id: str) -> datetime | None:
    times = []
    for item in case.records:
        if item.stage == "command_issued" and item.producer_id == app_id:
            try:
                moment = datetime.fromisoformat(item.timestamp_utc)
                if moment.utcoffset() is not None:
                    times.append(moment.astimezone(timezone.utc))
            except (ValueError, TypeError, OverflowError):
                continue
    return max(times) if times else None


def _age_hours(instant: datetime) -> int | None:
    age = (datetime.now(timezone.utc) - instant).total_seconds()
    if not -120 <= age <= 7 * 86400:
        return None
    return max(24, min(168, int(max(0, age) // 3600) + 4))


def _safe_args(schema: dict[str, Any], *,
               sensor_id: str, anchor: datetime) -> dict[str, Any] | None:
    fields = schema.get("properties", {})
    if not isinstance(fields, dict):
        return None
    required = schema.get("required", [])
    if not isinstance(required, list):
        return None
    args: dict[str, Any] = {"deviceId": sensor_id}
    # Prefer read-time window near the independently observed command,
    # never a fabricated timestamp, and only when explicitly advertised.
    if ("since" in fields and "until" in fields
            and "hoursBack" not in required):
        args["since"] = (anchor-timedelta(hours=2)).isoformat()
        args["until"] = (anchor+timedelta(hours=2)).isoformat()
    else:
        hours = _age_hours(anchor)
        if hours is None:
            return None
        if _accepts_field(schema, "hoursBack"):
            args["hoursBack"] = hours
    if _accepts_field(schema, "limit"):
        max_allowed = fields.get("limit", {}).get("maximum") if isinstance(fields.get("limit"), dict) else None
        args["limit"] = min(100, max_allowed) if type(max_allowed) is int and max_allowed >= 1 else 100
    if _schema_problem(args, schema) is not None:
        return None
    return args


def controller_sensor_history_proposals(
    tools: Iterable[MCPTool], case: CaseFile, *,
    learned_operations: Mapping[str, set[str]] | None = None,
    limit: int = 2,
) -> list[dict[str, Any]]:
    """Prioritise up to two app-selected sensors before a costly AI round."""
    gateway = _gateway(tools, "hub_list_device_events",
                       learned_operations=learned_operations)
    if gateway is None:
        return []
    schema = _args_schema(gateway)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Read only selectors derived from command-issuer app settings. A current
    # app configuration is NOT proof the selection was effective at event time.
    priorities = ("motionSensors", "motionSensor", "keepOnSensors",
                  "keepOnSensor", "presenceSensors", "presenceSensor",
                  "contactSensors", "contactSensor", "temperatureSensors",
                  "temperatureSensor", "humiditySensors", "humiditySensor",
                  "illuminanceSensors", "illuminanceSensor")
    for app_id in sorted(case.app_sensor_references, key=int):
        anchor = _issuer_last_command(case, app_id)
        if anchor is None:
            continue
        refs = sorted(case.app_sensor_references[app_id],
                      key=lambda row: priorities.index(row["key"])
                      if row["key"] in priorities else len(priorities))
        for ref in refs:
            for sensor_id in ref["deviceIds"]:
                if sensor_id in seen or len(result) >= max(0, min(4, limit)):
                    continue
                args = _safe_args(schema, sensor_id=sensor_id, anchor=anchor)
                if args is None:
                    continue
                proposal = {
                    "tool": gateway.name,
                    "arguments": {"tool": "hub_list_device_events", "args": args},
                    "discriminator": (f"Read source-attested app {app_id} "
                                      f"configured {ref['key']} sensor {sensor_id}"),
                    "information_gain": ("Compare typed sensor observations around "
                                         "event-attested command with current stored app "
                                         "selection; do not assume historical causality"),
                    "hypothesis_ids": [],
                }
                if _schema_problem(proposal["arguments"], gateway.input_schema) is None:
                    seen.add(sensor_id)
                    result.append(proposal)
    return result


def controller_log_coverage_proposals(
    tools: Iterable[MCPTool], case: CaseFile, *,
    verified_target_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Scope logs to the same source-attested latest switch issuer as config."""
    focus, _ = focused_switch_command(
        case, verified_target_ids=verified_target_ids)
    if focus is None or not focus.producer_id:
        return []
    issuer_id = focus.producer_id
    for tool in tools:
        if (not isinstance(tool, MCPTool)
                or tool.name not in {"hub_read_diagnostics", "hub_read_logs"}
                or classify_tool_effect(tool, {}) is not ToolEffect.READ):
            continue
        ann = tool.annotations if isinstance(tool.annotations, dict) else {}
        if (ann.get("readOnlyHint") is False or ann.get("mutates") is True
                or ann.get("destructiveHint") is True):
            continue
        props = tool.input_schema.get("properties", {}) if isinstance(tool.input_schema, dict) else {}
        op = props.get("tool", {}) if isinstance(props, dict) else {}
        enum = op.get("enum") if isinstance(op, dict) else None
        if not isinstance(enum, list) or "hub_get_logs" not in enum:
            continue
        inner = _args_schema(tool)
        required = inner.get("required", [])
        if not isinstance(required, list) or any(x != "appId" for x in required):
            continue
        for app_id in (issuer_id,):
            args: dict[str, Any] = {"appId": app_id}
            if _accepts_field(inner, "hoursBack"):
                args["hoursBack"] = 48
            if _accepts_field(inner, "limit"):
                args["limit"] = 80
            request = {"tool": "hub_get_logs", "args": args}
            if _schema_problem(request, tool.input_schema) is None:
                return [{
                    "tool": tool.name,
                    "arguments": request,
                    "discriminator": ("Read available log coverage for source-attested "
                                      f"command issuer app {app_id}"),
                    "information_gain": ("Determine which timestamped logs are currently "
                                         "retained, without treating absence as proof of "
                                         "restart or historical nonexecution"),
                    "hypothesis_ids": [],
                }]
    return []


__all__ = [
    "controller_sensor_history_proposals",
    "controller_log_coverage_proposals",
]

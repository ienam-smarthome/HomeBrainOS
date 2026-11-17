"""Original-receipt grounded, *advertised* read-only causal source opportunities.

This is navigation, not tool selection, truth of any historical decision,
consent for a write, or proof that an advertised read can return event data.
No tool is invoked; only executed, identity-checked original device history
and existing catalog definitions are inspected. Never construct a tool call
or invent a leaf/argument not present in an offered schema.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from investigation_review import is_read_only_review_tool
from native_device_event_receipt import original_device_event_history

_ID = re.compile(r"[0-9]{1,9}\Z")
_COMMAND = re.compile(r"command-[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_STATE_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_REPORTED_STATES = frozenset({
    "on", "off", "heating", "idle", "cooling", "active", "inactive",
    "open", "closed", "locked", "unlocked", "wet", "dry",
    "present", "not present", "running", "stopped", "alarm", "clear",
    "detected", "normal", "armed", "disarmed", "online", "offline",
})
_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,60}\Z")
_TOOL = re.compile(r"hub_(?:read|get|list|search)_[A-Za-z][A-Za-z0-9_]{0,80}\Z")
_ENUM = re.compile(r"[A-Za-z0-9_-]{1,30}\Z")
_MAX_SOURCE_RECEIPTS = 32
_MAX_EVENTS_PER_SOURCE = 200
_MAX_COMMAND_LEADS = 4
_MAX_STATE_LEADS = 6
_MAX_ISSUERS = 3
_MAX_TOOLS = 6
_MAX_FIELDS = 8


def _source_clock(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None and dt.utcoffset() is not None else None


def _id(value: Any) -> str | None:
    if type(value) is int:
        value = str(value)
    return value if isinstance(value, str) and _ID.fullmatch(value) else None


def _field_schema(function: dict) -> tuple[list[dict], bool]:
    schema = function.get("parameters")
    if not isinstance(schema, dict):
        return [], False
    props = schema.get("properties")
    if not isinstance(props, dict):
        return [], False
    required = schema.get("required")
    required = set(required) if isinstance(required, list) and all(
        isinstance(k, str) for k in required
    ) else set()
    fields = []
    for name, details in props.items():
        if (not isinstance(name, str) or not _FIELD.fullmatch(name)
                or not isinstance(details, dict)):
            continue
        kind = details.get("type")
        if kind not in ("string", "integer", "number", "boolean",
                        "array", "object"):
            kind = "unspecified"
        row = {"name": name, "type": kind, "required": name in required}
        choices = details.get("enum")
        if isinstance(choices, list):
            safe = [x for x in choices if isinstance(x, str) and _ENUM.fullmatch(x)]
            if safe:
                row["advertised_enum"] = safe[:6]
        fields.append(row)
        if len(fields) >= _MAX_FIELDS:
            break
    gateway = "tool" in props and "args" in props
    return fields, gateway


def _family(name: str, field_names: set[str], gateway: bool) -> str | None:
    lower = name.lower()
    if gateway:
        return ("read_only_leaf_gateway" if any(
            k in lower for k in ("logs", "apps", "history", "events", "rules")
        ) else None)
    if any(k in lower for k in ("logs", "execution", "trace")):
        return "potential_event_time_application_log"
    if "event" in lower or "history" in lower:
        return "potential_event_time_device_or_input_history"
    if name in ("hub_get_app", "hub_list_apps", "hub_get_rule",
                "hub_get_app_settings", "hub_read_app_config"):
        return "current_configuration_not_event_execution"
    return None


def causal_read_opportunities(
    receipts: list[dict], offered_read_tools: list[dict],
) -> dict | None:
    """Compact, source-safe options for a *model-chosen* discriminating read.

    Emits None without source-bound command OR categorical state evidence.
    Neither a state report nor a command issuer establishes the actual
    event-time decision, initiating room or physical effect.
    Never refer to an unadvertised tool; never assert logs are available.
    """
    if not isinstance(receipts, list) or not isinstance(offered_read_tools, list):
        return None
    leads: list[tuple[datetime, dict]] = []
    state_reports: list[tuple[datetime, dict]] = []
    ids: set[str] = set()
    for rec in receipts[:_MAX_SOURCE_RECEIPTS]:
        native = original_device_event_history(rec)
        if native is None:
            continue
        requested_device_id, _, events = native
        for row in events[:_MAX_EVENTS_PER_SOURCE]:
            if not isinstance(row, dict):
                continue
            inline_id = row.get("deviceId")
            if inline_id is not None and _id(inline_id) != requested_device_id:
                continue
            stamp = _source_clock(row.get("date"))
            if stamp is None:
                continue
            name = row.get("name")
            if (row.get("type") in (None, "command")
                    and isinstance(name, str) and _COMMAND.fullmatch(name)):
                origin = row.get("producedBy")
                app_id = _id(origin.get("appId")) if isinstance(origin, dict) else None
                if app_id:
                    ids.add(app_id)
                    leads.append((stamp, {
                        "command_name": name,
                        "recorded_issuer_app_id": app_id,
                        "observed_original_timestamp": row["date"],
                        "requested_output_device_id": requested_device_id,
                    }))
                continue
            if row.get("type") not in (None, "event"):
                continue
            value = row.get("value")
            if (not isinstance(name, str) or not _STATE_FIELD.fullmatch(name)
                    or not isinstance(value, str)
                    or value.lower() not in _REPORTED_STATES):
                continue
            notified_ids = []
            notified = row.get("triggered")
            if isinstance(notified, list):
                for listener in notified[:8]:
                    app_id = _id(listener.get("appId")) if isinstance(listener, dict) else None
                    if app_id and app_id not in notified_ids:
                        notified_ids.append(app_id)
            state_reports.append((stamp, {
                "reported_attribute": name,
                "reported_value": value.lower(),
                "observed_original_timestamp": row["date"],
                "requested_output_device_id": requested_device_id,
                "notified_listener_app_ids_not_issuers": notified_ids[:6],
            }))
    if not leads and not state_reports:
        return None

    # Collapse repeated identical rows from overlapping history requests.
    unique = {}
    for stamp, item in leads:
        key = (item["requested_output_device_id"], item["recorded_issuer_app_id"],
               item["command_name"], stamp)
        unique[key] = (stamp, item)
    latest = sorted(unique.values(), key=lambda x: x[0], reverse=True)
    unique_states = {}
    for stamp, item in state_reports:
        key = (item["requested_output_device_id"], item["reported_attribute"],
               item["reported_value"], stamp)
        unique_states[key] = (stamp, item)
    state_latest = sorted(unique_states.values(), key=lambda x: x[0], reverse=True)
    recorded_state_leads = []
    for _, item in state_latest[:_MAX_STATE_LEADS]:
        reported = dict(item)
        if latest:
            # Do not elevate listeners into the command-led issuer index.
            reported.pop("notified_listener_app_ids_not_issuers", None)
        recorded_state_leads.append(reported)
    eligible = {item["recorded_issuer_app_id"]
                for _, item in latest[:_MAX_COMMAND_LEADS]}
    issuer_ids = sorted(eligible, key=int)[:_MAX_ISSUERS]

    attempted: set[str] = set()
    succeeded: set[str] = set()
    for rec in receipts:
        if not isinstance(rec, dict):
            continue
        name = rec.get("name")
        args = rec.get("arguments")
        if (not isinstance(name, str) or not isinstance(args, dict)
                or not any(k in name.lower() for k in ("log", "trace", "execution"))):
            continue
        app_id = _id(args.get("appId"))
        if app_id in eligible:
            attempted.add(app_id)
            if rec.get("success") is True:
                succeeded.add(app_id)

    advertised = []
    seen = set()
    for tool in offered_read_tools:
        func = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(func, dict):
            continue
        name = func.get("name")
        if (not isinstance(name, str) or not _TOOL.fullmatch(name)
                or not is_read_only_review_tool(name) or name in seen):
            continue
        fields, gateway = _field_schema(func)
        family = _family(name, {f["name"] for f in fields}, gateway)
        if family is None:
            continue
        seen.add(name)
        advertised.append({
            "offered_function_name": name, "source_family": family,
            "advertised_argument_fields": fields,
            "leaf_contract_requires_discovery": gateway,
            "tool_offered_not_executed_by_this_index": True,
        })
    advertised.sort(key=lambda t: (
        0 if t["source_family"] == "potential_event_time_application_log" else
        1 if t["source_family"] == "potential_event_time_device_or_input_history" else
        2, t["offered_function_name"]
    ))
    return {
        "scope": "original_successful_device_command_or_state_rows_and_live_read_only_tool_definitions",
        "navigation_origin": (
            "native_command_with_recorded_issuer" if latest
            else "native_state_report_without_recorded_command_issuer"
        ),
        "recorded_state_observation_leads": recorded_state_leads,
        "state_report_is_not_command_decision_or_physical_confirmation": True,
        "listener_ids_are_not_command_issuers": True,
        "recorded_command_leads": [d for _, d in latest[:_MAX_COMMAND_LEADS]],
        "recorded_issuer_app_ids": issuer_ids,
        "issuer_log_read_attempted_in_this_request": sorted(attempted, key=int),
        "issuer_log_read_succeeded_in_this_request": sorted(succeeded, key=int),
        "advertised_source_tools": advertised[:_MAX_TOOLS],
        "advertised_source_tools_omitted": max(0, len(advertised) - _MAX_TOOLS),
        "source_has_event_time_decision_evidence": "not_established",
        "app_issuer_is_not_actual_trigger_or_room_demand": True,
        "source_tool_advertisement_is_not_data_availability": True,
        "no_tool_selected_or_called_by_this_index": True,
    }

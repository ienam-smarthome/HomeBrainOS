"""Typed, shadow-only evidence packets from original MCP receipts.

This module does not decide whether prose is true and never changes an answer.
It gives future claim binding a stable receipt/fact vocabulary while preserving
the original receipts as the sole authority.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import math
import re

from investigation_source_ledger import _response, _SAFE_FIELD, _SAFE_ID

SCHEMA = "homebrain-v2-claim-receipt-contract-shadow.v1"
_MAX_RECEIPTS = 40
_MAX_FACTS = 400
_SAFE_SCOPE = re.compile(r"^[A-Za-z0-9:+._/% -]{1,120}$")
_SAFE_NUMBER = re.compile(r"^-?\d{1,12}(?:\.\d{1,8})?$")
_SAFE_STATE = frozenset({
    "on", "off", "open", "closed", "active", "inactive", "idle",
    "heating", "cooling", "online", "offline", "unknown", "present",
    "not present", "locked", "unlocked", "running", "stopped",
})
_SCOPE_FIELDS = (
    "deviceId", "appId", "attribute", "attributeNames", "level", "mode",
    "since", "until", "hoursBack", "limit", "cursor", "format", "scope",
)
_INFO_FIELDS = (
    "uptimeSeconds", "freeMemoryKB", "internalTempCelsius", "databaseSizeMB",
    "firmwareVersion", "mcpServerVersion", "safeMode", "readEnabled",
    "writeEnabled",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _safe_id(value: object) -> str | None:
    return (
        str(value)
        if type(value) in (str, int) and _SAFE_ID.fullmatch(str(value))
        else None
    )


def _safe_field(value: object) -> str | None:
    return value if isinstance(value, str) and _SAFE_FIELD.fullmatch(value) else None


def _safe_value(value: object) -> object | None:
    if type(value) is bool:
        return value
    if type(value) in (int, float) and math.isfinite(value) and abs(value) < 1e12:
        return value
    if not isinstance(value, str) or len(value) > 80 or any(ord(ch) < 32 for ch in value):
        return None
    stripped = value.strip()
    if stripped.lower() in _SAFE_STATE or _SAFE_NUMBER.fullmatch(stripped):
        return stripped
    return None


def _scope(arguments: object) -> dict:
    if not isinstance(arguments, dict):
        return {}
    result = {}
    for key in _SCOPE_FIELDS:
        value = arguments.get(key)
        if type(value) in (int, float, bool):
            result[key] = value
        elif isinstance(value, str) and _SAFE_SCOPE.fullmatch(value):
            result[key] = value
        elif isinstance(value, list) and len(value) <= 16:
            fields = [_safe_field(item) for item in value]
            if all(field is not None for field in fields):
                result[key] = fields
    return result


def _coverage(
    tool: str, scope: dict, envelope: dict, data: dict, rows: list | None,
) -> dict:
    returned = len(rows) if isinstance(rows, list) else None
    result = {
        "returned_rows": returned,
        "reported_count": data.get("count") if type(data.get("count")) is int else None,
        "reported_total": data.get("total") if type(data.get("total")) is int else None,
        "reported_matches": data.get("matched") if type(data.get("matched")) is int else None,
        "native_has_more": data.get("hasMore") if type(data.get("hasMore")) is bool else None,
        "upstream_truncated": bool(
            envelope.get("truncated") is True or data.get("truncated") is True
            or data.get("response_too_large") is True
        ),
    }
    limit = scope.get("limit")
    result["requested_limit_reached"] = (
        isinstance(returned, int) and type(limit) is int and limit > 0 and returned >= limit
    )
    result["returned_equals_reported_total"] = (
        isinstance(returned, int) and type(result["reported_total"]) is int
        and returned == result["reported_total"]
    )
    if tool in ("hub_list_device_events", "hub_get_logs"):
        result.update({
            "requested_window_completeness_proven": False,
            "absence_of_unreturned_records_proven": False,
            "continuous_state_between_rows_proven": False,
        })
    if tool == "hub_get_logs" and result["reported_total"] is not None:
        result["reported_total_scope"] = "source_unspecified_not_query_coverage"
    return result


def _state_facts(receipt_id: str, data: dict, tool: str) -> list[dict]:
    if tool == "hub_list_devices":
        devices = data.get("devices")
    elif tool == "hub_get_device":
        devices = [data]
    else:
        return []
    if not isinstance(devices, list):
        return []
    facts = []
    for device in devices[:250]:
        if not isinstance(device, dict) or (device_id := _safe_id(device.get("id"))) is None:
            continue
        states = device.get("currentStates")
        if isinstance(states, dict):
            fields = states.items()
        else:
            attributes = device.get("attributes")
            fields = (
                (row.get("name"), row.get("value")) for row in attributes[:64]
                if isinstance(row, dict)
            ) if isinstance(attributes, list) else ()
        for field, value in fields:
            safe_field, safe_value = _safe_field(field), _safe_value(value)
            if safe_field is None or safe_value is None:
                continue
            facts.append({
                "fact_id": f"{receipt_id}.state.{len(facts) + 1}",
                "fact_type": "reported_current_state",
                "source_role": (
                    "stored_device_inventory_attribute" if tool == "hub_list_devices"
                    else "stored_individual_device_attribute"
                ),
                "subject": {"device_id": device_id},
                "field": safe_field,
                "value": safe_value,
                "attribute_specific_event_timestamp_proven": False,
                "physical_state_proven": False,
            })
        activity = device.get("lastActivity")
        if isinstance(activity, str) and 0 < len(activity) <= 45:
            try:
                stamp = datetime.fromisoformat(activity.replace("Z", "+00:00"))
            except ValueError:
                stamp = None
            if stamp is not None and stamp.tzinfo is not None:
                facts.append({
                    "fact_id": f"{receipt_id}.activity.{device_id}",
                    "fact_type": "reported_device_activity_marker",
                    "source_role": "device_wide_last_activity_not_attribute_sample",
                    "subject": {"device_id": device_id},
                    "source_timestamp": activity,
                    "attribute_specific_event_timestamp_proven": False,
                    "device_reachability_proven": False,
                })
    return facts


def _event_facts(receipt_id: str, data: dict, tool: str) -> list[dict]:
    # App configuration fields named "events" cannot establish native device
    # history. Only the matching source-class tool supplies these event facts.
    if tool != "hub_list_device_events":
        return []
    events = data.get("events")
    if not isinstance(events, list):
        return []
    facts = []
    for event in events[:250]:
        if not isinstance(event, dict):
            continue
        field = _safe_field(event.get("name"))
        timestamp = event.get("date")
        if field is None or not isinstance(timestamp, str) or len(timestamp) > 45:
            continue
        value = _safe_value(event.get("value"))
        producer = (
            event.get("producedBy")
            if isinstance(event.get("producedBy"), dict) else {}
        )
        command = field.startswith("command-") or event.get("type") == "command"
        fact = {
            "fact_id": f"{receipt_id}.event.{len(facts) + 1}",
            "fact_type": "recorded_command" if command else "reported_event_state",
            "source_role": (
                "native_device_command_row" if command
                else "native_device_reported_attribute_event"
            ),
            "independent_physical_actuation_proven": False,
            "app_self_reported_history_proven": False,
            "subject": {
                key: ident for key, ident in (
                    ("device_id", _safe_id(data.get("deviceId"))),
                    ("app_id", _safe_id(data.get("appId"))),
                ) if ident is not None
            },
            "field": field,
            "source_timestamp": timestamp,
            "continuous_state_until_next_row_proven": False,
        }
        if value is not None:
            fact["value"] = value
        if command:
            issuer = _safe_id(producer.get("appId"))
            if issuer is not None:
                fact["recorded_issuer_app_id"] = issuer
        else:
            notified = event.get("triggered")
            notified = notified[:32] if isinstance(notified, list) else []
            listeners = list(dict.fromkeys(
                ident for row in notified if isinstance(row, dict)
                if (ident := _safe_id(row.get("appId"))) is not None
            ))
            if listeners:
                fact["notified_listener_app_ids"] = listeners
                fact["notified_listener_is_command_issuer_proven"] = False
            reporter_device = _safe_id(producer.get("deviceId"))
            reporter_app = _safe_id(producer.get("appId"))
            if reporter_device is not None:
                fact["reporter_device_id"] = reporter_device
            if reporter_app is not None:
                fact["reporter_app_id"] = reporter_app
        facts.append(fact)
    return facts


def _app_identity_facts(receipt_id: str, data: dict, tool: str) -> list[dict]:
    """Typed app identity is not a native device or an execution receipt."""
    if tool == "hub_list_apps":
        apps = data.get("apps")
        if not isinstance(apps, list):
            return []
        facts = []
        for row in apps[:250]:
            if not isinstance(row, dict):
                continue
            ident = _safe_id(row.get("id"))
            if ident is None:
                continue
            facts.append({
                "fact_id": f"{receipt_id}.app.{len(facts) + 1}",
                "fact_type": "reported_installed_app_identity",
                "source_role": "app_inventory_not_device_inventory",
                "subject": {"app_id": ident},
                "historical_app_execution_proven": False,
            })
        return facts
    if tool == "hub_get_app_config":
        ident = _safe_id(data.get("appId"))
        if ident is None:
            return []
        return [{
            "fact_id": f"{receipt_id}.app_config.{ident}",
            "fact_type": "reported_app_configuration",
            "source_role": "stored_app_configuration_not_event_time_execution",
            "subject": {"app_id": ident},
            "historical_app_execution_proven": False,
        }]
    return []


def _log_facts(receipt_id: str, data: dict) -> list[dict]:
    entries = data.get("entries")
    if not isinstance(entries, list):
        return []
    groups = Counter()
    for entry in entries[:250]:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        level = _safe_field(str(entry.get("level", "")).lower())
        if isinstance(name, str) and name and len(name) <= 120 and level is not None:
            groups[(_digest(name), level)] += 1
    return [{
        "fact_id": f"{receipt_id}.log_group.{position}",
        "fact_type": "returned_log_source_group",
        "source_role": "native_past_log_rows_not_physical_execution",
        "source_name_sha256_prefix": source_hash,
        "level": level,
        "returned_rows": count,
    } for position, ((source_hash, level), count) in enumerate(
        sorted(groups.items()), 1
    )]


def _info_facts(receipt_id: str, data: dict) -> list[dict]:
    facts = []
    for field in _INFO_FIELDS:
        if field not in data or (value := _safe_value(data[field])) is None:
            continue
        facts.append({
            "fact_id": f"{receipt_id}.info.{field}",
            "fact_type": "reported_hub_info",
            "field": field,
            "value": value,
        })
    alerts = data.get("healthAlerts")
    if isinstance(alerts, dict) and isinstance(alerts.get("active"), list):
        facts.append({
            "fact_id": f"{receipt_id}.info.active_health_alert_count",
            "fact_type": "reported_current_alert_count",
            "field": "active_health_alert_count",
            "value": len(alerts["active"]),
            "historical_alert_absence_proven": False,
        })
    return facts


def build_claim_receipt_contract(question: str, answer: str, receipts: list[dict]) -> dict:
    """Return bounded typed evidence telemetry; never enforce or rewrite."""
    packets = []
    fact_count = 0
    for position, receipt in enumerate(receipts[:_MAX_RECEIPTS], 1):
        if not isinstance(receipt, dict):
            continue
        receipt_id = f"r{position}"
        tool = str(receipt.get("name") or "")[:100]
        packet = {
            "receipt_id": receipt_id,
            "receipt_number": position,
            "tool": tool,
            "success": receipt.get("success") is True,
            "operation_executed": receipt.get("operation_executed") is not False,
            "requested_scope": _scope(receipt.get("arguments")),
            "facts": [],
        }
        if packet["success"] and packet["operation_executed"]:
            envelope, data = _response(receipt)
            if isinstance(envelope, dict) and isinstance(data, dict):
                rows = data.get(
                    "events" if tool == "hub_list_device_events" else
                    "entries" if tool == "hub_get_logs" else
                    "devices" if tool == "hub_list_devices" else ""
                )
                packet["coverage"] = _coverage(
                    tool, packet["requested_scope"], envelope, data,
                    rows if isinstance(rows, list) else None,
                )
                facts = (
                    _state_facts(receipt_id, data, tool)
                    + _event_facts(receipt_id, data, tool)
                    + _app_identity_facts(receipt_id, data, tool)
                    + _log_facts(receipt_id, data)
                    + (_info_facts(receipt_id, data) if tool == "hub_get_info" else [])
                )
                remaining = max(0, _MAX_FACTS - fact_count)
                packet["facts"] = facts[:remaining]
                packet["facts_truncated"] = len(facts) > remaining
                fact_count += len(packet["facts"])
        packets.append(packet)
    return {
        "schema": SCHEMA,
        "mode": "shadow_only",
        "enforced": False,
        "answer_changed": False,
        "question_sha256_prefix": _digest(question) if isinstance(question, str) else None,
        "published_answer_sha256_prefix": _digest(answer) if isinstance(answer, str) else None,
        "claim_binding_status": "not_supplied_by_current_runtime",
        "claim_bindings": [],
        "typed_receipts": packets,
        "summary": {
            "receipts_seen": min(len(receipts), _MAX_RECEIPTS),
            "successful_executed_receipts": sum(
                packet["success"] and packet["operation_executed"] for packet in packets
            ),
            "typed_facts": fact_count,
            "additional_receipts_not_indexed": max(0, len(receipts) - _MAX_RECEIPTS),
            "facts_truncated": any(
                packet.get("facts_truncated") is True for packet in packets
            ),
        },
        "note": (
            "Original receipts remain authoritative. This packet supplies stable typed "
            "fact IDs and explicit coverage limits only; it does not attest any prose claim."
        ),
    }

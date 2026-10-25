"""Reviewed supplementary receipt adapters for Investigation V2.

No model-authored prose is parsed into facts. These adapters consume deliberately
typed, read-only host receipts; unfamiliar upstream shapes remain coverage-only.
They do not make MCP calls. Current stored app settings are NOT historical
effective behaviour, a log line is NOT proof of execution, and a transport
acknowledgement is NOT proof that a physical device changed state.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_ID = re.compile(r"^[0-9]{1,20}$")
_SENSITIVE = ("token", "password", "secret", "apikey", "auth", "credential", "private")
_MAX_FIELDS = 96


def _id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    raw = str(value).strip()
    return raw if _ID.fullmatch(raw) else None


def _field_value(field: Mapping[str, Any]) -> str | None:
    """Project only safe values already selected by the trusted host."""
    if "deviceIds" in field:
        values = field["deviceIds"]
        if (not isinstance(values, list) or not 0 < len(values) <= 32
                or any(_id(item) is None for item in values)):
            return None
        return "device IDs: " + ",".join(sorted({_id(item) for item in values}, key=int))
    if "numericValue" in field:
        value = field["numericValue"]
        unit = field.get("unitFromKey", "unspecified")
        if (type(value) not in (int, float) or not math.isfinite(value)
                or value < 0 or value > 10080
                or unit not in ("seconds", "minutes", "unspecified")):
            return None
        return f"{value} {unit}"
    if "minutes" in field:
        value = field["minutes"]
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not 0 <= value <= 1440):
            return None
        return f"{value} minutes"
    if type(field.get("value")) is bool:
        return "true" if field["value"] else "false"
    if isinstance(field.get("value"), str):
        # The upstream typed controller projection allowlists short enum values.
        value = field["value"].lower().strip()
        if value in ("off", "on", "none"):
            return value
    return None


def supplemental_events(
    receipt: Mapping[str, Any], source_id: str, tool: str, operation: str,
    args: Mapping[str, Any], details: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return reviewed structured observations with precise source pointers.

    Each result: category, target_id, event, stage, reference, time_basis.
    Host receipt observation time is used only for CURRENT configuration
    snapshots, not presented as the time the settings became effective.
    """
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if receipt.get("success") is not True:
        return rows, errors
    if receipt.get("mutates") is not False or receipt.get("effect") != "read":
        return rows, errors  # never use write receipts to imply a safe read
    evidence_kind = receipt.get("evidence_kind")

    if (operation == "hub_get_app_config"
            and evidence_kind == "typed_existing_rule_partial_settings"):
        target = _id(args.get("appId"))
        actual = _id(details.get("appId"))
        if not target or target != actual or details.get("settingsReadable") is not True:
            errors.append("app config missing an ID-matched readable projection")
            return rows, errors
        read_at = receipt.get("timestamp")
        for key in ("indexedFields", "controllerFields"):
            fields = details.get(key)
            if not isinstance(fields, list) or len(fields) > _MAX_FIELDS:
                errors.append(f"{key}: invalid or excessive projection")
                continue
            for index, field in enumerate(fields):
                if not isinstance(field, dict):
                    errors.append(f"{key}[{index}]: malformed field")
                    continue
                name = field.get("key")
                if (not isinstance(name, str) or not _FIELD.fullmatch(name)
                        or any(part in name.casefold() for part in _SENSITIVE)):
                    errors.append(f"{key}[{index}]: unsupported field")
                    continue
                value = _field_value(field)
                if value is None:
                    errors.append(f"{key}[{index}]: unsupported value")
                    continue
                rows.append({
                    "category": "stored_app_config", "target_id": target,
                    "event": {"name": f"stored-setting:{name}", "value": value,
                              "date": read_at},
                    "stage": "config_stored",
                    "pointer": f"{source_id}.details.{key}[{index}]",
                    "time_basis": "read_observed_at",
                })
        return rows, errors

    # The execution and acknowledgement adapters require EXPLICIT structured
    # host evidence. No regex interpretation of 'Action: ON' logs as execution.
    if (operation == "hub_get_app_execution"
            and evidence_kind == "typed_app_execution"):
        target_app = _id(args.get("appId"))
        payload = details.get("executionEvents")
        if not target_app or not isinstance(payload, list) or len(payload) > _MAX_FIELDS:
            return rows, ["app execution: missing target ID or bounded typed events"]
        for index, item in enumerate(payload):
            if (not isinstance(item, dict) or _id(item.get("appId")) != target_app
                    or item.get("executionObserved") is not True):
                errors.append(f"executionEvents[{index}]: unverified app execution")
                continue
            action = item.get("action")
            if not isinstance(action, str) or not _FIELD.fullmatch(action):
                errors.append(f"executionEvents[{index}]: invalid action")
                continue
            subject = _id(item.get("deviceId"))
            if "deviceId" in item and subject is None:
                errors.append(f"executionEvents[{index}]: invalid device ID")
                continue
            rows.append({
                "category": "app_execution",
                "target_id": subject or target_app,
                "event": {
                    "name": f"app-executed:{action}", "date": item.get("date"),
                    "producedBy": {"id": target_app, "type": "app"},
                },
                "stage": "app_execution_observed",
                "pointer": f"{source_id}.details.executionEvents[{index}]",
                "time_basis": "event_time",
            })
        return rows, errors

    if (operation == "hub_get_command_status"
            and evidence_kind == "typed_transport_ack"):
        target = _id(args.get("deviceId"))
        payload = details.get("acknowledgements")
        if not target or not isinstance(payload, list) or len(payload) > _MAX_FIELDS:
            return rows, ["transport ack: missing target ID or bounded typed events"]
        for index, item in enumerate(payload):
            if (not isinstance(item, dict) or _id(item.get("deviceId")) != target
                    or item.get("acknowledged") is not True):
                errors.append(f"acknowledgements[{index}]: unmatched or unverified ack")
                continue
            command_id = item.get("commandId")
            if (not isinstance(command_id, str) or not command_id
                    or len(command_id) > 80 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", command_id)):
                errors.append(f"acknowledgements[{index}]: invalid command correlation ID")
                continue
            rows.append({
                "category": "transport_ack", "target_id": target,
                "event": {
                    "name": "transport-ack", "date": item.get("date"),
                    "value": command_id,
                },
                "stage": "transport_ack",
                "pointer": f"{source_id}.details.acknowledgements[{index}]",
                "time_basis": "event_time",
            })
    return rows, errors

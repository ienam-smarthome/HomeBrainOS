"""Stage 9.1: a verified device command may authorise a bounded app-log READ.

Source identity comes from a fresh target-scoped native command event, never
from user-supplied app IDs, room names or switch timing. App-log text never
leaves this deterministic projection. An app-log declaration is not physical
execution or causal proof.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any

from device_history_service import DeviceHistoryService
from mcp_client import tool_succeeded
from archived_app_decision_evidence import _decision_stage

_ID = re.compile(r"^[0-9]{1,12}$")
_ALLOWED_LOG_HORIZON = timedelta(hours=48)
_LOG_PAD = timedelta(minutes=2)


def _utc(raw: Any) -> datetime | None:
    if type(raw) is not str or len(raw) > 64:
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo is not None else None


def app_decision_read_plan(device_id: str, command_at_utc: str,
                           now: datetime) -> dict[str, Any]:
    if type(device_id) is not str or not _ID.fullmatch(device_id):
        raise ValueError("invalid device ID")
    command_at = _utc(command_at_utc)
    if now.tzinfo is None or command_at is None:
        raise ValueError("UTC-aware command timestamp required")
    now = now.astimezone(timezone.utc)
    if not (now - _ALLOWED_LOG_HORIZON <= command_at <= now):
        raise ValueError("command outside recent 48-hour window")
    return {
        "device_id": device_id,
        "requested_command_at_utc": command_at.isoformat(),
        "hours_back": max(1, min(49, math.ceil((now-command_at).total_seconds()/3600)+1)),
        "device_event_operation": "command-off",
        "event_limit": 50,
        "log_limit": 100,
    }


def _base(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "homebrain-stage91-verified-app-log-shadow.v1",
        "status": "not_verified",
        "device_id": plan["device_id"],
        "verified_command_at_utc": None,
        "recorded_issuer_app_id": None,
        "command_record_verified_in_bounded_page": False,
        "command_row_device_id_explicit": False,
        "app_log_read_attempted": False,
        "app_log_rows_returned": None,
        "classified_decision_rows": [],
        "log_scope_basis": None,
        "source_coverage_complete": False,
        "app_decision_or_action_proven": False,
        "physical_execution_proven": False,
        "causal_link_proven": False,
        "device_clock_authenticated": False,
        "production_publisher_approval": False,
        "cloud_requests": 0,
        "device_commands": 0,
        "limitations": [
            "Source history is bounded and can omit a command even if it occurred.",
            "Recorded command issuer does not establish the app's upstream trigger.",
            "App log text is a declaration, not command delivery or physical actuation.",
            "An absent app-log message does not prove the app took no action.",
            "Only app-log classification metadata are returned, never private messages.",
        ],
    }


def verified_issuer(plan: dict[str, Any], command_source: Any) -> dict[str, Any]:
    """Fail closed unless an exactly matching command-off app producer is found."""
    packet = _base(plan)
    if not tool_succeeded(command_source):
        packet["status"] = "command_source_read_failed"
        return packet
    payload = DeviceHistoryService._payload(command_source.data)
    if type(payload.get("events")) is not list:
        packet["status"] = "command_source_unusable"
        return packet
    rows = DeviceHistoryService._events(command_source.data, limit=50)
    requested = _utc(plan["requested_command_at_utc"])
    issuers = set()
    explicit_target_id = False
    for row in rows:
        if str(row.get("name") or "").casefold() != "command-off":
            continue
        row_id = row.get("deviceId")
        if row_id not in (None, "") and str(row_id) != plan["device_id"]:
            continue
        if row_id not in (None, ""):
            explicit_target_id = True
        when = _utc(row.get("date"))
        if when != requested:
            continue
        producer = DeviceHistoryService._producer(row.get("producedBy"))
        app_id = str(producer.get("id") or "")
        if producer.get("type") == "app" and _ID.fullmatch(app_id):
            issuers.add(app_id)
    if len(issuers) != 1:
        packet["status"] = (
            "ambiguous_command_issuer" if issuers
            else "command_issuer_not_verified_in_returned_page"
        )
        return packet
    app_id = next(iter(issuers))
    packet.update({
        "status": ("verified_app_issuer_only" if explicit_target_id
                   else "issuer_verified_from_backend_scoped_page"),
        "recorded_issuer_app_id": app_id,
        "verified_command_at_utc": requested.isoformat(),
        "command_record_verified_in_bounded_page": True,
        "command_row_device_id_explicit": explicit_target_id,
        "log_scope_basis": ("explicit_target_and_app_producer"
                            if explicit_target_id else
                            "backend_target_filter_and_app_producer"),
    })
    packet["log_read_arguments"] = {
        "tool": "hub_get_logs",
        "args": {
            "appId": app_id,
            "since": (requested-_LOG_PAD).isoformat().replace("+00:00","Z"),
            "until": (requested+_LOG_PAD).isoformat().replace("+00:00","Z"),
            "limit": plan["log_limit"],
        },
    }
    return packet


def project_verified_app_logs(packet: dict[str, Any], log_source: Any) -> dict[str, Any]:
    result = {k: v for k,v in packet.items() if k != "log_read_arguments"}
    if not packet.get("command_record_verified_in_bounded_page"):
        result["status"] = "not_verified"
        return result
    result["app_log_read_attempted"] = True
    if not tool_succeeded(log_source):
        result["status"] = "app_log_read_failed"
        return result
    data = log_source.data
    for _ in range(4):
        if not isinstance(data, dict):
            break
        if type(data.get("logs")) is list:
            break
        data = next((data[k] for k in ("result","data","output")
                     if isinstance(data.get(k),dict)), data)
        if data is log_source.data:
            break
    logs = data.get("logs") if isinstance(data,dict) else None
    if type(logs) is not list:
        result["status"] = "app_log_payload_unusable"
        return result
    result["app_log_rows_returned"] = min(len(logs),100)
    result["page_at_100_cap"] = len(logs)>=100
    app_id = packet["recorded_issuer_app_id"]
    begin = _utc(packet["log_read_arguments"]["args"]["since"])
    end = _utc(packet["log_read_arguments"]["args"]["until"])
    rows = []
    rejected_mismatch = 0
    unverified_scope = 0
    for row in logs[:100]:
        if type(row) is not dict:
            continue
        event_at = _utc(row.get("date") or row.get("timestamp") or row.get("time"))
        if event_at is None or not begin <= event_at <= end:
            continue
        row_id = row.get("appId") or row.get("app_id")
        if row_id not in (None, "") and str(row_id) != app_id:
            rejected_mismatch += 1
            continue
        if row_id in (None, ""):
            unverified_scope += 1
        message = row.get("message")
        if type(message) is not str:
            continue
        # Never return message content, app names, devices, arbitrary IDs.
        stage = _decision_stage(message[:1500])
        if stage:
            rows.append({
                "source_row_index": len(rows)+1,
                "classification": stage,
                "reported_at_utc": event_at.isoformat(),
                "app_identity_basis": (
                    "explicit_app_id" if row_id not in (None,"")
                    else "backend_filter_only_unverified"
                ),
                "decision_execution_verified": False,
            })
    result.update({
        "status": "bounded_app_declarations_found" if rows else "no_classifiable_app_declarations",
        "classified_decision_rows": rows[:20],
        "excluded_other_app_rows": rejected_mismatch,
        "rows_without_explicit_app_identity": unverified_scope,
    })
    return result


__all__ = ["app_decision_read_plan","verified_issuer","project_verified_app_logs"]

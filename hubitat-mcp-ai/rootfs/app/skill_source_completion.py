"""Choose missing mandatory Hubitat diagnostic reads from scoped receipts.

A general hub log query cannot fulfil the device-scoped-log requirement.
Nothing here executes a tool or changes the Hubitat hub.
"""
from __future__ import annotations

from typing import Any
import re

from investigation_intelligence import plan_investigation
from rule_machine_analysis import historical_rule_execution_request


def _args(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("arguments") or {}
    if isinstance(args, dict) and isinstance(args.get("args"), dict):
        args = args["args"]
    return args if isinstance(args, dict) else {}


def pending_device_log_read(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    plan = plan_investigation(request)
    if not plan or plan.domain != "device_telemetry":
        return None
    matches: dict[str, str] = {}
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        state = (row.get("details") or {}).get("reportedDeviceState") or {}
        if not isinstance(state, dict):
            continue
        label = str(state.get("label") or "").strip()
        identity = str(state.get("deviceId") or "").strip()
        if label and identity and label.casefold() in str(request).casefold():
            matches[identity] = label
    # No inferred/ambiguous identity; never query logs for the wrong device.
    if len(matches) != 1:
        return None
    device_id = next(iter(matches))
    for row in receipts:
        if not isinstance(row, dict):
            continue
        leaf = str(row.get("sub_tool") or (row.get("arguments") or {}).get("tool") or _args(row).get("tool") or "")
        if leaf != "hub_get_logs":
            continue
        args = _args(row)
        if str(args.get("deviceId") or "") == device_id:
            return None  # already attempted, even if it failed
    return {"deviceId": device_id, "since": "24h", "limit": 60}


__all__ = ["pending_device_log_read"]


def pending_historical_command_read(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Require one real command-history read for an exact historic app action.

    Generic evidence obligation, not a device/app-specific patch. Resolve
    subject and lookback only from same-turn verified source receipts. Never
    interpret a switch-state event, a triggered listener, or zero app logs as
    command history. Do not duplicate a previously attempted command query.
    """
    if not historical_rule_execution_request(request):
        return None
    target = re.search(
        r"(?i)\bdevice\s*(?:id\s*)?[#:]?\s*(\d{2,7})\b",
        request,
    )
    action_match = re.search(
        r"(?i)\b(?:on|off)\s*(?:\(\s*\))?\s+commands?\b"
        r"|\bcommand[- ](on|off)\b"
        r"|\b(off|on)\s*\(\s*\)",
        request,
    )
    if not target or not action_match:
        return None
    action = (
        action_match.group(1) or action_match.group(2)
        or action_match.group(0).strip().split()[0]
    ).casefold()
    if action not in {"on", "off"}:
        return None
    device_id = target.group(1)
    verified_id = False
    verified_label = ""
    horizon: int | None = None
    for row in receipts:
        if not isinstance(row, dict):
            continue
        args = _args(row)
        operation = str(
            row.get("sub_tool") or
            (row.get("arguments") or {}).get("tool") or row.get("tool") or ""
        )
        if (
            operation == "hub_list_device_events"
            and str(args.get("deviceId") or "") == device_id
            and str(args.get("attribute") or "").casefold()
                == f"command-{action}"
        ):
            return None  # Already attempted: failed != unattempted
        if row.get("success") is not True:
            continue
        if str(args.get("deviceId") or "") == device_id and operation in {
            "hub_get_device", "hub_list_device_events",
        }:
            verified_id = True
        details = row.get("details")
        if (
            row.get("tool") == "homebrain_device_history"
            and isinstance(details, dict)
            and str(args.get("name") or "") == device_id
        ):
            verified_id = True
            label = str(details.get("label") or "").strip()
            if label:
                verified_label = label[:120]
        if (
            operation == "hub_list_device_events"
            and str(args.get("deviceId") or "") == device_id
            and str(args.get("attribute") or "").casefold() == "switch"
        ) or (
            row.get("tool") == "homebrain_device_history"
            and str(args.get("name") or "") == device_id
            and str(args.get("attribute") or "").casefold() == "switch"
        ):
            val = args.get("hoursBack", args.get("hours_back"))
            try:
                hours = int(val)
                if 1 <= hours <= 720:
                    horizon = max(horizon or 0, hours)
            except (TypeError, ValueError):
                pass
    if not (verified_id and verified_label and horizon):
        return None
    return {
        "deviceId": device_id, "label": verified_label,
        "hoursBack": horizon, "action": action,
    }


__all__.append("pending_historical_command_read")

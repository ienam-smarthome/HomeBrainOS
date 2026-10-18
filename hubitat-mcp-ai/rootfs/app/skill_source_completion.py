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
    """Plan a missing command stream from the same verified device identity.

    The local history adapter accepts a device label, whereas raw
    hub_read_devices reads use its numeric deviceId. Both are valid evidence
    for one target only when a successful read links the target and label.
    """
    if not historical_rule_execution_request(request):
        return None
    target = re.search(
        r"(?i)\bdevice\s*(?:id\s*)?[#:]?\s*(\d{2,7})\b", request,
    )
    action_match = re.search(
        r"(?i)\b(?:on|off)\s*(?:\(\s*\))?\s+commands?\b"
        r"|\bcommand[- ](on|off)\b|\b(off|on)\s*\(\s*\)",
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
    bound_labels: set[str] = set()
    lookbacks: list[int] = []
    local_histories: list[tuple[str, str, Any]] = []

    def add_lookback(value: Any) -> None:
        try:
            hours = int(value)
            if 1 <= hours <= 720:
                lookbacks.append(hours)
        except (TypeError, ValueError, OverflowError):
            pass

    for row in receipts:
        if not isinstance(row, dict):
            continue
        args = _args(row)
        wire = row.get("arguments") or {}
        operation = str(
            row.get("sub_tool")
            or (wire.get("tool") if isinstance(wire, dict) else "")
            or row.get("tool") or ""
        )
        scoped = str(args.get("deviceId") or "") == device_id
        if (
            operation == "hub_list_device_events" and scoped
            and str(args.get("attribute") or "").casefold() == f"command-{action}"
        ):
            return None  # Prior attempt, even failed, is not retried.
        if row.get("success") is not True:
            continue

        if scoped and operation in {"hub_get_device", "hub_list_device_events"}:
            verified_id = True
        if (
            scoped and operation == "hub_list_device_events"
            and str(args.get("attribute") or "").casefold() == "switch"
        ):
            add_lookback(args.get("hoursBack", args.get("hours_back")))

        # Only a verified targeted ID/label association may anchor the label.
        details = row.get("details")
        if (
            operation in {"hub_list_devices", "hub_get_device"}
            and isinstance(details, dict)
        ):
            state = details.get("reportedDeviceState")
            if isinstance(state, dict) and str(state.get("deviceId") or "") == device_id:
                verified_id = True
                label = str(state.get("label") or "").strip()
                if label and label.casefold() in request.casefold():
                    bound_labels.add(label)

        if (
            row.get("tool") == "homebrain_device_history"
            and isinstance(details, dict)
            and str(args.get("attribute") or "").casefold() == "switch"
        ):
            local_histories.append((
                str(args.get("name") or "").strip(),
                str(details.get("label") or "").strip(),
                args.get("hours_back", args.get("hoursBack")),
            ))

    if not verified_id:
        return None

    # The history adapter's name is normally a label, not a numeric ID.
    # Both the requested target and the history's returned identity must agree.
    for queried, label, hours in local_histories:
        if (
            label and label.casefold() in request.casefold()
            and (queried == device_id or queried.casefold() == label.casefold())
            and (not bound_labels or label.casefold() in {
                candidate.casefold() for candidate in bound_labels
            })
        ):
            bound_labels.add(label)
            add_lookback(hours)

    if len({label.casefold() for label in bound_labels}) != 1 or not lookbacks:
        return None
    label = next(iter(bound_labels))
    return {
        "deviceId": device_id, "label": label[:120],
        "hoursBack": max(lookbacks), "action": action,
    }


__all__.append("pending_historical_command_read")

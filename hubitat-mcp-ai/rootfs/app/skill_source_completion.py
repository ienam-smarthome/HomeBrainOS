"""Choose missing mandatory Hubitat diagnostic reads from scoped receipts.

A general hub log query cannot fulfil the device-scoped-log requirement.
Nothing here executes a tool or changes the Hubitat hub.
"""
from __future__ import annotations

from typing import Any

from investigation_intelligence import plan_investigation


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

"""One decisive app-log source obligation after verified historic command provenance.

This planner does not choose an app from its title or the model's story. It
requires an authenticated same-turn device-event command with an app producer,
a confirmed requested-device binding and an explicit local incident clock.
No MCP calls, mutation permissions, or provider calls occur here.
"""
from __future__ import annotations

from datetime import timedelta, timezone
import re
from typing import Any

from historical_command_source_contract import (
    focused_command_observation,
    requested_event_boundary,
)


def _op(row: dict[str, Any]) -> str:
    envelope = row.get("arguments")
    return str(
        row.get("sub_tool")
        or (envelope.get("tool") if isinstance(envelope, dict) else "")
        or ""
    )


def _args(row: dict[str, Any]) -> dict[str, Any]:
    envelope = row.get("arguments")
    if not isinstance(envelope, dict):
        return {}
    nested = envelope.get("args")
    return nested if isinstance(nested, dict) else envelope


def _parse(value: Any):
    if not isinstance(value, str):
        return None
    try:
        from datetime import datetime
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def pending_provenance_app_log_read(
    objective: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """One read window for a verified app-issued command, never inferred logs.

    Never retry an identical covering attempt even after a failed read.
    Historical log queries for unrelated apps or wrong windows are not
    counted as source coverage. Preserve the distinction between checking
    app logs and verifying the app's upstream cause.
    """
    if not re.search(
        r"(?i)\b(?:investigat|compare|why|cause|trigger|issuer|execution|"
        r"evidence|verify|forensic|explain)\w*\b",
        objective or "",
    ):
        return None
    boundary = requested_event_boundary(objective)
    observation = focused_command_observation(objective, receipts)
    if boundary is None or observation is None:
        return None
    device_id = str(observation["deviceId"])
    app_id = str(observation["recordedIssuerAppId"])
    # A unique command in an event window may still belong to another device.
    # Require the current turn to independently bind the requested subject
    # label to the exact history device ID, or user-supplied exact device ID.
    explicit = set(re.findall(
        r"(?i)\bdevice\s*(?:id\s*)?[#:]?\s*(\d{2,9})\b",
        objective,
    ))
    if explicit and explicit != {device_id}:
        return None
    targeted = False
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("evidence_kind") != "targeted_device_lookup":
            continue
        details = row.get("details")
        state = details.get("reportedDeviceState") if isinstance(details, dict) else None
        if not isinstance(state, dict):
            continue
        if str(state.get("deviceId") or "") != device_id:
            continue
        label = str(state.get("label") or "").strip()
        if label and re.search(
            r"(?<![\w-])" + re.escape(label) + r"(?![\w-])",
            objective, re.I,
        ):
            targeted = True
            break
    if not targeted and explicit != {device_id}:
        return None

    center = boundary.astimezone(timezone.utc)
    for row in receipts:
        if not isinstance(row, dict) or _op(row) != "hub_get_logs":
            continue
        args = _args(row)
        if str(args.get("appId") or "") != app_id:
            continue
        begin = _parse(args.get("since"))
        end = _parse(args.get("until"))
        if begin and end and begin <= center <= end:
            return None  # Once attempted, even failed, do not repeat.

    return {
        "tool": "hub_get_logs",
        "args": {
            "appId": app_id,
            "since": (center - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "until": (center + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 100,
        },
        "reason": "recorded app issuer; verified incident window",
        "deviceId": device_id,
    }


__all__ = ["pending_provenance_app_log_read"]

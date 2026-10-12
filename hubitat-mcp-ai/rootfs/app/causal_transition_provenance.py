"""Bounded independent source selection for ON and OFF causal transitions.

The closing OFF of an ON interval is a separate state transition. Observed
state changes, nearby sensor events and notified listeners cannot prove its
command producer. Build an exact focal end boundary and establish whether a
fresh command-off page is needed without widening investigation to other rooms.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from causal_command_provenance import correlate_command_producers
from causal_timeline import explicitly_focused_event_rows


def _clock(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _same(first: Any, second: Any, tolerance_ms: float = 3) -> bool:
    left, right = _clock(first), _clock(second)
    if left is None or right is None:
        return False
    try:
        return abs((left - right).total_seconds() * 1000) <= tolerance_ms
    except TypeError:
        return False


def focal_closed_transition(
    evidence: list[dict[str, Any]], original_user: str,
) -> dict[str, Any] | None:
    """Require one exactly selected, bounded interval and known device ID."""
    matched = explicitly_focused_event_rows(evidence, original_user)
    if len(matched) != 1 or not matched[0].get("end"):
        return None
    chosen = matched[0]
    subject = str(chosen.get("subject") or "")
    for receipt in evidence:
        if receipt.get("tool") != "homebrain_device_history" or not receipt.get("success"):
            continue
        details = receipt.get("details") or {}
        if str(details.get("label") or "") != subject:
            continue
        device_id = str(
            details.get("deviceId")
            or (receipt.get("arguments") or {}).get("_resolved_target", {}).get("id")
            or ""
        )
        if not device_id:
            continue
        observed_off = next((
            event for event in (
                *(details.get("boundaryEvents") or []),
                *(details.get("correlationEvents") or []),
            ) if isinstance(event, dict)
            and event.get("name") == "switch"
            and event.get("value") == "off"
            and _same(event.get("date"), chosen["end"])
        ), {})
        return {
            "subject": subject,
            "deviceId": device_id,
            "start": chosen["start"],
            "end": chosen["end"],
            "offStateEvent": observed_off,
        }
    return None


def positive_off_command_already_recorded(
    evidence: list[dict[str, Any]], focus: dict[str, Any]
) -> bool:
    """Do not re-query if compatible OFF provenance is already independently recorded."""
    return any(
        row.get("boundaryRole") == "end"
        and _same(row.get("intervalStart"), focus["start"])
        and _same(row.get("stateBoundary"), focus["end"])
        and not row.get("competingCommands")
        and isinstance(row.get("producer"), dict)
        and str((row.get("producer") or {}).get("id") or "")
        for row in correlate_command_producers(evidence)
    )


def scoped_off_history_receipt(
    evidence: list[dict[str, Any]], focus: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the actual scoped read, including an unsuccessful attempt."""
    for row in reversed(evidence):
        if row.get("sub_tool") != "hub_list_device_events":
            continue
        args = (row.get("arguments") or {}).get("args") or {}
        if (
            str(args.get("deviceId") or "") == str(focus.get("deviceId") or "")
            and args.get("attribute") == "command-off"
        ):
            return row
    return None


__all__ = [
    "focal_closed_transition",
    "positive_off_command_already_recorded",
    "scoped_off_history_receipt",
]

"""Request-local clock semantics for current state vs recent device events.

Supply the model a short, typed timing distinction from existing read receipts.
A named lastSeen field, the host receipt timestamp and a source-reported
attribute event are distinct clocks. None attests physical activity or an
unobserved attribute change.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

_EVENT_ATTRS = ("power", "switch", "amperage", "voltage", "energy")
_ALLOWED_VALUES = re.compile(r"^[A-Za-z0-9 .:+/_-]{1,40}$")
_DEVICE_ID = re.compile(r"^[1-9][0-9]{0,17}$")


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 50:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo is not None else None


def render_current_state_clock_evidence(
    receipts: list[dict[str, Any]],
) -> str | None:
    """Render only one verified target's current state and bounded event clocks.

    This packet uses no tool execution, model text, new device discovery, or
    guessed timestamps. A missing event remains unknown, even if the hub's
    status field or a source page appears fresh.
    """
    snapshots = []
    for receipt in receipts:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("evidence_kind") != "deterministic_targeted_device_resolution":
            continue
        details = receipt.get("details")
        snap = details.get("reportedDeviceState") if isinstance(details, dict) else None
        if not isinstance(snap, dict) or snap.get("source") != "verified-resolved-device-hubitat-state":
            continue
        ident = str(snap.get("deviceId") or "")
        attrs = snap.get("reportedAttributes")
        if not _DEVICE_ID.fullmatch(ident) or not isinstance(attrs, dict):
            continue
        snapshots.append((ident, attrs, snap))
    # No ambiguity about which device current-state evidence refers to.
    if len(snapshots) != 1:
        return None
    target_id, attrs, snap = snapshots[0]
    last_seen = attrs.get("lastSeen")
    if not isinstance(last_seen, str) or len(last_seen) > 64:
        last_seen = None
    # Current scalar values are from the selected resolved device, not event
    # history. Keep the output minimal and avoid arbitrary source string data.
    current = []
    for key in ("switch", "power"):
        value = attrs.get(key)
        if (isinstance(value, (int, float)) and not isinstance(value, bool)
                or isinstance(value, str) and _ALLOWED_VALUES.fullmatch(value)):
            current.append(f"{key}={value}")
    if not current and not last_seen:
        return None

    last_event: dict[str, tuple[datetime, str]] = {}
    bounded = False
    for receipt in receipts:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("evidence_kind") != "deterministic_device_event_history":
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        label = details.get("label")
        selected_label = snap.get("label")
        if (not isinstance(label, str) or not isinstance(selected_label, str)
                or label.casefold() != selected_label.casefold()):
            continue
        events = details.get("observedEvents")
        if not isinstance(events, list):
            continue
        bounded = True
        for item in events[:80]:
            if not isinstance(item, dict) or item.get("name") not in _EVENT_ATTRS:
                continue
            reporter = item.get("producedBy")
            if not isinstance(reporter, dict) or str(reporter.get("id") or "") != target_id:
                continue
            stamp = _time(item.get("date"))
            value = item.get("value")
            if not stamp or (not isinstance(value, (str, int, float))
                             or isinstance(value, bool)):
                continue
            shown = str(value)
            if not _ALLOWED_VALUES.fullmatch(shown):
                continue
            name = item["name"]
            if name not in last_event or stamp > last_event[name][0]:
                last_event[name] = (stamp, shown)
    lines = [
        "HOST CURRENT-STATE CLOCK EVIDENCE (read-only source facts, not a prose template):",
        f"- Verified resolved device ID: {target_id}; current reported "
        + (", ".join(current) or "state fields not present") + ".",
        "- Reported driver lastSeen: "
        + (last_seen if last_seen else "not available")
        + ". This is the lastSeen ATTRIBUTE, not necessarily the newest event.",
        "- Host receipt timestamp is READ/processing time, not a device check-in or attribute transition.",
    ]
    if bounded:
        for name in ("power", "switch", "amperage", "voltage"):
            if name in last_event:
                event_at, value = last_event[name]
                lines.append(
                    f"- Latest RETURNED {name} event: {event_at.isoformat()}, "
                    f"reported value={value}; device event, NOT a lastSeen update."
                )
            elif name in ("power", "switch"):
                lines.append(
                    f"- No {name} event within the bounded returned history "
                    "rows; its last actual change is NOT established."
                )
        lines.append(
            "- The event list is bounded and may omit older rows. "
            "Even an event flagged isStateChange does not independently prove "
            "a physical transition or the last change outside this page."
        )
    lines.append(
        "- Keep these clocks distinct. Do not describe the latest power/voltage/"
        "amperage event as the device's lastSeen/check-in. Current device state "
        "and source event records cannot independently establish compressor "
        "operation or physical connectivity."
    )
    return "\n".join(lines)


__all__ = ["render_current_state_clock_evidence"]

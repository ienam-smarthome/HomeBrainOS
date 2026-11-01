"""Stage 8: explicit-consent, bounded read-only LIVE device preflight.

A real Hubitat context resource may be read by the dedicated route, but this
module is a pure projection. No model inference, MCP tool dispatch, commands,
historical causality, storage or publication. Never emit full live context,
unbounded attributes, log text, tokens or network identifiers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from device_read_contract import live_context_is_complete

_SAFE_FIELDS = frozenset({
    "switch", "healthStatus", "mqttStatus", "sensorStatus",
    "power", "battery", "temperature", "thermostatOperatingState",
    "heatingSetpoint",
})
_STATUS_FIELDS = frozenset({
    "switch", "healthStatus", "mqttStatus", "sensorStatus",
    "thermostatOperatingState",
})
_MAX_DEVICES = 1000


def _safe_state(key: str, value: Any) -> str | int | float | bool | None:
    if key in _STATUS_FIELDS:
        # A state string is a report, not physical proof. Reject free-text
        # errors/messages, escaping odd whitespace/control characters.
        if type(value) is str and 0 < len(value) <= 32 and value.isprintable():
            return value
    elif key in _SAFE_FIELDS and type(value) in (int, float, bool):
        if type(value) is float and not -1e9 <= value <= 1e9:
            return None
        if type(value) is int and not -1000000000 <= value <= 1000000000:
            return None
        return value
    return None


def build_live_shadow_preflight(
    device_id: str, context: Any, *, observed_at_utc: str,
) -> dict[str, Any]:
    """Only read evidence for a specifically selected numeric device ID."""
    if type(device_id) is not str or not device_id.isascii() or not device_id.isdecimal() or not 1 <= len(device_id) <= 12:
        raise ValueError("invalid target device id")
    if type(observed_at_utc) is not str or len(observed_at_utc) > 40:
        raise ValueError("invalid observation time")
    baseline = {
        "schema": "homebrain-live-shadow-preflight.v1",
        "mode": "explicit_read_only_live_context",
        "target_device_id": device_id,
        "observed_at_utc": observed_at_utc,
        "ready_for_causal_attribution": False,
        "device_control_enabled": False,
        "cloud_requests": 0,
        "publisher_approval": False,
        "persistent_capture": False,
        "timestamp_provenance": "collector_preflight_time_only",
        "live_context_complete": False,
        "device_reported_states": {},
        "evidence_limitations": [
            "Live context states are hub reports, not authenticated device-origin packets.",
            "MQTT broker/driver connectivity alone never proves physical device connectivity.",
            "Current state does not establish event history, command execution or unique cause.",
            "No physical event time or complete historical absence is independently proven.",
        ],
    }
    if (not live_context_is_complete(context)
            or len(context.get("devices", [])) > _MAX_DEVICES):
        return {**baseline, "status": "blocked_incomplete_context",
                "ready_for_read_only_investigation": False,
                "reason": "Hub context is partial, truncated or not proven complete."}
    baseline["live_context_complete"] = True
    matches = [
        item for item in context["devices"]
        if type(item.get("id")) in (str, int)
        and str(item["id"]) == device_id
    ]
    if len(matches) != 1:
        return {**baseline,
                "status": "blocked_target_ambiguous" if matches else "target_not_found",
                "ready_for_read_only_investigation": False,
                "reason": "Target must match exactly one device in the complete context."}
    matched = matches[0]
    states = matched.get("attributes")
    if type(states) is not dict:
        return {**baseline, "status": "blocked_missing_state_projection",
                "ready_for_read_only_investigation": False,
                "reason": "Target has no usable state projection."}
    result_states: dict[str, Any] = {}
    for field in sorted(_SAFE_FIELDS):
        if field in states:
            safe = _safe_state(field, states[field])
            if safe is not None:
                result_states[field] = safe
    # Never surface untrusted room labels, device names, MACs, IPs, log
    # messages or raw error fields in this portable preflight response.
    baseline["device_reported_states"] = result_states
    baseline["reported_field_count"] = len(result_states)
    baseline["ready_for_read_only_investigation"] = bool(result_states)
    baseline["status"] = ("ready_for_read_only_followup" if result_states
                          else "blocked_no_bounded_reported_states")
    baseline["reason"] = (
        "One device matched. Scoped current-state reports are available; "
        "additional authenticated history is needed for causal investigation."
        if result_states else
        "Target was identified but no allowlisted current-state reports were present."
    )
    return baseline


__all__ = ["build_live_shadow_preflight"]

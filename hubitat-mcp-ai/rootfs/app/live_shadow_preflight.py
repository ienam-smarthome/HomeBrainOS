"""Stage 8: explicit-consent, bounded read-only LIVE device preflight.

A real Hubitat context resource may be read by the dedicated route, but this
module is a pure projection. No model inference, MCP tool dispatch, commands,
historical causality, storage or publication. Never emit full live context,
unbounded attributes, log text, tokens or network identifiers.
"""
from __future__ import annotations

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
# Never echo arbitrary upstream status strings: drivers may put log text,
# secrets, IP addresses or unescaped HTML in otherwise conventional fields.
_STATUS_VALUES = frozenset({
    "on", "off", "online", "offline", "unknown", "stale",
    "healthy", "unhealthy", "connected", "connecting",
    "disconnected", "active", "inactive", "idle",
    "heating", "cooling", "pending", "error", "warning",
    "ok", "open", "closed", "present", "not_present",
})


def _safe_state(key: str, value: Any) -> str | int | float | bool | None:
    if key in _STATUS_FIELDS:
        # A state string is a report, not physical proof. Reject free-text
        # errors/messages, escaping odd whitespace/control characters.
        if type(value) is str and value.casefold().strip() in _STATUS_VALUES:
            return value.casefold().strip()
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
    # Do not collapse completely different failure modes into one message.
    # Metadata is checked as *data*, never copied back to the browser.
    devices = context.get("devices") if type(context) is dict else None
    has_devices = (type(devices) is list
                   and all(type(item) is dict for item in devices)
                   and len(devices) <= _MAX_DEVICES)
    identity_marker = (context.get("idsComplete") if type(context) is dict
                       else None)
    raw_total = (context.get("totalDevices") if type(context) is dict else None)
    known_total = None
    if type(raw_total) is int and 0 <= raw_total <= _MAX_DEVICES:
        known_total = raw_total
    elif (type(raw_total) is str and raw_total.isascii()
          and raw_total.isdecimal() and len(raw_total) <= 6
          and int(raw_total) <= _MAX_DEVICES):
        known_total = int(raw_total)
    count_matches = (has_devices and known_total is not None
                     and known_total == len(devices))
    explicit_incomplete = (
        type(context) is dict and (
            context.get("truncated") is True
            or context.get("partial") is True
            or identity_marker is False
        )
    )
    baseline["context_diagnostics"] = {
        "device_array_well_formed_and_bounded": bool(has_devices),
        "identity_marker": ("complete" if identity_marker is True
                            else "incomplete" if identity_marker is False
                            else "missing_or_unrecognised"),
        "total_marker": ("matching" if count_matches
                         else "conflicting" if known_total is not None
                              else "missing_or_unrecognised"),
        "explicit_partial_or_truncated": bool(explicit_incomplete),
        "returned_device_count": len(devices) if has_devices else None,
    }
    baseline["ready_for_device_scoped_observation"] = False
    if not has_devices:
        return {**baseline, "status": "blocked_context_shape",
                "ready_for_read_only_investigation": False,
                "reason": "Hub context has no bounded device array; inspect resource coverage."}
    if explicit_incomplete:
        return {**baseline, "status": "blocked_explicit_partial_context",
                "ready_for_read_only_investigation": False,
                "reason": "Hub explicitly reports truncated/partial identity coverage."}
    if known_total is not None and not count_matches:
        return {**baseline, "status": "blocked_total_mismatch",
                "ready_for_read_only_investigation": False,
                "reason": "Device count does not match the source-reported total."}
    # Missing identity/total metadata DOES NOT establish completeness.
    # It also does not invalidate a specific observed record: if the
    # requested ID is present exactly once in the *returned subset*, its
    # allowlisted reported values may be displayed as PROVISIONAL, with no
    # global absence assertion or certification to proceed with a causal read.
    fully_verified = (live_context_is_complete(context)
                      and identity_marker is True and count_matches)
    baseline["live_context_complete"] = bool(fully_verified)
    matches = [
        item for item in devices
        if type(item.get("id")) in (str, int)
        and str(item["id"]) == device_id
    ]
    if len(matches) != 1:
        return {**baseline,
                "status": ("blocked_target_ambiguous" if matches else
                           "target_not_found" if fully_verified
                           else "target_not_seen_in_unverified_context"),
                "ready_for_read_only_investigation": False,
                "reason": ("Multiple matching records were returned; no unique target."
                           if matches else
                           "Target was not seen; without complete inventory this "
                           "does not establish that the device is absent."
                           if not fully_verified else
                           "Target not found in the explicitly complete hub context.")}
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
    baseline["ready_for_device_scoped_observation"] = bool(result_states)
    baseline["ready_for_read_only_investigation"] = bool(
        result_states and fully_verified
    )
    baseline["status"] = (
        ("ready_for_read_only_followup" if fully_verified
         else "scoped_reports_unverified_inventory")
        if result_states else "blocked_no_bounded_reported_states"
    )
    baseline["reason"] = (
        "Only provisional, target-scoped hub reports are available: the "
        "resource did not provide enough explicit completeness metadata. "
        "Do not infer missing devices, missing history or causal outcomes."
        if result_states and not fully_verified else
        "One device matched in a complete context. Historical causation, "
        "clock accuracy and physical actuation still require further proof."
        if result_states else
        "Target returned no allowlisted state reports; this is not physical OFF proof."
    )
    return baseline



def build_verified_detail_shadow(
    device_id: str, devices: Any, provenance: Any, *, observed_at_utc: str,
) -> dict[str, Any]:
    """Project ONE target from a verified, freshly paginated detailed manifest.

    The caller must obtain the manifest via the existing read-only
    get_audit_devices(identity_only=False) pathway. Nothing in this function
    makes a Hubitat command, fetches extra history, or publishes source text.
    """
    if (type(device_id) is not str or not device_id.isascii()
            or not device_id.isdecimal() or not 1 <= len(device_id) <= 12):
        raise ValueError("invalid target device id")
    if type(observed_at_utc) is not str or len(observed_at_utc) > 40:
        raise ValueError("invalid observation time")
    base = {
        "schema": "homebrain-live-shadow-detailed.v1",
        "target_device_id": device_id,
        "observed_at_utc": observed_at_utc,
        "read_only": True,
        "cloud_requests": 0,
        "device_commands": 0,
        "publisher_approval": False,
        "persistent_capture": False,
        "historical_causation_verified": False,
        "device_origin_packet_verified": False,
        "ready_for_historical_investigation": False,
        "reported_states": {},
        "verified_inventory_coverage": False,
        "data_scope": "single_target_projection_from_paginated_detailed_manifest",
        "limitations": [
            "This is a fresh detailed hub-report snapshot, not a device-origin packet.",
            "No past command execution, physical connectivity, clock accuracy, or causal relationship is proven.",
            "No complete event history was examined; absence of a field is not proof of an absent event.",
        ],
    }
    if (type(provenance) is not dict
            or provenance.get("complete") is not True
            or provenance.get("source") != "fresh_projected_gateway"
            or provenance.get("projection") != "full"):
        return {**base, "status": "blocked_unverified_detailed_inventory",
                "reason": "Fresh detailed inventory could not be independently verified."}
    if (type(devices) is not list or not 1 <= len(devices) <= _MAX_DEVICES
            or not all(type(item) is dict for item in devices)):
        return {**base, "status": "blocked_malformed_detailed_inventory",
                "reason": "Detailed inventory shape is incomplete or oversized."}
    ids = [str(item.get("id") or item.get("deviceId") or "") for item in devices]
    if (any(not name or not name.isascii() or not name.isdecimal() for name in ids)
            or len(set(ids)) != len(ids)):
        return {**base, "status": "blocked_ambiguous_detailed_inventory",
                "reason": "Detailed inventory lacks unique numeric identities."}
    if provenance.get("devices") != len(devices):
        return {**base, "status": "blocked_detailed_count_conflict",
                "reason": "Detailed source coverage does not match the returned inventory."}
    base["verified_inventory_coverage"] = True
    matches = [item for item, identifier in zip(devices, ids) if identifier == device_id]
    if len(matches) != 1:
        return {**base, "status": "target_not_in_verified_detailed_inventory",
                "reason": "Target device is not in the verified detailed snapshot."}
    target = matches[0]

    # Both structured detailed attribute lists and summary dictionaries can
    # be reported by drivers. Only accept a simple, allowlisted value from a
    # unique occurrence; conflicting duplicate fields are not promoted.
    projected: dict[str, Any] = {}
    conflicts: set[str] = set()
    raw_containers = [target.get("attributes"), target.get("currentStates")]
    for container in raw_containers:
        pairs = []
        if type(container) is dict:
            pairs = list(container.items())
        elif type(container) is list and len(container) <= 256:
            for row in container:
                if type(row) is not dict:
                    continue
                key = row.get("name")
                if key is None:
                    key = row.get("attribute")
                if "currentValue" in row:
                    value = row["currentValue"]
                else:
                    value = row.get("value")
                pairs.append((key, value))
        for key, value in pairs:
            if type(key) is not str or key not in _SAFE_FIELDS:
                continue
            cleaned = _safe_state(key, value)
            if cleaned is None:
                continue
            if key in projected and projected[key] != cleaned:
                conflicts.add(key)
            else:
                projected[key] = cleaned
    for key in conflicts:
        projected.pop(key, None)
    base["reported_states"] = dict(sorted(projected.items()))
    base["status"] = ("verified_identity_with_reported_states" if projected
                      else "verified_identity_no_allowlisted_state")
    base["reason"] = (
        "Detailed source identity coverage was verified. The selected device "
        "has bounded current hub-reported attributes. Further independently "
        "sourced history is required for causal investigation."
        if projected else
        "Device identity was verified but no suitable allowlisted state fields "
        "were present. This does not prove the device is physically offline."
    )
    return base


__all__ = ["build_live_shadow_preflight", "build_verified_detail_shadow"]

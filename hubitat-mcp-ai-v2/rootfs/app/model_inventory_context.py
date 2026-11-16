"""Compact model-facing read-only inventory INDEX for causal investigations.

Original native MCP data remain unchanged in PRIVATE receipts. This is not
device selection, history evidence, a source filter or an authorization.
Every valid identity is retained so the model can choose focused follow-up.
"""
from __future__ import annotations

import json
from typing import Any

_MAX_DEVICES = 700
_MAX_LABEL = 110
_MAX_ROOM = 70
_MAX_STATE_FIELDS = 7
_STATE_NAMES = ("switch", "motion", "thermostatOperatingState",
                "temperature", "heatingSetpoint", "power", "battery")


def compact_inventory_context(source: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(source, dict):
        return None
    content = source.get("content")
    if not isinstance(content, list):
        return None
    text_parts = [v.get("text") for v in content
                  if isinstance(v, dict) and v.get("type") == "text"
                  and isinstance(v.get("text"), str)]
    if len(text_parts) != 1:
        return None
    try:
        native = json.loads(text_parts[0])
    except (TypeError, ValueError):
        return None
    if not isinstance(native, dict) or not isinstance(native.get("devices"), list):
        return None
    devices = native["devices"]
    if len(devices) < 20 or len(devices) > _MAX_DEVICES:
        return None
    # Fail closed on unexpected partial/malformed identities: we must not
    # silently make a device unfindable by omitting it from a claimed index.
    index = []
    for device in devices:
        if not isinstance(device, dict):
            return None
        device_id = device.get("id")
        label = device.get("label")
        if not isinstance(device_id, (str, int)) or isinstance(device_id, bool):
            return None
        if not isinstance(label, str) or not label or len(label) > _MAX_LABEL:
            return None
        room = device.get("room")
        if room is not None and (not isinstance(room, str)
                                 or len(room) > _MAX_ROOM):
            room = None
        row = {"id": str(device_id), "label": label, "room": room}
        states = device.get("currentStates")
        if isinstance(states, dict):
            subset = {
                k: states[k] for k in _STATE_NAMES[:_MAX_STATE_FIELDS]
                if k in states and isinstance(states[k], (str, int, float))
                and not isinstance(states[k], bool)
                and len(str(states[k])) <= 30
            }
            if subset:
                row["sampled_current_states"] = subset
        index.append(row)
    # Do not compact small inventories or claim completeness when the
    # native count conflicts with returned device rows.
    reported_count = native.get("count")
    if isinstance(reported_count, int) and reported_count != len(devices):
        return None
    return {
        "client_inventory_navigation": {
            "source": "original current-request native hub_list_devices",
            "returned_device_identities": len(index),
            "reported_total": native.get("total"),
            "all_returned_ids_labels_rooms_kept": True,
            "current_states_are_snapshots_not_history": True,
            "omitted_details_require_model_selected_read": True,
            "not_an_event_history_or_controller_execution_log": True,
            "note": "Identity/navigation view; the original full native source is retained in PRIVATE Technical JSON. Select only proportionate follow-up sources.",
            "devices": index,
        }
    }

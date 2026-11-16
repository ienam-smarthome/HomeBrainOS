"""Validate both supported native device-history response envelopes.

Current upstream Hubitat may return {"device": label, "events": [...],
"count": n} without explicitly echoing source/deviceId. The executed,
successful original current-request tool arguments then bind its identity.
Older envelopes with source="device"/deviceId are also accepted, but a
conflicting ID or explicit non-device source is always rejected.

This is NOT device selection, an evidence inference or a native call.
"""
from __future__ import annotations

from investigation_source_ledger import _response, _SAFE_ID


def _ident(value: object) -> str | None:
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        return None
    return value


def original_device_event_history(
    receipt: dict,
) -> tuple[str, str, list[dict]] | None:
    """Return validated (requested device ID, display label, original events).

    Never infer identity from a label or an app ID, nor accept a source that
    contradicts the original request. No mutation of native receipts.
    """
    if (not isinstance(receipt, dict)
            or receipt.get("success") is not True
            or receipt.get("name") != "hub_list_device_events"):
        return None
    args = receipt.get("arguments")
    if not isinstance(args, dict):
        return None
    requested_id = _ident(args.get("deviceId"))
    if requested_id is None:
        return None
    _, native = _response(receipt)
    if not isinstance(native, dict) or native.get("source") not in (None, "device"):
        return None
    returned_id = native.get("deviceId")
    if returned_id is not None and _ident(returned_id) != requested_id:
        return None
    events = native.get("events")
    if not isinstance(events, list):
        return None
    label = native.get("device")
    label = label.strip() if isinstance(label, str) else ""
    # If source/device ID are omitted, require an upstream device-history
    # label rather than accepting an arbitrary event-bearing object.
    if native.get("source") is None and returned_id is None and not label:
        return None
    return requested_id, label or f"Device {requested_id}", events

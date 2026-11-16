"""Bounded original command provenance for conservative source-only answers.

Only executed-successful, identity-bound native device-history reads qualify.
A command producer app ID is a recorded issuer, NEVER proof of its internal
trigger, of command delivery, or of physical state. Listener metadata is not an
issuer. This module performs no extra read, write, model call or routing.
"""
from __future__ import annotations

from datetime import datetime
import re

from native_device_event_receipt import original_device_event_history

_COMMAND = re.compile(r"command-[A-Za-z][A-Za-z0-9]{0,39}\Z")
_APP_ID = re.compile(r"[0-9]{1,9}\Z")
_LABEL = re.compile(r"[^\w\s().,\-\u00b0%/]+", re.UNICODE)
_MAX_RECEIPTS = 40
_MAX_EVENTS = 300
_MAX_ROWS = 6
_MAX_DEVICES = 3
_MAX_KINDS_PER_DEVICE = 4


def _stamp(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return instant if instant.tzinfo is not None and instant.utcoffset() is not None else None
    except ValueError:
        return None


def _label(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    clean = _LABEL.sub("", value.strip().replace("\n", " "))
    return clean[:60] or fallback


def original_command_rows(receipts: list[dict]) -> tuple[list[dict], bool]:
    """Return selected source-bound command records and whether any page hit limit.

    The newest event per distinct command name is retained per requested device,
    so repeated dimming/setpoint calls cannot hide a recorded ON or OFF command.
    This selection does NOT infer which device is the requested focal output.
    Malformed, mismatched, non-device and failed receipts are ignored.
    """
    newest: dict[tuple[str, str], dict] = {}
    capped = False
    for receipt in receipts[:_MAX_RECEIPTS]:
        valid = original_device_event_history(receipt)
        if valid is None:
            continue
        device_id, native_label, events = valid
        label = _label(native_label, "Device " + device_id)
        args = receipt.get("arguments")
        limit = args.get("limit") if isinstance(args, dict) else None
        if type(limit) is int and 0 < limit <= 10000 and len(events) >= limit:
            capped = True
        for event in events[:_MAX_EVENTS]:
            if not isinstance(event, dict):
                continue
            kind = event.get("name")
            if (not isinstance(kind, str) or _COMMAND.fullmatch(kind) is None
                    or event.get("type") not in (None, "command")):
                continue
            stamp = _stamp(event.get("date"))
            if stamp is None:
                continue
            producer = event.get("producedBy")
            producer = producer if isinstance(producer, dict) else {}
            app_id = producer.get("appId")
            if type(app_id) is int:
                app_id = str(app_id)
            if not isinstance(app_id, str) or _APP_ID.fullmatch(app_id) is None:
                app_id = None
            entry = {
                "device_id": device_id,
                "device_label": label,
                "command_name": kind,
                "timestamp": stamp,
                "issuer_app_id": app_id,
                "issuer_label": (
                    _label(producer.get("name"), "Unnamed app")
                    if app_id is not None else None
                ),
            }
            key = (device_id, kind)
            prior = newest.get(key)
            if prior is None or stamp > prior["timestamp"]:
                newest[key] = entry
            elif stamp == prior["timestamp"] and (
                prior["issuer_app_id"] != app_id
                or prior["issuer_label"] != entry["issuer_label"]
            ):
                # Two source rows with same target/name/time but conflicting
                # issuer metadata do not establish a unique issuer.
                prior["issuer_app_id"] = None
                prior["issuer_label"] = None

    chosen: list[dict] = []
    devices: set[str] = set()
    per_device: dict[str, int] = {}
    for item in sorted(newest.values(), key=lambda row: row["timestamp"], reverse=True):
        device = item["device_id"]
        if device not in devices and len(devices) >= _MAX_DEVICES:
            continue
        if per_device.get(device, 0) >= _MAX_KINDS_PER_DEVICE:
            continue
        chosen.append(item)
        devices.add(device)
        per_device[device] = per_device.get(device, 0) + 1
        if len(chosen) >= _MAX_ROWS:
            break
    return chosen, capped

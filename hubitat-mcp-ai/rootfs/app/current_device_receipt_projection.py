"""Privacy-bounded, host-attested current readings from one verified device.

A read receipt's collection time is not a source event or attribute-change
time. This projection is diagnostic only; it never grants live control,
physical status, fresh telemetry, or causation.
"""
from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any, Mapping

SCALAR_ATTRS = frozenset({
    "switch", "power", "amperage", "voltage", "energy", "temperature",
    "humidity", "battery", "level", "illuminance", "dataAgeSeconds",
    "telePeriod", "healthStatus", "deviceHealth", "mqttStatus",
    "sensorStatus", "lastSeen", "lastActivity",
})
_NUMERIC = frozenset({
    "power", "amperage", "voltage", "energy", "temperature", "humidity",
    "battery", "level", "illuminance", "dataAgeSeconds", "telePeriod",
})
_ENUM = {
    "switch": frozenset(("on", "off")),
    "healthStatus": frozenset(("online", "offline", "unknown")),
    "deviceHealth": frozenset(("ok", "online", "offline", "unknown", "failed")),
    "mqttStatus": frozenset(("connected", "disconnected", "connecting", "unknown")),
    "sensorStatus": frozenset(("online", "offline", "unknown")),
}
_TIMESTAMP = frozenset(("lastSeen", "lastActivity"))
_ID = re.compile(r"^[1-9]\d{0,17}$")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")


def _value(name: str, raw: Any) -> str | int | float | None:
    if isinstance(raw, dict):
        raw = raw.get("currentValue", raw.get("value"))
    if name in _NUMERIC:
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return raw if math.isfinite(float(raw)) else None
        if isinstance(raw, str) and len(raw) <= 30 and _NUMBER.fullmatch(raw.strip()):
            try:
                val = float(raw)
                return val if math.isfinite(val) else None
            except ValueError:
                pass
        return None
    if name in _ENUM:
        if isinstance(raw, str) and raw.casefold().strip() in _ENUM[name]:
            return raw.casefold().strip()
        return None
    if name in _TIMESTAMP:
        if not isinstance(raw, str) or len(raw) > 64:
            return None
        try:
            datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            # Tasmota drivers may use ordinary "Mon Nov 02 ... GMT 2026".
            # Preserve only short, deliberately constrained date/time forms.
            if not re.fullmatch(
                r"[A-Za-z]{3} [A-Za-z]{3} \d{2} \d{2}:\d{2}:\d{2} "
                r"(?:GMT|UTC|BST) \d{4}", raw.strip()
            ):
                return None
        return raw.strip()
    return None


def _reported_attributes(device: Mapping[str, Any]) -> dict[str, str | int | float]:
    result: dict[str, str | int | float] = {}
    # A detailed-list attributes projection can be a map or typed list.
    raw = device.get("attributes")
    if isinstance(raw, dict):
        for key, val in raw.items():
            if key in SCALAR_ATTRS:
                safe = _value(key, val)
                if safe is not None:
                    result[key] = safe
    elif isinstance(raw, list):
        for item in raw[:120]:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("attribute")
            if name not in SCALAR_ATTRS:
                continue
            safe = _value(name, item.get("currentValue", item.get("value")))
            if safe is not None:
                result[name] = safe
    # Compact currentStates take precedence over detailed capability metadata,
    # as in the canonical device_attributes helper.
    live = device.get("currentStates")
    if isinstance(live, dict):
        for key, val in live.items():
            if key in SCALAR_ATTRS:
                safe = _value(key, val)
                if safe is not None:
                    result[key] = safe
    for key in SCALAR_ATTRS:
        if key in device and key not in result:
            safe = _value(key, device[key])
            if safe is not None:
                result[key] = safe
    return result


def resolved_device_snapshot(data: Any) -> dict[str, Any] | None:
    """Keep only an exact named/ID read's selected target, not fuzzy cache data."""
    if not isinstance(data, dict) or data.get("matched") is not True:
        return None
    if data.get("requestCacheHit") is True:
        return None
    attempts = data.get("attempts")
    if (not isinstance(attempts, list) or len(attempts) != 1
            or not isinstance(attempts[0], dict)
            or attempts[0].get("source") not in ("label_filter", "device_id_direct")):
        return None
    raw = data.get("target")
    if not isinstance(raw, dict):
        return None
    ident = str(raw.get("id") or raw.get("deviceId") or "")
    published_id = str(data.get("deviceId") or "")
    if not _ID.fullmatch(ident) or ident != published_id:
        return None
    label = raw.get("label") or raw.get("name")
    if not isinstance(label, str) or not label.strip() or len(label) > 100:
        return None
    attrs = _reported_attributes(raw)
    if not attrs:
        return None
    return {
        "deviceId": ident,
        "label": label.strip(),
        "reportedAttributes": attrs,
        "source": "verified-resolved-device-hubitat-state",
        "attributeChangeTimesVerified": False,
        "readReceiptTimeIsAttributeEventTime": False,
        "physicalConnectivityVerified": False,
    }


__all__ = ["resolved_device_snapshot"]

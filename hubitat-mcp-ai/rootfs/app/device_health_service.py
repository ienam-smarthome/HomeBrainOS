from __future__ import annotations

from typing import Any


_OFFLINE_TERMS = {"offline", "unavailable", "not responding", "failed"}
_STALE_TERMS = {"stale", "inactive", "not seen"}


def classify_device_health(devices: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Classify Hubitat devices into health groups without LLM interpretation.

    Explicit health failures are kept separate from stale activity. Missing
    activity alone is never treated as proof of an offline device.
    """
    result = {
        "offline_devices": [],
        "stale_devices": [],
        "warnings": [],
    }

    for device in devices:
        if not isinstance(device, dict):
            continue
        label = str(device.get("label") or device.get("name") or device.get("id") or "Unknown")
        text = " ".join(str(value) for value in device.values()).casefold()

        item = {"name": label, "source": "hub_read_devices"}
        if any(term in text for term in _OFFLINE_TERMS):
            item["status"] = "offline"
            result["offline_devices"].append(item)
        elif any(term in text for term in _STALE_TERMS):
            item["status"] = "stale"
            result["stale_devices"].append(item)

        battery = device.get("battery")
        try:
            if battery is not None and float(battery) <= 20:
                result["warnings"].append({
                    "name": label,
                    "status": "low_battery",
                    "battery": battery,
                    "source": "hub_read_devices",
                })
        except (TypeError, ValueError):
            pass

    return result


__all__ = ["classify_device_health"]

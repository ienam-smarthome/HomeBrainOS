from __future__ import annotations

import re
from typing import Any

from fast_fallback_live import _looks_like_light, live_attributes


def _normalise(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()),
    ).strip()


def _capability_text(item: dict[str, Any]) -> str:
    value = item.get("capabilities")
    names: list[str] = []
    if isinstance(value, dict):
        entries = list(value.values()) + list(value.keys())
    elif isinstance(value, list):
        entries = value
    elif value in (None, ""):
        entries = []
    else:
        entries = [value]

    for entry in entries:
        if isinstance(entry, dict):
            current = (
                entry.get("displayName")
                or entry.get("name")
                or entry.get("label")
                or entry.get("id")
            )
        else:
            current = entry
        if current not in (None, ""):
            names.append(str(current))
    return " ".join(names)


def device_icon(
    item: dict[str, Any],
    attrs: dict[str, Any] | None = None,
) -> str:
    """Return a stable, recognisable icon from live state and device metadata.

    Dedicated child sensors such as ``FP300 battery`` and ``FP300 Lux`` are
    detected before their parent device's broader presence/motion metadata. This
    prevents every multi-sensor child from inheriting the same generic icon.
    """
    attrs = attrs if isinstance(attrs, dict) else live_attributes(item)
    keys = {_normalise(key).replace(" ", "") for key in attrs}
    label_text = _normalise(
        " ".join(
            str(item.get(key) or "")
            for key in ("label", "name", "displayName")
        )
    )
    text = _normalise(
        " ".join(
            [
                str(item.get(key) or "")
                for key in (
                    "label",
                    "name",
                    "displayName",
                    "type",
                    "deviceType",
                    "category",
                    "driverName",
                )
            ]
            + [_capability_text(item), " ".join(map(str, attrs.keys()))]
        )
    )
    words = set(text.split())
    label_words = set(label_text.split())

    if any(term in text for term in ("hub info", "hubitat hub", "c8 pro", "c 8 pro")):
        return "🧠"
    if "weather" in words or "forecast" in words:
        return "🌦️"
    if any(
        term in words
        for term in ("prayer", "pray", "fajr", "dhuhr", "maghrib", "isha")
    ):
        return "🕌"

    # Prefer the explicitly named child/sensor function over parent metadata.
    if "battery" in label_words or ("battery" in keys and len(keys) <= 3):
        return "🔋"
    if (
        "lux" in label_words
        or "illuminance" in label_words
        or "illuminance" in keys
        or "light sensor" in label_text
    ):
        return "☀️"
    if "humidity" in label_words or (
        "humidity" in keys and "temperature" not in keys
    ):
        return "💧"
    if "temperature" in label_words or (
        "temperature" in keys
        and not ({"power", "energy"} & keys)
        and "humidity" not in keys
    ):
        return "🌡️"

    if _looks_like_light(item):
        return "💡"
    if "camera" in words or "cam" in words or any(
        word.endswith("cam") for word in words
    ):
        return "📷"
    if "thermostat" in text or " trv " in f" {text} " or {
        "thermostatmode",
        "thermostatoperatingstate",
        "heatingsetpoint",
        "coolingsetpoint",
    } & keys:
        return "♨️"
    if "motion" in words or "motion" in keys:
        return "🏃"
    if "presence" in words or "occupancy" in words or "presence" in keys:
        return "📍"
    if "contact" in words or "contact" in keys or any(
        word in words for word in ("door", "window")
    ):
        return "🚪"
    if "lock" in words or "lock" in keys:
        return "🔒"
    if any(word in words for word in ("smoke", "siren", "alarm")) or {
        "smoke",
        "carbonmonoxide",
        "alarm",
    } & keys:
        return "🚨"
    if any(word in words for word in ("water", "leak", "moisture")) or {
        "water",
        "moisture",
    } & keys:
        return "💦"
    if "fan" in words or "fanspeed" in keys or "speed" in keys:
        return "🌀"
    if "valve" in words or "valve" in keys:
        return "🚰"
    if "button" in words or {
        "pushed",
        "held",
        "doubletapped",
        "numberofbuttons",
    } & keys:
        return "🔘"
    if any(word in label_words for word in ("socket", "outlet", "plug")):
        return "🔌"
    if {"power", "energy"} & keys or any(
        word in label_words for word in ("power", "energy")
    ):
        return "⚡"
    if "temperature" in keys:
        return "🌡️"
    if "humidity" in keys:
        return "💧"
    if "switch" in keys or "switch" in words:
        return "🎚️"
    if "battery" in keys:
        return "🔋"
    return "📟"


__all__ = ["device_icon"]

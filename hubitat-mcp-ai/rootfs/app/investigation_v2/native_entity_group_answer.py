"""Generic, independently grounded multi-entity state answer for Native V2.

The model chooses names and READ tools. The host joins a bounded verified
candidate group to exact scoped device receipts; it does not route on words,
infer room membership or treat stored level as active brightness.
"""
from __future__ import annotations
import math
from collections.abc import Mapping, Sequence
from typing import Any
from .native_source_adapters import safe_string

_BINARY = {
    "switch": {"on", "off"}, "motion": {"active", "inactive"},
    "presence": {"present", "not present"}, "contact": {"open", "closed"},
    "lock": {"locked", "unlocked"}, "healthStatus": {"online", "offline", "unknown", "stale"},
    "networkStatus": {"online", "offline", "unknown", "stale"},
    "deviceHealth": {"online", "offline", "unknown", "stale"},
}
_NUMERIC = {
    "level": (0, 100, "%"), "battery": (0, 100, "%"),
    "humidity": (0, 100, "%"), "temperature": (-100, 250, "°C"),
    "power": (-1000000, 1000000, " W"),
    "illuminance": (0, 1000000, " lx"),
    "heatingSetpoint": (-100, 250, "°C"),
    "coolingSetpoint": (-100, 250, "°C"),
}
_DISPLAY = ("switch", "motion", "presence", "contact", "lock",
            "temperature", "humidity", "battery", "power", "illuminance",
            "healthStatus", "networkStatus", "deviceHealth",
            "heatingSetpoint", "coolingSetpoint")

def _id(x: Any) -> str:
    if type(x) not in (int, str):
        return ""
    value = str(x)
    return value if value.isdecimal() and len(value) <= 20 else ""

def _attributes(data: Mapping[str, Any]) -> dict[str, str]:
    attrs = data.get("attributes")
    if not isinstance(attrs, list):
        return {}
    output = {}
    for row in attrs[:80]:
        if not isinstance(row, Mapping):
            continue
        key, val = row.get("name"), row.get("value")
        if not isinstance(key, str) or key in output:
            continue
        if key in _BINARY and isinstance(val, str):
            value = val.strip().casefold()
            if value in _BINARY[key]:
                output[key] = value
        elif key in _NUMERIC and type(val) in (int, float):
            low, high, unit = _NUMERIC[key]
            if math.isfinite(float(val)) and low <= val <= high:
                output[key] = (str(int(val)) if val == int(val)
                               else str(round(val, 2))) + unit
    return output

def entity_group_answer(
    lookups: Sequence[Mapping[str, Any]],
    witnesses: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Only a complete same-ID READ set may produce a complete group answer."""
    groups = [row for row in lookups if isinstance(row, Mapping)
              and row.get("status") == "candidate_group"]
    if not groups:
        return None
    lookup = groups[-1]
    ids_raw = lookup.get("candidate_ids")
    if not isinstance(ids_raw, list):
        return None
    ids = [_id(x) for x in ids_raw]
    if (not 2 <= len(ids) <= 8 or any(not ident for ident in ids)
            or len(set(ids)) != len(ids)):
        return None
    group_label = safe_string(lookup.get("query"), 85)
    if not group_label:
        return None
    observations = {}
    for w in witnesses:
        if not isinstance(w, Mapping) or w.get("operation") != "hub_get_device":
            continue
        filters, data, read = w.get("read_filters"), w.get("source_data"), w.get("read")
        if (not isinstance(filters, Mapping) or not isinstance(data, Mapping)
                or type(read) is not int):
            continue
        ident = _id(filters.get("deviceId"))
        if (ident not in ids or _id(data.get("id")) != ident
                or ident in observations):
            continue
        label = data.get("label") or data.get("name")
        if not isinstance(label, str) or not label.strip():
            continue
        caps = data.get("capabilities")
        caps = ({s for s in caps[:80] if isinstance(s, str) and len(s) <= 64}
                if isinstance(caps, list) else set())
        observations[ident] = {
            "name": safe_string(label, 90), "read": read,
            "light": "Light" in caps, "values": _attributes(data),
        }
    if set(observations) != set(ids):
        return None
    lights = [ident for ident in ids if observations[ident]["light"]]
    others = [ident for ident in ids if ident not in lights]
    lines = [f"**{len(ids)} devices matching “{group_label}” were individually read.**"]
    if lights:
        lines.append(f"**{len(lights)} device(s) advertise the Light capability:**")
    for ident in lights + others:
        item = observations[ident]
        values = item["values"]
        properties = [f"{key}={values[key]}" for key in _DISPLAY
                      if key in values][:3]
        if item["light"] and "level" in values:
            properties.append("last reported level=" + values["level"])
        detail = ", ".join(properties) if properties else (
            "no recognised state in this source read")
        lines.append(f"- **{item['name']}** (device {ident}): "
                     f"{detail}. (Read #{item['read']})")
    if not lights:
        lines.append("No returned device advertises the Light capability.")
    lines.append(
        "**Limits:** Names are candidate matches, not verified room "
        "membership. The returned attributes are snapshots, not independent "
        "physical confirmation. An OFF light's stored level is not its "
        "current emitted brightness; devices absent from the name match "
        "require a separate room inventory.")
    return {
        "text": "\n".join(lines), "candidate_count": len(ids),
        "verified_device_read_count": len(observations),
        "matched_light_count": len(lights),
        "room_membership_verified": False,
        "evidence_reads": [observations[ident]["read"] for ident in ids],
        "authority": "independent_identity_and_scoped_device_receipts",
    }

__all__ = ["entity_group_answer"]

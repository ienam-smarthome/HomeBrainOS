from __future__ import annotations

from typing import Any

from device_intelligence_catalogue import (
    CapabilityCatalogueDeviceIndex,
    _ATTRIBUTE_GROUPS,
    _CAPABILITY_GROUPS,
    _attributes,
    _capability_names,
    _compact,
    _label,
    _looks_like_camera,
    _looks_like_light,
    _looks_like_outlet,
    _normalise,
)


class SafeCapabilityCatalogueDeviceIndex(CapabilityCatalogueDeviceIndex):
    """Capability catalogue with conservative custom-driver name matching."""

    @staticmethod
    def _groups(item: dict[str, Any]) -> set[str]:
        groups: set[str] = set()
        generic = {"sensor", "switch", "battery", "alarm", "lock", "valve"}
        for capability in _capability_names(item):
            compact = _compact(capability)
            exact = _CAPABILITY_GROUPS.get(compact)
            if exact:
                groups.add(exact)
            if compact not in generic:
                for known, candidate in _CAPABILITY_GROUPS.items():
                    if len(known) >= 8 and compact.endswith(known):
                        groups.add(candidate)

        attrs = _attributes(item)
        for key in attrs:
            group = _ATTRIBUTE_GROUPS.get(_compact(key))
            if group:
                groups.add(group)

        if "switch" in attrs or "switch" in groups:
            groups.add("switch")
            if _looks_like_light(item) or "light" in groups:
                groups.add("light")
            elif _looks_like_outlet(item):
                groups.add("outlet")
        if _looks_like_camera(item):
            groups.add("camera")
        text = " " + _normalise(_label(item)) + " "
        if " fan " in text:
            groups.add("fan")
        if " button " in text:
            groups.add("button")
        groups.add("device")
        return groups


__all__ = ["SafeCapabilityCatalogueDeviceIndex"]

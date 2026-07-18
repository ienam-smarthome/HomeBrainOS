from __future__ import annotations

import asyncio
import time
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


def _membership_key(item: dict[str, Any]) -> str:
    for name in ("id", "deviceId", "device_id"):
        value = item.get(name)
        if value not in (None, ""):
            return str(value)
    return _normalise(_label(item))


class SafeCapabilityCatalogueDeviceIndex(CapabilityCatalogueDeviceIndex):
    """Capability catalogue with authoritative membership and safe matching.

    The compact all-device summary is the authoritative selected-device list.
    Detailed metadata may enrich those devices, but metadata-only records are not
    allowed back into live answers after a device has been removed from the MCP
    allowlist. This prevents a stale 120-second catalogue entry from making a
    removed sensor reappear in motion, room, recommendation or snapshot results.
    """

    async def enriched_devices(self, *, force: bool = False) -> list[dict[str, Any]]:
        summary, metadata = await asyncio.gather(
            self.summary_devices(force=force),
            self.metadata_devices(force=force),
        )
        metadata_by_key = {
            key: dict(item)
            for item in metadata
            if (key := _membership_key(item))
        }
        enriched: list[dict[str, Any]] = []
        selected_keys: set[str] = set()

        for item in summary:
            key = _membership_key(item)
            if not key:
                continue
            selected_keys.add(key)
            detail = metadata_by_key.get(key) or {}
            combined = dict(detail)
            combined.update(item)

            if detail.get("capabilities") is not None:
                combined["capabilities"] = detail["capabilities"]

            # A compact summary may contain empty state containers. Preserve the
            # detailed live attributes in that case, but never preserve a device
            # that is absent from the authoritative summary membership list.
            for state_key in ("attributes", "currentStates", "states", "state"):
                summary_value = item.get(state_key)
                metadata_value = detail.get(state_key)
                if summary_value in (None, {}, []) and metadata_value not in (None, {}, []):
                    combined[state_key] = metadata_value
            enriched.append(combined)

        self._last_metadata_orphans_dropped = len(
            set(metadata_by_key).difference(selected_keys)
        )
        return enriched

    async def dashboard_metrics(self, *, force: bool = False) -> dict[str, Any]:
        devices = await self.enriched_devices(force=force)
        lights_on = 0
        switches_on = 0
        motion_active = 0
        low_batteries = 0
        states_read = 0

        for item in devices:
            if item.get("disabled") is True:
                continue
            attrs = _attributes(item)
            if attrs:
                states_read += 1
            groups = self._groups(item)
            switch = _normalise(attrs.get("switch"))
            if switch == "on":
                if "light" in groups:
                    lights_on += 1
                else:
                    switches_on += 1
            if _normalise(attrs.get("motion")) == "active":
                motion_active += 1
            try:
                battery = float(str(attrs.get("battery")).replace("%", "").strip())
            except (TypeError, ValueError):
                battery = None
            if battery is not None and battery <= 20:
                low_batteries += 1

        snapshot = getattr(self, "_snapshot", None)
        age = (
            round(max(0.0, time.monotonic() - snapshot.stored_at), 2)
            if snapshot is not None
            else None
        )
        return {
            "success": True,
            "lights_on": lights_on,
            "switches_on": switches_on,
            "motion_active": motion_active,
            "low_batteries": low_batteries,
            "selected_devices": len(devices),
            "state_records": states_read,
            "metadata_orphans_dropped": int(
                getattr(self, "_last_metadata_orphans_dropped", 0)
            ),
            "updated_at": time.time(),
            "index_age_seconds": age,
        }

    def stats(self) -> dict[str, Any]:
        value = super().stats()
        now = time.monotonic()
        metadata = getattr(self, "_metadata", None)
        value.update(
            {
                "metadata_loaded": metadata is not None,
                "metadata_age_seconds": (
                    round(max(0.0, now - metadata.stored_at), 2)
                    if metadata is not None
                    else None
                ),
                "metadata_ttl_seconds": self.metadata_ttl_seconds,
                "metadata_orphans_dropped": int(
                    getattr(self, "_last_metadata_orphans_dropped", 0)
                ),
            }
        )
        return value

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

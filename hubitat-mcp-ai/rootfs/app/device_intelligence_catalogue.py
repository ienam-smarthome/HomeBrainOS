from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

from device_intelligence_index import DeviceIntelligenceIndex
from mcp_client import MCPError, MCPToolResult


_METADATA_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "capabilities",
    # Kingpanther's compact summary can legitimately omit currentStates. Keep the
    # detailed attributes in the catalogue so enriched_devices always has a live
    # state source instead of becoming metadata-only.
    "attributes",
    "disabled",
    "lastActivity",
]

_CAPABILITY_GROUPS = {
    "motionsensor": "motion",
    "contactsensor": "contact",
    "temperaturemeasurement": "temperature",
    "relativehumiditymeasurement": "humidity",
    "humiditymeasurement": "humidity",
    "presencesensor": "presence",
    "occupancysensor": "presence",
    "illuminancemeasurement": "illuminance",
    "battery": "battery",
    "thermostat": "thermostat",
    "thermostatheatingsetpoint": "thermostat",
    "lock": "lock",
    "smokedetector": "smoke",
    "carbonmonoxidedetector": "carbon-monoxide",
    "watersensor": "water",
    "moisturemeasurement": "moisture",
    "powermeter": "power",
    "energymeter": "energy",
    "switch": "switch",
    "switchlevel": "light",
    "colorcontrol": "light",
    "colortemperature": "light",
    "fancontrol": "fan",
    "valve": "valve",
    "pushablebutton": "button",
    "holdablebutton": "button",
    "doubletappablebutton": "button",
    "alarm": "alarm",
    "accelerationsensor": "acceleration",
    "sensor": "sensor",
}

_REQUESTED_CAPABILITY_GROUPS = {
    "motion sensor": "motion",
    "contact sensor": "contact",
    "temperature measurement": "temperature",
    "relative humidity measurement": "humidity",
    "presence sensor": "presence",
    "illuminance measurement": "illuminance",
    "battery": "battery",
    "thermostat": "thermostat",
    "lock": "lock",
    "smoke detector": "smoke",
    "carbon monoxide detector": "carbon-monoxide",
    "water sensor": "water",
    "power meter": "power",
    "energy meter": "energy",
    "switch": "switch",
    "fan control": "fan",
    "valve": "valve",
    "pushable button": "button",
    "holdable button": "button",
    "alarm": "alarm",
    "acceleration sensor": "acceleration",
    "sensor": "sensor",
}

_ATTRIBUTE_GROUPS = {
    "motion": "motion",
    "contact": "contact",
    "temperature": "temperature",
    "humidity": "humidity",
    "presence": "presence",
    "illuminance": "illuminance",
    "battery": "battery",
    "thermostatmode": "thermostat",
    "thermostatoperatingstate": "thermostat",
    "heatingsetpoint": "thermostat",
    "coolingsetpoint": "thermostat",
    "lock": "lock",
    "smoke": "smoke",
    "carbonmonoxide": "carbon-monoxide",
    "water": "water",
    "moisture": "moisture",
    "power": "power",
    "energy": "energy",
    "switch": "switch",
    "level": "light",
    "valve": "valve",
    "alarm": "alarm",
    "acceleration": "acceleration",
}


@dataclass(slots=True)
class _MetadataSnapshot:
    result: MCPToolResult
    devices: list[dict[str, Any]]
    stored_at: float
    expires_at: float


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def _device_id(item: dict[str, Any]) -> str:
    for key in ("id", "deviceId", "device_id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _label(item: dict[str, Any]) -> str:
    return str(item.get("label") or item.get("name") or item.get("displayName") or "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        direct = [item for item in value if isinstance(item, dict)]
        if direct:
            return direct
        nested: list[dict[str, Any]] = []
        for item in value:
            nested.extend(_rows(item))
        return nested
    if not isinstance(value, dict):
        return []
    for key in ("devices", "items", "results", "data", "content"):
        if key in value:
            found = _rows(value.get(key))
            if found:
                return found
    if _device_id(value) or _label(value):
        return [value]
    nested: list[dict[str, Any]] = []
    for item in value.values():
        nested.extend(_rows(item))
    return nested


def _attributes(item: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("currentStates", "states", "state", "attributes"):
        value = item.get(key)
        if isinstance(value, dict):
            merged.update(value)
            continue
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("attribute") or entry.get("key")
            if not name:
                continue
            current = entry.get("currentValue")
            if current in (None, ""):
                current = entry.get("value")
            if current in (None, ""):
                current = entry.get("currentState")
            merged[str(name)] = current
    return merged


def _capability_names(item: dict[str, Any]) -> set[str]:
    value = item.get("capabilities")
    names: set[str] = set()
    if isinstance(value, str):
        names.add(value)
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("capability") or entry.get("id")
                if name:
                    names.add(str(name))
            elif entry not in (None, ""):
                names.add(str(entry))
    elif isinstance(value, dict):
        for key, entry in value.items():
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("capability") or key
                names.add(str(name))
            else:
                names.add(str(key))
    return names


def _looks_like_light(item: dict[str, Any]) -> bool:
    text = _normalise(" ".join(str(item.get(key) or "") for key in ("label", "name", "type", "deviceType")))
    words = set(text.split())
    return bool(words.intersection({"light", "lamp", "bulb", "dimmer"})) or any(
        term in text for term in ("rgb", "colour", "color")
    )


def _looks_like_outlet(item: dict[str, Any]) -> bool:
    text = " " + _normalise(" ".join(str(item.get(key) or "") for key in ("label", "name", "type", "deviceType"))) + " "
    return any(term in text for term in (" socket ", " outlet ", " smart plug ", " plug "))


def _looks_like_camera(item: dict[str, Any]) -> bool:
    words = set(_normalise(" ".join(str(item.get(key) or "") for key in ("label", "name", "type", "deviceType"))).split())
    return "camera" in words or "cam" in words or any(word.endswith("cam") for word in words)


class CapabilityCatalogueDeviceIndex(DeviceIntelligenceIndex):
    """Unified state index enriched by one cached capability catalogue.

    Kingpanther's capabilityFilter is an exact capability-name match. Custom drivers
    can expose equivalent names without spaces (for example ``ContactSensor``), so
    an exact filter may return zero even though the device is selected. This index
    loads the selected devices' capability names and detailed attributes once,
    normalises them locally and merges that data with the compact live snapshot.
    """

    def __init__(
        self,
        client: Any,
        *,
        ttl_seconds: float = 15.0,
        capability_ttl_seconds: float = 60.0,
        metadata_ttl_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            client,
            ttl_seconds=ttl_seconds,
            capability_ttl_seconds=capability_ttl_seconds,
        )
        self.metadata_ttl_seconds = max(10.0, float(metadata_ttl_seconds))
        self._metadata: _MetadataSnapshot | None = None
        self._metadata_lock = asyncio.Lock()
        self._stats.setdefault("metadata_refreshes", 0)
        self._stats.setdefault("metadata_hits", 0)
        self._stats.setdefault("local_capability_matches", 0)
        self._stats.setdefault("server_capability_fallbacks", 0)

    async def invalidate(self) -> None:
        await super().invalidate()
        async with self._metadata_lock:
            self._metadata = None

    async def metadata_result(self, *, force: bool = False) -> MCPToolResult:
        snapshot = await self._metadata_snapshot(force=force)
        return snapshot.result

    async def metadata_devices(self, *, force: bool = False) -> list[dict[str, Any]]:
        snapshot = await self._metadata_snapshot(force=force)
        return list(snapshot.devices)

    async def _metadata_snapshot(self, *, force: bool = False) -> _MetadataSnapshot:
        now = time.monotonic()
        current = self._metadata
        if not force and current is not None and now < current.expires_at:
            self._stats["metadata_hits"] += 1
            return current

        async with self._metadata_lock:
            now = time.monotonic()
            current = self._metadata
            if not force and current is not None and now < current.expires_at:
                self._stats["metadata_hits"] += 1
                return current
            generation = self._generation
            result = await self.client.call_tool(
                "hub_list_devices",
                {
                    "detailed": True,
                    "format": "detailed",
                    "fields": list(_METADATA_FIELDS),
                },
            )
            if result.is_error:
                self._last_error = result.text or "Device capability catalogue refresh failed"
                raise MCPError(self._last_error)
            devices = self._dedupe(_rows(result.data))
            stored = time.monotonic()
            snapshot = _MetadataSnapshot(
                result=result,
                devices=devices,
                stored_at=stored,
                expires_at=stored + self.metadata_ttl_seconds,
            )
            if generation == self._generation:
                self._metadata = snapshot
                self._last_error = None
                self._stats["metadata_refreshes"] += 1
            return snapshot

    async def enriched_devices(self, *, force: bool = False) -> list[dict[str, Any]]:
        summary, metadata = await asyncio.gather(
            self.summary_devices(force=force),
            self.metadata_devices(force=force),
        )
        merged: dict[str, dict[str, Any]] = {}
        for item in metadata:
            key = _device_id(item) or _normalise(_label(item))
            if key:
                merged[key] = dict(item)
        for item in summary:
            key = _device_id(item) or _normalise(_label(item))
            if not key:
                continue
            combined = dict(merged.get(key) or {})
            combined.update(item)
            if key in merged and merged[key].get("capabilities") is not None:
                combined["capabilities"] = merged[key]["capabilities"]
            # A compact summary may contain an empty attributes/currentStates field.
            # Do not let that erase richer live attributes from the detailed catalogue.
            for state_key in ("attributes", "currentStates", "states", "state"):
                summary_value = item.get(state_key)
                metadata_value = (merged.get(key) or {}).get(state_key)
                if summary_value in (None, {}, []) and metadata_value not in (None, {}, []):
                    combined[state_key] = metadata_value
            merged[key] = combined
        return list(merged.values())

    async def capability_result(
        self,
        capability: str,
        *,
        detailed: bool = False,
        force: bool = False,
    ) -> MCPToolResult:
        group = _REQUESTED_CAPABILITY_GROUPS.get(_normalise(capability))
        if group:
            devices = await self.enriched_devices(force=force)
            matched = [item for item in devices if group in self._groups(item)]
            if matched:
                self._stats["local_capability_matches"] += 1
                if detailed:
                    try:
                        upstream = await super().capability_result(
                            capability,
                            detailed=True,
                            force=force,
                        )
                        upstream_rows = _rows(upstream.data)
                        if upstream_rows:
                            return upstream
                    except Exception:
                        pass
                return self._synthetic_result(capability, matched, source="capability-catalogue")
        self._stats["server_capability_fallbacks"] += 1
        return await super().capability_result(
            capability,
            detailed=detailed,
            force=force,
        )

    async def capability_devices(
        self,
        capability: str,
        *,
        detailed: bool = False,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        result = await self.capability_result(
            capability,
            detailed=detailed,
            force=force,
        )
        return self._dedupe(_rows(result.data))

    async def diagnostics(self, *, force: bool = False) -> dict[str, Any]:
        enriched, base = await asyncio.gather(
            self.enriched_devices(force=force),
            super().diagnostics(force=force),
        )
        groups: dict[str, set[str]] = {}
        for item in enriched:
            device_id = _device_id(item) or _label(item)
            for group in self._groups(item):
                groups.setdefault(group, set()).add(device_id)
        base = dict(base)
        base["groups"] = {key: len(value) for key, value in sorted(groups.items())}
        base["metadata_ttl_seconds"] = self.metadata_ttl_seconds
        base["state_records"] = sum(1 for item in enriched if _attributes(item))
        return base

    @classmethod
    def _synthetic_result(
        cls,
        capability: str,
        devices: list[dict[str, Any]],
        *,
        source: str,
    ) -> MCPToolResult:
        data = {
            "devices": devices,
            "count": len(devices),
            "capabilityFilter": capability,
            "source": source,
        }
        return MCPToolResult(
            name="hub_list_devices",
            arguments={"capabilityFilter": capability, "source": source},
            raw=data,
            text="",
            data=data,
            is_error=False,
        )

    @staticmethod
    def _groups(item: dict[str, Any]) -> set[str]:
        groups: set[str] = set()
        for capability in _capability_names(item):
            compact = _compact(capability)
            exact = _CAPABILITY_GROUPS.get(compact)
            if exact:
                groups.add(exact)
            for known, candidate in _CAPABILITY_GROUPS.items():
                if len(known) >= 6 and known in compact:
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


__all__ = [
    "CapabilityCatalogueDeviceIndex",
    "_ATTRIBUTE_GROUPS",
    "_CAPABILITY_GROUPS",
    "_attributes",
    "_capability_names",
    "_compact",
    "_label",
    "_looks_like_camera",
    "_looks_like_light",
    "_looks_like_outlet",
    "_normalise",
]

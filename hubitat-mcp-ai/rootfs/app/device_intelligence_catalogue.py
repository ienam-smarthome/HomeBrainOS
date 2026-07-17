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
    loads the selected devices' capability names once, normalises them locally and
    merges that metadata with the compact live-state snapshot.
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
                    # Preserve richer attributes when the exact upstream filter works,
                    # but never lose locally identified devices when it does not.
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
        devices = await self.enriched_devices(force=force)
        now = time.monotonic()
        groups: dict[str, set[str]] = {}
        no_room: list[str] = []
        disabled: list[str] = []
        aliases: dict[str, set[str]] = {}
        labels: dict[str, list[str]] = {}

        for item in devices:
            device_id = _device_id(item) or _label(item)
            label = _label(item) or device_id
            room = str(item.get("room") or "").strip()
            if not room:
                no_room.append(label)
            if bool(item.get("disabled")):
                disabled.append(label)
            for group in self._groups(item):
                groups.setdefault(group, set()).add(device_id)
            normal_label = _normalise(label)
            labels.setdefault(normal_label, []).append(_device_id(item))
            for alias in self._alias_forms(label):
                aliases.setdefault(alias, set()).add(device_id)

        ambiguous_aliases = {
            alias: sorted(
                _label(item)
                for item in devices
                if _device_id(item) in ids
            )
            for alias, ids in aliases.items()
            if len(ids) > 1
        }
        duplicate_labels = {
            label: sorted(ids)
            for label, ids in labels.items()
            if label and len(ids) > 1
        }
        metadata_age = (
            round(max(0.0, now - self._metadata.stored_at), 2)
            if self._metadata is not None
            else None
        )
        summary_age = (
            round(max(0.0, now - self._snapshot.stored_at), 2)
            if self._snapshot is not None
            else None
        )
        return {
            "success": True,
            "selected_count": len(devices),
            "groups": {key: len(value) for key, value in sorted(groups.items())},
            "rooms": sorted({str(item.get("room") or "").strip() for item in devices if str(item.get("room") or "").strip()}),
            "without_room": sorted(no_room, key=str.lower),
            "disabled": sorted(disabled, key=str.lower),
            "duplicate_labels": duplicate_labels,
            "ambiguous_aliases": ambiguous_aliases,
            "last_refresh_age_seconds": summary_age,
            "metadata_age_seconds": metadata_age,
            "ttl_seconds": self.ttl_seconds,
            "capability_ttl_seconds": self.capability_ttl_seconds,
            "metadata_ttl_seconds": self.metadata_ttl_seconds,
            "last_error": self._last_error,
            "stats": dict(self._stats),
        }

    def stats(self) -> dict[str, Any]:
        value = super().stats()
        now = time.monotonic()
        value.update(
            {
                "metadata_loaded": self._metadata is not None,
                "metadata_age_seconds": (
                    round(max(0.0, now - self._metadata.stored_at), 2)
                    if self._metadata is not None
                    else None
                ),
                "metadata_ttl_seconds": self.metadata_ttl_seconds,
            }
        )
        return value

    @staticmethod
    def _synthetic_result(
        capability: str,
        devices: list[dict[str, Any]],
        *,
        source: str,
    ) -> MCPToolResult:
        return MCPToolResult(
            name="hub_list_devices",
            arguments={"capabilityFilter": capability},
            raw={"source": source, "capabilityFilter": capability},
            text="",
            data={
                "devices": devices,
                "count": len(devices),
                "total": len(devices),
                "capabilityFilter": capability,
                "capabilityFilterMatchedKnownCapability": True,
                "source": source,
            },
            is_error=False,
        )

    @staticmethod
    def _alias_forms(label: str) -> set[str]:
        base = _normalise(label)
        if not base:
            return set()
        number_words = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        }
        number_digits = {value: key for key, value in number_words.items()}
        words = base.split()
        return {
            base,
            " ".join(number_words.get(word, word) for word in words),
            " ".join(number_digits.get(word, word) for word in words),
            _normalise(re.sub(r"\([^)]*\)", " ", label)),
        }

    @staticmethod
    def _groups(item: dict[str, Any]) -> set[str]:
        groups: set[str] = set()
        for capability in _capability_names(item):
            compact = _compact(capability)
            group = _CAPABILITY_GROUPS.get(compact)
            if group:
                groups.add(group)
            # Some custom drivers append words such as Capability or Sensor.
            for known, candidate in _CAPABILITY_GROUPS.items():
                if known and (compact.endswith(known) or known.endswith(compact)):
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


__all__ = ["CapabilityCatalogueDeviceIndex"]

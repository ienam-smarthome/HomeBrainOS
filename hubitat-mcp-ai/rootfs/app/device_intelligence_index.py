from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from mcp_client import MCPError, MCPToolResult


_SUMMARY_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "disabled",
    "lastActivity",
]

_DETAILED_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "attributes",
    "disabled",
    "lastActivity",
]

_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_NUMBER_DIGITS = {value: key for key, value in _NUMBER_WORDS.items()}

_CAPABILITY_GROUPS = {
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

_COMMON_ATTRIBUTE_GROUPS = {
    "motion": "motion",
    "contact": "contact",
    "temperature": "temperature",
    "humidity": "humidity",
    "presence": "presence",
    "illuminance": "illuminance",
    "battery": "battery",
    "thermostatMode": "thermostat",
    "thermostatOperatingState": "thermostat",
    "heatingSetpoint": "thermostat",
    "coolingSetpoint": "thermostat",
    "lock": "lock",
    "smoke": "smoke",
    "carbonMonoxide": "carbon-monoxide",
    "water": "water",
    "moisture": "moisture",
    "power": "power",
    "energy": "energy",
    "valve": "valve",
    "alarm": "alarm",
    "acceleration": "acceleration",
}


@dataclass(slots=True)
class _Snapshot:
    result: MCPToolResult
    devices: list[dict[str, Any]]
    stored_at: float
    expires_at: float


@dataclass(slots=True)
class _CapabilitySnapshot:
    result: MCPToolResult
    devices: list[dict[str, Any]]
    stored_at: float
    expires_at: float
    detailed: bool


def _normalise(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return re.sub(r"\s+", " ", text)


def _device_id(item: dict[str, Any]) -> str:
    for key in ("id", "deviceId", "device_id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _label(item: dict[str, Any]) -> str:
    for key in ("label", "name", "displayName"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _room_name(item: dict[str, Any]) -> str:
    value = item.get("room") or item.get("roomName")
    if isinstance(value, dict):
        value = value.get("name") or value.get("label") or value.get("roomName")
    return str(value or "").strip()


def _attributes(item: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("currentStates", "state", "states", "attributes"):
        value = item.get(key)
        if isinstance(value, dict):
            merged.update(value)
        elif isinstance(value, list):
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


def _device_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        direct = [item for item in value if isinstance(item, dict)]
        if direct:
            return direct
        rows: list[dict[str, Any]] = []
        for item in value:
            rows.extend(_device_rows(item))
        return rows
    if not isinstance(value, dict):
        return []
    for key in ("devices", "items", "results", "data", "content"):
        if key not in value:
            continue
        rows = _device_rows(value.get(key))
        if rows:
            return rows
    if _device_id(value) or _label(value):
        return [value]
    rows: list[dict[str, Any]] = []
    for nested in value.values():
        rows.extend(_device_rows(nested))
    return rows


def _looks_like_light(item: dict[str, Any]) -> bool:
    text = _normalise(
        " ".join(
            str(item.get(key) or "")
            for key in ("label", "name", "displayName", "type", "deviceType", "category")
        )
    )
    return any(word in text.split() for word in ("light", "lamp", "bulb", "dimmer")) or any(
        phrase in text for phrase in ("rgb", "colour", "color")
    )


def _looks_like_outlet(item: dict[str, Any]) -> bool:
    text = " " + _normalise(
        " ".join(str(item.get(key) or "") for key in ("label", "name", "type", "deviceType"))
    ) + " "
    return any(term in text for term in (" socket ", " outlet ", " smart plug ", " plug "))


def _looks_like_camera(item: dict[str, Any]) -> bool:
    words = set(_normalise(" ".join(str(item.get(key) or "") for key in ("label", "name", "type"))).split())
    return "camera" in words or "cam" in words or any(word.endswith("cam") for word in words)


def _alias_forms(label: str) -> set[str]:
    base = _normalise(label)
    if not base:
        return set()
    forms = {base}
    words = base.split()
    spoken = [_NUMBER_DIGITS.get(word, word) for word in words]
    numeric = [_NUMBER_WORDS.get(word, word) for word in words]
    forms.add(" ".join(spoken))
    forms.add(" ".join(numeric))
    forms.add(_normalise(re.sub(r"\([^)]*\)", " ", label)))
    return {item for item in forms if item}


class DeviceIntelligenceIndex:
    """One shared, truthful view of selected Hubitat devices and live states.

    The base index is a compact all-device summary. Capability-filtered snapshots
    are loaded only when a class needs evidence that summary currentStates cannot
    provide. All consumers share these snapshots, and broker invalidation after a
    control command invalidates this index as well.
    """

    def __init__(
        self,
        client: Any,
        *,
        ttl_seconds: float = 15.0,
        capability_ttl_seconds: float = 60.0,
    ) -> None:
        self.client = client
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self.capability_ttl_seconds = max(1.0, float(capability_ttl_seconds))
        self._snapshot: _Snapshot | None = None
        self._capabilities: dict[tuple[str, bool], _CapabilitySnapshot] = {}
        self._lock = asyncio.Lock()
        self._capability_locks: dict[tuple[str, bool], asyncio.Lock] = {}
        self._generation = 0
        self._last_error: str | None = None
        self._stats = {
            "summary_refreshes": 0,
            "summary_hits": 0,
            "capability_refreshes": 0,
            "capability_hits": 0,
            "invalidations": 0,
        }
        register = getattr(client, "register_invalidator", None)
        if callable(register):
            register(self._broker_invalidated)

    async def _broker_invalidated(self, category: str) -> None:
        if category in {"devices", "all"}:
            await self.invalidate()

    async def invalidate(self) -> None:
        async with self._lock:
            self._generation += 1
            self._snapshot = None
            self._capabilities.clear()
            self._stats["invalidations"] += 1

    async def summary_result(self, *, force: bool = False) -> MCPToolResult:
        snapshot = await self._summary_snapshot(force=force)
        return snapshot.result

    async def summary_devices(self, *, force: bool = False) -> list[dict[str, Any]]:
        snapshot = await self._summary_snapshot(force=force)
        return list(snapshot.devices)

    async def _summary_snapshot(self, *, force: bool = False) -> _Snapshot:
        now = time.monotonic()
        current = self._snapshot
        if not force and current is not None and now < current.expires_at:
            self._stats["summary_hits"] += 1
            return current

        async with self._lock:
            now = time.monotonic()
            current = self._snapshot
            if not force and current is not None and now < current.expires_at:
                self._stats["summary_hits"] += 1
                return current
            generation = self._generation
            result = await self.client.call_tool(
                "hub_list_devices",
                {
                    "detailed": False,
                    "format": "summary",
                    "fields": list(_SUMMARY_FIELDS),
                },
            )
            if result.is_error:
                self._last_error = result.text or "Device summary refresh failed"
                raise MCPError(self._last_error)
            devices = self._dedupe(_device_rows(result.data))
            stored = time.monotonic()
            snapshot = _Snapshot(
                result=result,
                devices=devices,
                stored_at=stored,
                expires_at=stored + self.ttl_seconds,
            )
            if generation == self._generation:
                self._snapshot = snapshot
                self._last_error = None
                self._stats["summary_refreshes"] += 1
            return snapshot

    async def capability_result(
        self,
        capability: str,
        *,
        detailed: bool = False,
        force: bool = False,
    ) -> MCPToolResult:
        snapshot = await self._capability_snapshot(
            capability,
            detailed=detailed,
            force=force,
        )
        return snapshot.result

    async def capability_devices(
        self,
        capability: str,
        *,
        detailed: bool = False,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        snapshot = await self._capability_snapshot(
            capability,
            detailed=detailed,
            force=force,
        )
        return list(snapshot.devices)

    async def _capability_snapshot(
        self,
        capability: str,
        *,
        detailed: bool,
        force: bool,
    ) -> _CapabilitySnapshot:
        key = (_normalise(capability), bool(detailed))
        now = time.monotonic()
        current = self._capabilities.get(key)
        if not force and current is not None and now < current.expires_at:
            self._stats["capability_hits"] += 1
            return current

        lock = self._capability_locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            current = self._capabilities.get(key)
            if not force and current is not None and now < current.expires_at:
                self._stats["capability_hits"] += 1
                return current
            generation = self._generation
            result = await self.client.call_tool(
                "hub_list_devices",
                {
                    "detailed": bool(detailed),
                    "format": "detailed" if detailed else "summary",
                    "capabilityFilter": capability,
                    "fields": list(_DETAILED_FIELDS if detailed else _SUMMARY_FIELDS),
                },
            )
            if result.is_error:
                self._last_error = result.text or f"Capability lookup failed: {capability}"
                raise MCPError(self._last_error)
            devices = self._dedupe(_device_rows(result.data))
            stored = time.monotonic()
            snapshot = _CapabilitySnapshot(
                result=result,
                devices=devices,
                stored_at=stored,
                expires_at=stored + self.capability_ttl_seconds,
                detailed=bool(detailed),
            )
            if generation == self._generation:
                self._capabilities[key] = snapshot
                self._last_error = None
                self._stats["capability_refreshes"] += 1
            return snapshot

    async def exact_device(self, requested_name: str) -> tuple[dict[str, Any] | None, list[str]]:
        devices = await self.summary_devices()
        target = _normalise(requested_name)
        aliases = self._alias_map(devices)
        ids = aliases.get(target, set())
        if len(ids) == 1:
            wanted = next(iter(ids))
            return next((item for item in devices if _device_id(item) == wanted), None), []

        target_words = set(target.split())
        scored: list[tuple[float, str]] = []
        for item in devices:
            label = _label(item)
            normal = _normalise(label)
            if not normal:
                continue
            words = set(normal.split())
            overlap = len(target_words & words) / max(1, len(target_words | words))
            if target in normal or normal in target:
                overlap += 0.5
            if overlap > 0.15:
                scored.append((overlap, label))
        scored.sort(key=lambda entry: (-entry[0], entry[1].lower()))
        return None, [label for _, label in scored[:5]]

    async def dashboard_metrics(self, *, force: bool = False) -> dict[str, Any]:
        snapshot = await self._summary_snapshot(force=force)
        lights_on = 0
        switches_on = 0
        motion_active = 0
        low_batteries = 0
        for item in snapshot.devices:
            attrs = _attributes(item)
            switch = _normalise(attrs.get("switch"))
            if switch == "on":
                if _looks_like_light(item):
                    lights_on += 1
                else:
                    switches_on += 1
            if _normalise(attrs.get("motion")) == "active":
                motion_active += 1
            try:
                battery = float(str(attrs.get("battery")).replace("%", "").strip())
            except Exception:
                battery = None
            if battery is not None and battery <= 20:
                low_batteries += 1
        return {
            "success": True,
            "lights_on": lights_on,
            "switches_on": switches_on,
            "motion_active": motion_active,
            "low_batteries": low_batteries,
            "selected_devices": len(snapshot.devices),
            "updated_at": time.time(),
            "index_age_seconds": round(max(0.0, time.monotonic() - snapshot.stored_at), 2),
        }

    async def diagnostics(self, *, force: bool = False) -> dict[str, Any]:
        snapshot = await self._summary_snapshot(force=force)
        groups: dict[str, set[str]] = {}
        no_room: list[str] = []
        disabled: list[str] = []
        for item in snapshot.devices:
            device_id = _device_id(item) or _label(item)
            label = _label(item) or device_id
            room = _room_name(item)
            if not room:
                no_room.append(label)
            if bool(item.get("disabled")):
                disabled.append(label)
            for group in self._infer_groups(item):
                groups.setdefault(group, set()).add(device_id)

        aliases = self._alias_map(snapshot.devices)
        ambiguous_aliases = {
            alias: sorted(
                _label(item)
                for item in snapshot.devices
                if _device_id(item) in ids
            )
            for alias, ids in aliases.items()
            if len(ids) > 1
        }
        duplicate_labels: dict[str, list[str]] = {}
        labels: dict[str, list[str]] = {}
        for item in snapshot.devices:
            labels.setdefault(_normalise(_label(item)), []).append(_device_id(item))
        for label, ids in labels.items():
            if label and len(ids) > 1:
                duplicate_labels[label] = sorted(ids)

        loaded_capabilities = []
        now = time.monotonic()
        for (capability, detailed), item in sorted(self._capabilities.items()):
            loaded_capabilities.append(
                {
                    "capability": capability,
                    "detailed": detailed,
                    "devices": len(item.devices),
                    "age_seconds": round(max(0.0, now - item.stored_at), 2),
                }
            )

        return {
            "success": True,
            "selected_count": len(snapshot.devices),
            "groups": {key: len(value) for key, value in sorted(groups.items())},
            "rooms": sorted({room for item in snapshot.devices if (room := _room_name(item))}),
            "without_room": sorted(no_room, key=str.lower),
            "disabled": sorted(disabled, key=str.lower),
            "duplicate_labels": duplicate_labels,
            "ambiguous_aliases": ambiguous_aliases,
            "loaded_capabilities": loaded_capabilities,
            "last_refresh_age_seconds": round(max(0.0, now - snapshot.stored_at), 2),
            "ttl_seconds": self.ttl_seconds,
            "capability_ttl_seconds": self.capability_ttl_seconds,
            "last_error": self._last_error,
            "stats": dict(self._stats),
        }

    def stats(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            **self._stats,
            "summary_loaded": self._snapshot is not None,
            "summary_age_seconds": (
                round(max(0.0, now - self._snapshot.stored_at), 2)
                if self._snapshot is not None
                else None
            ),
            "capability_entries": len(self._capabilities),
            "last_error": self._last_error,
        }

    @staticmethod
    def _dedupe(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        for item in devices:
            key = _device_id(item) or _normalise(_label(item))
            if key:
                found.setdefault(key, item)
        return list(found.values())

    @staticmethod
    def _alias_map(devices: list[dict[str, Any]]) -> dict[str, set[str]]:
        aliases: dict[str, set[str]] = {}
        for item in devices:
            device_id = _device_id(item)
            if not device_id:
                continue
            for alias in _alias_forms(_label(item)) | _alias_forms(str(item.get("name") or "")):
                aliases.setdefault(alias, set()).add(device_id)
        return aliases

    @staticmethod
    def _infer_groups(item: dict[str, Any]) -> set[str]:
        attrs = _attributes(item)
        groups = {group for key, group in _COMMON_ATTRIBUTE_GROUPS.items() if key in attrs}
        if "switch" in attrs:
            if _looks_like_light(item):
                groups.add("light")
            elif _looks_like_outlet(item):
                groups.add("outlet")
            else:
                groups.add("switch")
        if _looks_like_camera(item):
            groups.add("camera")
        text = " " + _normalise(_label(item)) + " "
        if " fan " in text:
            groups.add("fan")
        if " button " in text:
            groups.add("button")
        groups.add("device")
        return groups


async def maybe_call(callback: Callable[[str], Awaitable[None] | None], category: str) -> None:
    result = callback(category)
    if asyncio.iscoroutine(result):
        await result


__all__ = ["DeviceIntelligenceIndex"]

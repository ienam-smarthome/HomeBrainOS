from __future__ import annotations

import asyncio
import json
import re
import time
from difflib import SequenceMatcher
from typing import Any, Awaitable

from fallback_router import _device_id, _label, _normalise
from fast_fallback_live import (
    FastFallbackRouter as LiveFastFallbackRouter,
    _looks_like_light,
    live_attributes,
)
from mcp_client import MCPError, MCPToolResult
from presenter import (
    compact_number,
    display_payload,
    first_mapping,
    first_value,
    format_memory_kb,
    safe_debug,
)
from spoken_device_name import unique_spoken_match
from system_presenter_v2 import present_hub_info_v2

_GROUP_WORDS = {
    "light",
    "lights",
    "lamp",
    "lamps",
    "bulb",
    "bulbs",
    "switch",
    "switches",
}
_FILLER_WORDS = {"all", "the", "my", "our", "room"}

_DEVICE_HEALTH_TERMS = (
    "device health",
    "offline or stale",
    "offline and stale",
    "offline devices",
    "stale devices",
    "devices offline",
    "devices stale",
    "not responding",
    "unresponsive devices",
)

_HUB_RESOURCE_TERMS = (
    "hub resources",
    "hub resource",
    "hub cpu",
    "cpu load",
    "processor load",
    "free memory",
    "hub memory",
    "hub temperature",
    "database size",
    "hub uptime",
)

_NEGATIVE_HEALTH = {
    "offline",
    "unavailable",
    "not present",
    "dead",
    "failed",
    "unreachable",
    "not responding",
}
_POSITIVE_HEALTH = {
    "online",
    "available",
    "present",
    "healthy",
    "ok",
    "alive",
    "reachable",
}
_DEVICE_HEALTH_PAGE_SIZE = 50
_DEVICE_HEALTH_MAX_PAGES = 100
_PERIODIC_STATE_KEYS = {
    "temperature",
    "humidity",
    "power",
    "energy",
    "voltage",
    "current",
    "airQualityIndex",
    "carbonDioxide",
    "pressure",
    "moisture",
}
_PERIODIC_CAPABILITY_IDS = {
    "temperaturemeasurement",
    "relativehumiditymeasurement",
    "powermeter",
    "energymeter",
    "voltagemeasurement",
    "currentmeter",
    "airquality",
    "carbondioxidemeasurement",
    "pressuremeasurement",
    "moisturemeasurement",
}
_EVENT_DRIVEN_CAPABILITY_IDS = {
    "switch",
    "pushablebutton",
    "holdablebutton",
    "doubletappablebutton",
    "motionsensor",
    "contactsensor",
    "presencesensor",
    "lock",
    "doorcontrol",
    "windowshade",
}
_QUIET_DEVICE_LABEL = re.compile(
    r"\b(?:button|mini\s+switch|remote|scene|socket|outlet|plug|switch|camera|cam|"
    r"vacuum|roborock|robot|fp1|fp2|fp300|motion|contact|presence|occupancy|lux|"
    r"illuminance|thermostat|trv|life360|display|doorbell)\b",
    re.IGNORECASE,
)
_UNUSABLE_STATE_TEXT = {
    "",
    "unknown",
    "unavailable",
    "not available",
    "none",
    "null",
    "n/a",
}
_DEVICE_HEALTH_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "disabled",
    "lastActivity",
    "currentStates",
    "attributes",
    "capabilities",
]


def _capability_names(value: Any) -> set[str]:
    if isinstance(value, list):
        entries = value
    elif value in (None, ""):
        entries = []
    else:
        entries = [value]

    names: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict):
            raw = (
                entry.get("displayName")
                or entry.get("name")
                or entry.get("label")
                or entry.get("id")
            )
        else:
            raw = entry
        text = re.sub(r"[^a-z0-9]+", "", _normalise(raw))
        if text:
            names.add(text)
    return names


def _health_state(device: dict[str, Any]) -> str:
    attrs = live_attributes(device)
    return _normalise(
        attrs.get("healthStatus")
        or attrs.get("status")
        or device.get("healthStatus")
        or device.get("status")
    )


def _device_keys(device: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    device_id = _device_id(device)
    if device_id not in (None, ""):
        keys.add(f"id:{device_id}")
    label = _normalise(_label(device))
    if label:
        keys.add(f"label:{label}")
    return keys


def _usable_state(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_usable_state(item) for item in value.values())
    if isinstance(value, list):
        return any(_usable_state(item) for item in value)
    if value is None:
        return False
    return _normalise(value) not in _UNUSABLE_STATE_TEXT


def _matching_device(
    device: dict[str, Any],
    indexed: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for key in _device_keys(device):
        if key in indexed:
            return indexed[key]
    return None


def _index_devices(devices: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for device in devices:
        for key in _device_keys(device):
            indexed[key] = device
    return indexed


def _enrich_stale_device(
    stale_device: dict[str, Any],
    live_device: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep stale-filter age metadata while restoring omitted live state evidence."""

    if live_device is None:
        return stale_device

    enriched = dict(live_device)
    for key, value in stale_device.items():
        if key in {"currentStates", "attributes", "capabilities"} and not _usable_state(value):
            continue
        enriched[key] = value
    return enriched


def classify_age_only_device(
    device: dict[str, Any],
    *,
    authoritative_health: str = "",
) -> dict[str, Any]:
    """Classify a row returned by MCP's ``stale:<hours>`` event-age filter.

    ``lastActivity`` is event age, not a reachability test. An explicit negative
    ``healthStatus`` always wins. Event-driven or normally static devices with no
    negative health state are informational quiet rows. Periodic telemetry may be
    marked stale when it has stopped reporting.
    """

    attrs = live_attributes(device)
    health = _normalise(authoritative_health) or _health_state(device)
    label = _label(device) or f"Device {_device_id(device)}"
    last_activity = device.get("lastActivity") or "No activity recorded"
    capabilities = _capability_names(device.get("capabilities"))
    searchable = _normalise(
        " ".join(
            str(device.get(key) or "")
            for key in ("label", "name", "type", "deviceType", "category")
        )
    )

    base = {
        "label": label,
        "last_activity": last_activity,
        "health": health or None,
        "capabilities": sorted(capabilities),
        "state_keys": sorted(str(key) for key in attrs),
    }

    if health in _NEGATIVE_HEALTH:
        return {
            **base,
            "kind": "offline",
            "reason": f"Live healthStatus is {health}.",
        }
    if health in _POSITIVE_HEALTH:
        return {
            **base,
            "kind": "quiet",
            "reason": (
                f"Live healthStatus is {health}; lastActivity records event age, not connectivity."
            ),
        }

    event_driven = bool(capabilities & _EVENT_DRIVEN_CAPABILITY_IDS)
    quiet_identity = bool(_QUIET_DEVICE_LABEL.search(searchable))
    if event_driven or quiet_identity:
        return {
            **base,
            "kind": "quiet",
            "reason": (
                "This is an event-driven or normally static device, so an unchanged state can "
                "produce no Hubitat events for long periods."
            ),
        }

    periodic_keys = _PERIODIC_STATE_KEYS.intersection(attrs)
    periodic_capabilities = capabilities & _PERIODIC_CAPABILITY_IDS
    if periodic_keys or periodic_capabilities:
        useful_periodic = {
            key: attrs.get(key)
            for key in periodic_keys
            if _usable_state(attrs.get(key))
        }
        return {
            **base,
            "kind": "stale",
            "reason": (
                "Periodic telemetry has not generated a Hubitat event within the configured "
                "threshold."
            ),
            "periodic_values": useful_periodic,
        }

    if any(_usable_state(value) for value in attrs.values()):
        return {
            **base,
            "kind": "quiet",
            "reason": (
                "A current state is available, but the device has not generated a new event; "
                "this is not proof of a health fault."
            ),
        }

    return {
        **base,
        "kind": "quiet",
        "reason": (
            "Only an old lastActivity timestamp is available. That is insufficient evidence "
            "to call the device stale or offline."
        ),
    }

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

# Safe speech/name variants that preserve the intended device meaning. The
# normalised form is accepted only when exactly one selected MCP device matches.
_DEVICE_WORD_ALIASES = {
    "prayer": "pray",
    "prayers": "pray",
}

_HUMIDITY_APPLIANCE_WORDS = {"humidifier", "dehumidifier"}


def normalise_spoken_device_name(value: str) -> str:
    """Normalise common speech-to-text variants without changing device meaning."""
    words = re.findall(r"[a-z0-9]+", _normalise(value))
    normalised: list[str] = []
    for word in words:
        if word == "number":
            continue
        word = _NUMBER_WORDS.get(word, word)
        word = _DEVICE_WORD_ALIASES.get(word, word)
        normalised.append(word)
    return " ".join(normalised)


def _humidity_speech_key(value: str) -> str | None:
    """Return a shared key for humidifier/dehumidifier speech variants.

    Speech recognition commonly drops the short leading "de" sound. This key is
    used only after exact matching has failed, and only a unique full-label match
    is accepted. Other words and number suffixes must still match exactly.
    """
    words = normalise_spoken_device_name(value).split()
    if not any(word in _HUMIDITY_APPLIANCE_WORDS for word in words):
        return None
    return " ".join(
        "humidity-appliance" if word in _HUMIDITY_APPLIANCE_WORDS else word
        for word in words
    )

class VerifiedFastFallbackRouter(LiveFastFallbackRouter):
    """Live MCP fallback with verified controls and explicit update reporting."""

    def __init__(
        self,
        *args: Any,
        control_verification_timeout_seconds: float = 7.0,
        control_verification_initial_delay_seconds: float = 0.2,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.control_verification_timeout_seconds = max(
            2.0,
            min(20.0, float(control_verification_timeout_seconds)),
        )
        self.control_verification_initial_delay_seconds = max(
            0.05,
            min(2.0, float(control_verification_initial_delay_seconds)),
        )

    async def _hub_info(self) -> dict[str, Any]:
        arguments = {
            "includeAppUpdate": True,
            "includeHealthAlerts": True,
        }
        result = await self.client.call_tool("hub_get_info", arguments)
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        # The MCP app-version check is asynchronous on its first call. Give it one
        # short follow-up read when the server explicitly says a check is in progress.
        data = first_mapping(result.data)
        app_update = data.get("appUpdate") if isinstance(data, dict) else None
        latest = (
            str(app_update.get("latestVersion") or "")
            if isinstance(app_update, dict)
            else ""
        )
        if "check in progress" in latest.lower():
            await asyncio.sleep(1.0)
            follow_up = await self.client.call_tool("hub_get_info", arguments)
            if not follow_up.is_error:
                result = follow_up

        message, display = present_hub_info_v2(result.data)
        return self._decorate(
            self._response(message, "fallback-hub-info", True, result),
            display,
            result,
        )

    async def _fresh_live_devices(
        self,
        capability_filter: str | None = None,
    ) -> MCPToolResult:
        """Force a new Hubitat read instead of reusing a pre-command cache entry.

        Verification used to re-read through the 12-second device cache. If the
        first poll happened before a slow device published its new state, every
        later poll returned that same cached old value. Invalidating before each
        poll makes every attempt an authoritative upstream read.
        """
        invalidate = getattr(self.client, "invalidate", None)
        if callable(invalidate):
            await invalidate("devices")
        return await self._live_devices(capability_filter)

    @staticmethod
    def _find_control_device(
        result: MCPToolResult,
        *,
        device_id: Any,
        label: str,
    ) -> dict[str, Any] | None:
        rows = FastFallbackRouter._device_rows(result.data)
        return next(
            (
                item
                for item in rows
                if str(_device_id(item)) == str(device_id)
                or _normalise(_label(item)) == _normalise(label)
            ),
            None,
        )

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        # A control decision must not use a cached state. This prevents a recently
        # changed device being incorrectly reported as "already on/off".
        candidates_result = await self._fresh_live_devices("Switch")
        candidates = self._device_rows(candidates_result.data)
        match, alternatives = self._match_device(requested_name, candidates)
        if not match:
            response: dict[str, Any]
            if alternatives:
                response = self._response(
                    "I could not find an exact device match. Closest matches: "
                    + ", ".join(alternatives[:5])
                    + ".",
                    "fallback-ambiguous-device",
                    False,
                    candidates_result,
                )
                response["alternatives"] = alternatives[:5]
            else:
                response = self._response(
                    f'I could not find a device named "{requested_name}".',
                    "fallback-device-not-found",
                    False,
                    candidates_result,
                )
                response["alternatives"] = []
            response["requested_name"] = requested_name
            response["requested_state"] = _normalise(action)
            return response

        device_id = _device_id(match)
        label = _label(match) or requested_name
        if device_id is None:
            return self._response(
                f'I found "{label}", but the MCP result did not include its device ID.',
                "fallback-device-id-missing",
                False,
            )

        initial_state = _normalise(live_attributes(match).get("switch")) or "unknown"
        desired_state = _normalise(action)
        if initial_state == desired_state:
            display = display_payload(
                "device-control",
                label,
                subtitle=f"Already {desired_state}",
                metrics=[
                    {"label": "Requested", "value": desired_state.title(), "icon": "🎯"},
                    {"label": "Fresh state", "value": initial_state.title(), "icon": "✅"},
                ],
                note="The current state was refreshed from Hubitat before deciding no command was needed.",
            )
            return self._decorate(
                self._response(
                    f"{label} is already {desired_state}.",
                    "fallback-device-already-set",
                    True,
                    candidates_result,
                ),
                display,
                candidates_result,
            )

        direct_tool = await self.client.get_tool("hub_call_device_command")
        properties = (
            (direct_tool.input_schema or {}).get("properties", {})
            if direct_tool
            else {}
        )
        command_args: dict[str, Any] = {}
        for key in ("deviceId", "id", "device_id"):
            if not properties or key in properties:
                command_args[key] = device_id
                break
        command_args["command"] = desired_state
        if not properties or "params" in properties:
            command_args["params"] = []

        command_result = await self._execute_catalog_tool(
            "hub_call_device_command",
            "hub_manage_devices",
            command_args,
        )
        if command_result.is_error:
            return self._response(
                command_result.text or f'Failed to turn {desired_state} "{label}".',
                "fallback-control-error",
                False,
                command_result,
            )

        verified_state = "unknown"
        verification_result: MCPToolResult | None = None
        attempts: list[dict[str, Any]] = []
        verification_started = time.perf_counter()
        deadline = verification_started + self.control_verification_timeout_seconds
        delays = (
            self.control_verification_initial_delay_seconds,
            0.45,
            0.8,
            1.25,
            1.75,
            2.25,
        )

        for delay in delays:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            await asyncio.sleep(min(delay, remaining))
            if time.perf_counter() > deadline:
                break
            poll_started = time.perf_counter()
            verification_result = await self._fresh_live_devices("Switch")
            current = self._find_control_device(
                verification_result,
                device_id=device_id,
                label=label,
            )
            if current:
                verified_state = _normalise(live_attributes(current).get("switch")) or "unknown"
            attempts.append(
                {
                    "elapsed_seconds": round(time.perf_counter() - verification_started, 2),
                    "state": verified_state,
                    "read_ms": round((time.perf_counter() - poll_started) * 1000),
                }
            )
            if verified_state == desired_state:
                break

        verification_seconds = round(time.perf_counter() - verification_started, 2)
        confirmed = verified_state == desired_state
        if confirmed:
            message = f"{label} turned {desired_state} and was confirmed {verified_state}."
            subtitle = f"Confirmed {verified_state} in {verification_seconds:g}s"
            tone = "success"
            intent = "fallback-device-control-confirmed"
            success = True
        elif verified_state in {"on", "off"}:
            message = (
                f"The {desired_state} command was accepted for {label}, but its Hubitat switch "
                f"state was still {verified_state} after {verification_seconds:g} seconds. "
                "The device may be reporting its new state late; check it again."
            )
            subtitle = f"State update pending · last read {verified_state}"
            tone = "warning"
            intent = "fallback-device-control-pending"
            success = False
        else:
            message = (
                f"The {desired_state} command was accepted for {label}, but Hubitat did not return "
                f"a readable switch state within {verification_seconds:g} seconds. Check the device state again."
            )
            subtitle = "State update pending"
            tone = "warning"
            intent = "fallback-device-control-unverified"
            success = False

        display = display_payload(
            "device-control",
            label,
            subtitle=subtitle,
            metrics=[
                {"label": "Before", "value": initial_state.title(), "icon": "↩️"},
                {"label": "Requested", "value": desired_state.title(), "icon": "🎯"},
                {
                    "label": "Latest read",
                    "value": verified_state.title(),
                    "icon": "✅" if confirmed else "⏳",
                },
                {"label": "Verification", "value": f"{verification_seconds:g}s", "icon": "⏱️"},
            ],
            items=[
                {
                    "icon": "✅" if confirmed else "⏳",
                    "title": "Command verification",
                    "subtitle": message,
                    "value": "Confirmed" if confirmed else "Pending",
                    "tone": tone,
                }
            ],
            note=(
                "Every verification attempt bypasses the device-state cache and reads fresh Hubitat currentStates. "
                "Most devices confirm on the first or second read; slower drivers are allowed a longer window."
            ),
        )
        response = self._response(
            message,
            intent,
            success,
            verification_result or command_result,
        )
        response["command_sent"] = True
        response["command_accepted"] = True
        response["confirmed"] = confirmed
        response["outcome"] = "completed" if confirmed else "sent"
        response["submitted"] = True
        response["verified"] = confirmed
        response["requested_state"] = desired_state
        response["initial_state"] = initial_state
        response["verified_state"] = verified_state
        response["verification_seconds"] = verification_seconds
        response["verification_attempts"] = attempts
        response["technical"] = json.dumps(
            {
                "device_id": device_id,
                "label": label,
                "command_arguments": command_args,
                "command_result": command_result.data,
                "initial_state": initial_state,
                "verified_state": verified_state,
                "verification_seconds": verification_seconds,
                "verification_attempts": attempts,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        response["display"] = display
        return response

class AttentionFastFallbackRouter(VerifiedFastFallbackRouter):
    """Verified MCP fallback with one authoritative attention scan."""

    def __init__(self, client: Any, attention_stale_hours: float = 48) -> None:
        super().__init__(client)
        self.attention_stale_hours = max(1.0, float(attention_stale_hours))

    async def _safe_result(
        self,
        name: str,
        operation: Awaitable[MCPToolResult],
    ) -> tuple[str, MCPToolResult | None, str | None]:
        try:
            result = await operation
            if result.is_error:
                return name, result, result.text or f"{name} returned an error"
            return name, result, None
        except Exception as exc:
            return name, None, str(exc)

    async def _attention(self) -> dict[str, Any]:
        battery_call = self._live_devices("Battery")
        stale_call = self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": False,
                "format": "summary",
                "filter": f"stale:{self.attention_stale_hours:g}",
                "fields": [
                    "id",
                    "name",
                    "label",
                    "room",
                    "disabled",
                    "lastActivity",
                    "currentStates",
                ],
            },
        )
        health_call = self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": True,
                "format": "detailed",
                "capabilityFilter": "Health Check",
                "fields": ["id", "name", "label", "room", "attributes"],
            },
        )
        hub_call = self.client.call_tool(
            "hub_get_info",
            {"includeAppUpdate": True, "includeHealthAlerts": True},
        )

        outcomes = await asyncio.gather(
            self._safe_result("battery", battery_call),
            self._safe_result("stale", stale_call),
            self._safe_result("health", health_call),
            self._safe_result("hub", hub_call),
        )
        results = {name: result for name, result, _error in outcomes}
        errors = {name: error for name, _result, error in outcomes if error}

        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        counts = {
            "battery": 0,
            "device_health": 0,
            "hub": 0,
            "updates": 0,
        }

        def add_item(
            category: str,
            title: str,
            value: str,
            subtitle: str,
            *,
            icon: str,
            tone: str = "warning",
            priority: float = 50,
        ) -> None:
            key = (category, _normalise(title))
            if key in seen:
                return
            seen.add(key)
            items.append(
                {
                    "category": category,
                    "icon": icon,
                    "title": title,
                    "value": value,
                    "subtitle": subtitle,
                    "tone": tone,
                    "priority": priority,
                }
            )
            counts[category] += 1

        battery_result = results.get("battery")
        if battery_result is not None:
            for device in self._device_rows(battery_result.data):
                battery = self._number_value(live_attributes(device).get("battery"))
                if battery is None or battery > 20:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                add_item(
                    "battery",
                    label,
                    f"{battery:g}%",
                    "Replace soon" if battery <= 15 else "Low battery",
                    icon="🪫",
                    tone="danger" if battery <= 15 else "warning",
                    priority=battery,
                )

        offline_labels: set[str] = set()
        health_result = results.get("health")
        if health_result is not None:
            for device in self._device_rows(health_result.data):
                attrs = live_attributes(device)
                health = _normalise(
                    attrs.get("healthStatus")
                    or attrs.get("status")
                    or device.get("healthStatus")
                    or device.get("status")
                )
                if health not in {
                    "offline",
                    "unavailable",
                    "not present",
                    "dead",
                    "failed",
                }:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                offline_labels.add(_normalise(label))
                add_item(
                    "device_health",
                    label,
                    "Offline",
                    "Hubitat Health Check reports this device is not responding",
                    icon="📡",
                    tone="danger",
                    priority=0,
                )

        stale_result = results.get("stale")
        if stale_result is not None:
            for device in self._device_rows(stale_result.data):
                if device.get("disabled") is True:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                if _normalise(label) in offline_labels:
                    continue
                last_activity = device.get("lastActivity") or "No activity recorded"
                add_item(
                    "device_health",
                    label,
                    f"Stale {self.attention_stale_hours:g}h+",
                    f"Last activity: {last_activity}",
                    icon="🕒",
                    tone="warning",
                    priority=20,
                )

        hub_result = results.get("hub")
        if hub_result is not None:
            hub_data = first_mapping(hub_result.data)
            for field, title, icon in (
                ("memoryWarning", "Hub memory", "💾"),
                ("temperatureWarning", "Hub temperature", "🌡️"),
                ("databaseWarning", "Hub database", "🗄️"),
            ):
                warning = hub_data.get(field)
                if warning:
                    add_item(
                        "hub",
                        title,
                        "Warning",
                        str(warning),
                        icon=icon,
                        tone="danger",
                        priority=5,
                    )

            if hub_data.get("safeMode") is True:
                add_item(
                    "hub",
                    "Hub safe mode",
                    "On",
                    "The Hubitat hub is currently running in safe mode",
                    icon="🛡️",
                    tone="danger",
                    priority=1,
                )

            health_alerts = hub_data.get("healthAlerts")
            active_alerts = (
                health_alerts.get("active")
                if isinstance(health_alerts, dict)
                else []
            )
            if isinstance(active_alerts, list):
                for alert in active_alerts:
                    add_item(
                        "hub",
                        "Hub health alert",
                        str(alert),
                        "Hubitat reports an active platform health alert",
                        icon="⚠️",
                        tone="danger",
                        priority=4,
                    )

            _message, hub_display = present_hub_info_v2(hub_result.data)
            platform = hub_display.get("platform_update") or {}
            app_update = hub_display.get("app_update") or {}
            if platform.get("available") is True:
                add_item(
                    "updates",
                    "Hub platform update",
                    str(platform.get("available_version") or "Available"),
                    str(platform.get("message") or "A Hubitat platform update is available"),
                    icon="⬆️",
                    tone="warning",
                    priority=10,
                )
            elif platform.get("available") is None:
                add_item(
                    "updates",
                    "Hub update status",
                    "Unknown",
                    str(platform.get("message") or "Platform update status could not be read"),
                    icon="❔",
                    tone="warning",
                    priority=30,
                )

            if app_update.get("available") is True:
                add_item(
                    "updates",
                    "MCP Rule Server update",
                    str(app_update.get("latest") or "Available"),
                    str(app_update.get("message") or "An MCP Rule Server update is available"),
                    icon="📦",
                    tone="warning",
                    priority=11,
                )

        if errors:
            failed = ", ".join(sorted(errors))
            add_item(
                "hub",
                "Attention scan incomplete",
                "Check failed",
                f"Could not read: {failed}",
                icon="⚠️",
                tone="warning",
                priority=2,
            )

        items.sort(
            key=lambda item: (
                item.get("priority", 100),
                item.get("title", "").lower(),
            )
        )

        if items:
            message = "Items needing attention:\n" + "\n".join(
                f"- {item['title']}: {item['value']} ({item['subtitle']})"
                for item in items
            )
        else:
            message = (
                "No low batteries, offline or stale devices, hub warnings, "
                "or available updates were found."
            )

        technical_result = next(
            (result for result in results.values() if result is not None),
            None,
        )
        display = display_payload(
            "attention",
            "Needs attention",
            subtitle=f"{len(items)} issue{'' if len(items) == 1 else 's'} found",
            metrics=[
                {"label": "Low batteries", "value": str(counts["battery"]), "icon": "🪫"},
                {"label": "Offline/stale", "value": str(counts["device_health"]), "icon": "📡"},
                {"label": "Hub warnings", "value": str(counts["hub"]), "icon": "⚠️"},
                {"label": "Updates", "value": str(counts["updates"]), "icon": "⬆️"},
            ],
            items=[
                {key: value for key, value in item.items() if key not in {"priority", "category"}}
                for item in items
            ],
            note=(
                f"Device staleness threshold: {self.attention_stale_hours:g} hours."
                + (f" Incomplete sources: {', '.join(sorted(errors))}." if errors else "")
            ),
        )
        return self._decorate(
            self._response(message, "fallback-attention", True, technical_result),
            display,
            technical_result,
        )

    @staticmethod
    def _number_value(value: Any) -> float | None:
        try:
            return float(str(value).replace("%", "").strip())
        except Exception:
            return None

class GroupFastFallbackRouter(AttentionFastFallbackRouter):
    """Attention-aware fallback with verified plural/group device controls."""

    @staticmethod
    def _group_request(requested_name: str) -> tuple[str, list[str]] | None:
        target = _normalise(requested_name)
        words = re.findall(r"[a-z0-9]+", target)
        if not words:
            return None

        plural_kind = None
        if any(word in {"lights", "lamps", "bulbs"} for word in words):
            plural_kind = "light"
        elif "switches" in words:
            plural_kind = "switch"
        elif words[0] == "all" and any(word in _GROUP_WORDS for word in words):
            plural_kind = "light" if any(
                word in {"light", "lights", "lamp", "lamps", "bulb", "bulbs"}
                for word in words
            ) else "switch"

        if plural_kind is None:
            return None

        qualifiers = [
            word
            for word in words
            if word not in _GROUP_WORDS and word not in _FILLER_WORDS
        ]
        return plural_kind, qualifiers

    @staticmethod
    def _group_candidates(
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        parsed = FastFallbackRouter._group_request(requested_name)
        if parsed is None:
            return []
        kind, qualifiers = parsed

        matches: list[dict[str, Any]] = []
        for item in candidates:
            is_light = _looks_like_light(item)
            if kind == "light" and not is_light:
                continue
            if kind == "switch" and is_light:
                continue

            searchable = _normalise(
                " ".join(
                    str(item.get(key) or "")
                    for key in (
                        "label",
                        "name",
                        "displayName",
                        "room",
                        "category",
                        "type",
                        "deviceType",
                    )
                )
            )
            searchable_words = set(re.findall(r"[a-z0-9]+", searchable))
            if qualifiers and not all(word in searchable_words for word in qualifiers):
                continue
            matches.append(item)

        return sorted(matches, key=lambda item: _label(item).lower())

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        live_result = await self._live_devices("Switch")
        candidates = self._device_rows(live_result.data)
        group = self._group_candidates(requested_name, candidates)
        if group:
            return await self._control_group(
                requested_name,
                action,
                group,
                live_result,
            )
        return await super()._control_device(requested_name, action)

    async def _control_group(
        self,
        requested_name: str,
        action: str,
        devices: list[dict[str, Any]],
        initial_result: Any,
    ) -> dict[str, Any]:
        desired_state = _normalise(action)
        tool = await self.client.get_tool("hub_call_device_command")
        properties = (
            (tool.input_schema or {}).get("properties", {})
            if tool
            else {}
        )

        rows: dict[str, dict[str, Any]] = {}
        command_details: list[dict[str, Any]] = []

        for device in devices:
            device_id = _device_id(device)
            label = _label(device) or f"Device {device_id}"
            initial_state = _normalise(live_attributes(device).get("switch")) or "unknown"
            key = str(device_id)
            rows[key] = {
                "id": device_id,
                "label": label,
                "initial": initial_state,
                "verified": initial_state,
                "command_sent": False,
                "command_error": None,
            }

            if initial_state == desired_state:
                continue
            if device_id is None:
                rows[key]["command_error"] = "Device ID missing"
                continue

            args: dict[str, Any] = {}
            for id_key in ("deviceId", "id", "device_id"):
                if not properties or id_key in properties:
                    args[id_key] = device_id
                    break
            args["command"] = desired_state
            if not properties or "params" in properties:
                args["params"] = []

            result = await self._execute_catalog_tool(
                "hub_call_device_command",
                "hub_manage_devices",
                args,
            )
            rows[key]["command_sent"] = True
            if result.is_error:
                rows[key]["command_error"] = result.text or "Command failed"
            command_details.append(
                {
                    "device_id": device_id,
                    "label": label,
                    "arguments": args,
                    "success": not result.is_error,
                    "result": result.data,
                    "error": result.text if result.is_error else None,
                }
            )

        pending = [
            row
            for row in rows.values()
            if row["initial"] != desired_state
            and row["command_sent"]
            and not row["command_error"]
        ]

        verification_result = initial_result
        if pending:
            for delay in (0.35, 0.75, 1.1):
                await asyncio.sleep(delay)
                verification_result = await self._live_devices("Switch")
                current_by_id = {
                    str(_device_id(item)): item
                    for item in self._device_rows(verification_result.data)
                }
                for row in pending:
                    current = current_by_id.get(str(row["id"]))
                    if current:
                        row["verified"] = (
                            _normalise(live_attributes(current).get("switch"))
                            or "unknown"
                        )
                if all(row["verified"] == desired_state for row in pending):
                    break

        confirmed = 0
        already = 0
        failed = 0
        display_items: list[dict[str, Any]] = []
        lines: list[str] = []

        for row in rows.values():
            if row["initial"] == desired_state:
                already += 1
                state_text = f"Already {desired_state}"
                tone = "success"
                icon = "✅"
            elif row["verified"] == desired_state and not row["command_error"]:
                confirmed += 1
                state_text = f"Confirmed {desired_state}"
                tone = "success"
                icon = "✅"
            else:
                failed += 1
                if row["command_error"]:
                    state_text = f"Command failed: {row['command_error']}"
                elif row["verified"] in {"on", "off"}:
                    state_text = f"Not confirmed · still {row['verified']}"
                else:
                    state_text = "State could not be verified"
                tone = "warning"
                icon = "⚠️"

            lines.append(f"- {row['label']}: {state_text}")
            display_items.append(
                {
                    "icon": icon,
                    "title": row["label"],
                    "subtitle": state_text,
                    "value": row["verified"].title(),
                    "tone": tone,
                }
            )

        total = len(rows)
        successful = confirmed + already
        group_title = requested_name.strip().title()
        if failed == 0:
            message = (
                f"{group_title}: all {total} devices are confirmed {desired_state}.\n"
                + "\n".join(lines)
            )
            intent = "fallback-device-group-control-confirmed"
        else:
            message = (
                f"{group_title}: {successful} of {total} devices are confirmed {desired_state}; "
                f"{failed} could not be confirmed.\n"
                + "\n".join(lines)
            )
            intent = "fallback-device-group-control-partial"

        display = display_payload(
            "device-group-control",
            group_title,
            subtitle=f"{successful} of {total} confirmed {desired_state}",
            metrics=[
                {"label": "Matched", "value": str(total), "icon": "💡"},
                {"label": "Confirmed", "value": str(confirmed), "icon": "✅"},
                {"label": "Already set", "value": str(already), "icon": "↩️"},
                {"label": "Issues", "value": str(failed), "icon": "⚠️"},
            ],
            items=display_items,
            note="Plural light commands are matched by device label/room and verified from Hubitat currentStates.",
        )
        response = self._response(
            message,
            intent,
            failed == 0,
            verification_result,
        )
        response.update(
            {
                "display": display,
                "requested_state": desired_state,
                "matched_devices": total,
                "confirmed_devices": successful,
                "failed_devices": failed,
                "technical": json.dumps(
                    {
                        "requested_name": requested_name,
                        "requested_state": desired_state,
                        "devices": list(rows.values()),
                        "commands": command_details,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            }
        )
        return response

class FastFallbackRouter(GroupFastFallbackRouter):
    """Group-aware fallback with focused device-health and hub-resource routes."""

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if any(term in q for term in _HUB_RESOURCE_TERMS):
            return await self._hub_resources()
        if any(term in q for term in _DEVICE_HEALTH_TERMS):
            return await self._device_health()
        return await super().answer(query)

    async def _hub_resources(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        data = first_mapping(result.data)
        model = first_value(data, "name", "hubName", "model") or "Hubitat hub"
        firmware = first_value(data, "firmwareVersion", "currentVersion")
        free_memory = format_memory_kb(
            first_value(data, "freeMemoryKB", "freeMemoryKb")
        )
        temperature = compact_number(
            first_value(data, "internalTempCelsius", "temperature"),
            "°C",
        )
        database_size = format_memory_kb(
            first_value(data, "databaseSizeKB", "databaseSizeKb")
        )
        uptime = first_value(
            data,
            "uptimeFormatted",
            "formattedUptime",
            "uptime",
        )
        cpu_raw = first_value(
            data,
            "cpuLoad",
            "cpuLoadPercent",
            "cpuPercent",
            "processorLoad",
        )
        cpu = compact_number(cpu_raw, "%") if cpu_raw not in (None, "") else None

        lines: list[str] = []
        if cpu:
            lines.append(f"Hub CPU load is {cpu}.")
        else:
            lines.append(
                "The Hubitat MCP Rule Server does not expose CPU load through hub_get_info."
            )
        if free_memory:
            lines.append(f"Hub free memory is {free_memory}.")
        if temperature:
            lines.append(f"Internal temperature is {temperature}.")
        if database_size:
            lines.append(f"Database size is {database_size}.")
        if uptime:
            lines.append(f"Uptime is {uptime}.")

        metrics = [
            {
                "label": "CPU load",
                "value": cpu or "Not exposed",
                "icon": "🧠",
            }
        ]
        for label, value, icon in (
            ("Free memory", free_memory, "💾"),
            ("Temperature", temperature, "🌡️"),
            ("Database", database_size, "🗄️"),
            ("Uptime", uptime, "⏱️"),
        ):
            if value not in (None, ""):
                metrics.append({"label": label, "value": str(value), "icon": icon})

        subtitle = " · ".join(
            value
            for value in (
                str(model),
                f"Firmware {firmware}" if firmware else None,
            )
            if value
        )
        display = display_payload(
            "hub-resources",
            "Hub resources",
            subtitle=subtitle,
            metrics=metrics,
            note=(
                "Kingpanther MCP currently exposes free memory, temperature, database size "
                "and uptime, but not the Hubitat CPU percentage."
                if not cpu
                else "Live values were read from Kingpanther's hub_get_info tool."
            ),
        )
        return self._decorate(
            self._response(
                "\n".join(lines),
                "fallback-hub-resources",
                True,
                result,
            ),
            display,
            result,
        )

    @staticmethod
    def _reported_inventory_count(data: Any) -> int | None:
        """Read a total/inventory count the MCP tool response may report.

        Some Hubitat MCP builds page or cap device-list results. If the raw
        response carries a count field larger than the number of rows we
        actually parsed, the list was truncated and the health scan is
        incomplete rather than clean.
        """

        if not isinstance(data, dict):
            return None
        for key in (
            "device_count",
            "total",
            "count",
            "inventory_count",
            "total_count",
            "projected_inventory_count",
        ):
            value = data.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return int(value)
        return None

    async def _paged_device_health_inventory(self) -> MCPToolResult:
        """Read the complete detailed inventory without exceeding MCP response limits."""

        rows: list[dict[str, Any]] = []
        seen_pages: set[tuple[str, ...]] = set()
        first_result: MCPToolResult | None = None
        reported_total: int | None = None

        for page_number in range(_DEVICE_HEALTH_MAX_PAGES):
            offset = page_number * _DEVICE_HEALTH_PAGE_SIZE
            result = await self._execute_catalog_tool(
                "hub_list_devices",
                "hub_read_devices",
                {
                    "detailed": True,
                    "format": "detailed",
                    "fields": list(_DEVICE_HEALTH_FIELDS),
                    "limit": _DEVICE_HEALTH_PAGE_SIZE,
                    "offset": offset,
                },
            )
            if first_result is None:
                first_result = result

            data = result.data
            if result.is_error or (
                isinstance(data, dict)
                and (
                    data.get("response_too_large") is True
                    or data.get("truncated") is True
                )
            ):
                return result

            page_rows = self._device_rows(data)
            page_signature = tuple(
                str(_device_id(device) or _label(device) or index)
                for index, device in enumerate(page_rows)
            )
            if offset and page_rows and page_signature in seen_pages:
                return MCPToolResult(
                    name=result.name,
                    arguments=result.arguments,
                    raw=result.raw,
                    text=result.text,
                    data={
                        "devices": rows,
                        "truncated": True,
                        "pagination_error": "the MCP server repeated a device page",
                    },
                    is_error=False,
                )
            seen_pages.add(page_signature)
            rows.extend(page_rows)

            page_total = self._reported_inventory_count(data)
            if page_total is not None:
                reported_total = max(reported_total or 0, page_total)
            if not page_rows or len(page_rows) < _DEVICE_HEALTH_PAGE_SIZE:
                break
            if reported_total is not None and len(rows) >= reported_total:
                break
        else:
            assert first_result is not None
            return MCPToolResult(
                name=first_result.name,
                arguments=first_result.arguments,
                raw=first_result.raw,
                text=first_result.text,
                data={
                    "devices": rows,
                    "truncated": True,
                    "pagination_error": "the device inventory exceeded the pagination safety limit",
                },
                is_error=False,
            )

        assert first_result is not None
        aggregate_data: dict[str, Any] = {"devices": rows}
        if reported_total is not None:
            aggregate_data["total"] = reported_total
        return MCPToolResult(
            name=first_result.name,
            arguments=first_result.arguments,
            raw=first_result.raw,
            text=first_result.text,
            data=aggregate_data,
            is_error=False,
        )

    async def _device_health(self) -> dict[str, Any]:
        stale_call = self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": True,
                "format": "detailed",
                "filter": f"stale:{self.attention_stale_hours:g}",
                "fields": list(_DEVICE_HEALTH_FIELDS),
            },
        )
        # Do not depend on capabilityFilter=Health Check. Some drivers expose a
        # real healthStatus current state without advertising that capability in
        # the MCP catalogue, and some MCP builds use HealthCheck without a space.
        live_call = self._paged_device_health_inventory()

        outcomes = await asyncio.gather(
            self._safe_result("stale", stale_call),
            self._safe_result("live", live_call),
        )
        results = {name: result for name, result, _error in outcomes}
        errors = {name: error for name, _result, error in outcomes if error}

        issues: dict[str, dict[str, Any]] = {}
        health_by_key: dict[str, str] = {}
        live_rows: list[dict[str, Any]] = []
        health_evidence: list[dict[str, Any]] = []

        live_result = results.get("live")
        if live_result is not None:
            live_rows = self._device_rows(live_result.data)
            live_data = live_result.data
            if isinstance(live_data, dict) and (
                live_data.get("response_too_large") is True
                or live_data.get("truncated") is True
            ):
                estimated_bytes = live_data.get("estimatedBytes")
                size_limit_bytes = live_data.get("sizeLimitBytes")
                size_detail = (
                    f" ({estimated_bytes} bytes exceeds the {size_limit_bytes}-byte limit)"
                    if isinstance(estimated_bytes, (int, float))
                    and isinstance(size_limit_bytes, (int, float))
                    else ""
                )
                errors["coverage"] = (
                    "the live device inventory response was truncated or too large"
                    f"{size_detail}"
                )
            reported_total = self._reported_inventory_count(live_data)
            if (
                "coverage" not in errors
                and reported_total is not None
                and reported_total > len(live_rows)
            ):
                errors["coverage"] = (
                    f"the live health scan only returned {len(live_rows)} of "
                    f"{reported_total} known devices (result may be paginated/truncated)"
                )
            for device in live_rows:
                health = _health_state(device)
                if health:
                    health_evidence.append(
                        {
                            "id": _device_id(device),
                            "label": _label(device),
                            "health": health,
                            "state_keys": sorted(live_attributes(device)),
                        }
                    )
                for key in _device_keys(device):
                    health_by_key[key] = health
                if health not in _NEGATIVE_HEALTH or device.get("disabled") is True:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                issues[_normalise(label)] = {
                    "id": _device_id(device),
                    "icon": "📡",
                    "title": label,
                    "value": "Offline",
                    "subtitle": f"Live Hubitat healthStatus: {health}",
                    "tone": "danger",
                    "kind": "offline",
                    "reason": f"Live healthStatus is {health}.",
                }

        live_index = _index_devices(live_rows)
        quiet: list[dict[str, Any]] = []
        classified_rows: list[dict[str, Any]] = []
        stale_result = results.get("stale")
        if stale_result is not None:
            for stale_device in self._device_rows(stale_result.data):
                if stale_device.get("disabled") is True:
                    continue
                live_device = _matching_device(stale_device, live_index)
                device = _enrich_stale_device(stale_device, live_device)
                label = _label(device) or f"Device {_device_id(device)}"
                key = _normalise(label)
                if key in issues:
                    continue
                authoritative_health = next(
                    (
                        health_by_key[device_key]
                        for device_key in _device_keys(device)
                        if device_key in health_by_key
                    ),
                    "",
                )
                classified = classify_age_only_device(
                    device,
                    authoritative_health=authoritative_health,
                )
                classified_rows.append(classified)
                if classified["kind"] == "offline":
                    issues[key] = {
                        "id": _device_id(device),
                        "icon": "📡",
                        "title": label,
                        "value": "Offline",
                        "subtitle": str(classified["reason"]),
                        "tone": "danger",
                        "kind": "offline",
                        "reason": classified["reason"],
                    }
                elif classified["kind"] == "stale":
                    issues[key] = {
                        "id": _device_id(device),
                        "icon": "📈",
                        "title": label,
                        "value": f"Telemetry stale {self.attention_stale_hours:g}h+",
                        "subtitle": f"Last activity: {classified['last_activity']}",
                        "tone": "warning",
                        "kind": "stale",
                        "reason": classified["reason"],
                    }
                else:
                    quiet.append(
                        {
                            "id": _device_id(device),
                            "icon": "🕒",
                            "title": label,
                            "value": "Quiet, not offline",
                            "subtitle": f"Last event: {classified['last_activity']}",
                            "tone": None,
                            "kind": "quiet",
                            "reason": classified["reason"],
                        }
                    )

        issue_items = sorted(
            issues.values(),
            key=lambda item: (
                0 if item["kind"] == "offline" else 1,
                item["title"].lower(),
            ),
        )
        quiet.sort(key=lambda item: item["title"].lower())
        offline_count = sum(item["kind"] == "offline" for item in issue_items)
        stale_count = sum(item["kind"] == "stale" for item in issue_items)

        if issue_items:
            message = "Confirmed device-health issues:\n" + "\n".join(
                f"- {item['title']}: {item['value']} ({item['subtitle']})"
                for item in issue_items
            )
            if quiet:
                message += (
                    f"\n{len(quiet)} other device{'' if len(quiet) == 1 else 's'} have an old "
                    "lastActivity timestamp but no negative live health state."
                )
            if errors:
                message += "\nThe scan was incomplete: " + ", ".join(sorted(errors)) + "."
        elif errors:
            message = (
                "The device-health scan was incomplete, so I cannot confirm that no devices are "
                "offline or stale. Failed checks: " + ", ".join(sorted(errors)) + "."
            )
        elif quiet:
            message = (
                "No devices are confirmed offline or stale. "
                f"{len(quiet)} selected device{'' if len(quiet) == 1 else 's'} have not generated "
                f"a Hubitat event for {self.attention_stale_hours:g} hours or longer, but "
                "lastActivity is event age rather than a connectivity test."
            )
        else:
            message = "No devices are confirmed offline or stale."

        display_items = [
            {key: value for key, value in item.items() if key not in {"kind", "reason"}}
            for item in issue_items
        ]
        quiet_shown = quiet[:12]
        display_items.extend(
            {key: value for key, value in item.items() if key not in {"kind", "reason"}}
            for item in quiet_shown
        )
        if errors:
            display_items.append(
                {
                    "icon": "⚠️",
                    "title": "Device-health scan incomplete",
                    "value": "Check failed",
                    "subtitle": "Could not read: " + ", ".join(sorted(errors)),
                    "tone": "warning",
                }
            )

        note = (
            "Offline is read from each selected device's detailed live healthStatus. The stale "
            "filter is used only for lastActivity age and periodic-telemetry classification."
        )
        omitted_quiet = max(0, len(quiet) - len(quiet_shown))
        if omitted_quiet:
            note += f" {omitted_quiet} additional quiet timestamp rows are omitted."
        if errors:
            note += f" Incomplete checks: {', '.join(sorted(errors))}."

        display = display_payload(
            "device-health",
            "Device health",
            subtitle=(
                f"{len(issue_items)} confirmed issue{'' if len(issue_items) == 1 else 's'}"
                if issue_items
                else "Scan incomplete"
                if errors
                else "No confirmed offline or stale devices"
            ),
            metrics=[
                {"label": "Offline", "value": str(offline_count), "icon": "📡"},
                {"label": "Stale telemetry", "value": str(stale_count), "icon": "📈"},
                {"label": "Quiet timestamps", "value": str(len(quiet)), "icon": "🕒"},
                {"label": "Threshold", "value": f"{self.attention_stale_hours:g}h", "icon": "⏱️"},
            ],
            items=display_items,
            note=note,
        )
        technical_result = next(
            (result for result in results.values() if result is not None),
            None,
        )
        response = self._response(
            message,
            "fallback-device-health",
            not errors,
            technical_result,
        )
        response["route"] = "mcp-fast"
        response["display"] = display
        response["offline_count"] = offline_count
        response["stale_telemetry_count"] = stale_count
        response["quiet_timestamp_count"] = len(quiet)
        response["health_items"] = [*issue_items, *quiet]
        response["offline_devices"] = [
            item for item in issue_items if item["kind"] == "offline"
        ]
        response["stale_devices"] = [
            item for item in issue_items if item["kind"] == "stale"
        ]
        response["quiet_devices"] = list(quiet)
        response["technical"] = safe_debug(
            {
                "threshold_hours": self.attention_stale_hours,
                "selected_devices_scanned": len(live_rows),
                "offline_devices": [
                    item for item in issue_items if item["kind"] == "offline"
                ],
                "stale_telemetry": [
                    item for item in issue_items if item["kind"] == "stale"
                ],
                "quiet_timestamp_devices": quiet,
                "classified_stale_filter_rows": classified_rows,
                "live_health_evidence": health_evidence,
                "scan_errors": errors,
                "classification_rule": (
                    "Detailed live healthStatus is authoritative. lastActivity age alone is quiet; "
                    "only periodic telemetry without a positive health state is marked stale."
                ),
            }
        )
        return response

class SpeechFastFallbackRouter(FastFallbackRouter):
    """Fast fallback with speech-aware matching and verified device controls."""

    @staticmethod
    def _match_device(
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, list[str]]:
        target = normalise_spoken_device_name(requested_name)
        exact = [
            item
            for item in candidates
            if normalise_spoken_device_name(_label(item)) == target
        ]
        if len(exact) == 1:
            return exact[0], []

        # Handle only conservative speech variations (number words, spacing and
        # duplicated letters) and require one unique full-label key. This resolves
        # "liiving room light two" to "Livingroom Light 2" without guessing between
        # Light 1 and Light 2 when the number is omitted.
        spoken = unique_spoken_match(
            requested_name,
            candidates,
            label_of=_label,
        )
        if spoken is not None:
            return spoken, []

        scored = sorted(
            (
                (
                    SequenceMatcher(
                        None,
                        target,
                        normalise_spoken_device_name(_label(item)),
                    ).ratio(),
                    item,
                )
                for item in candidates
                if _label(item)
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        alternatives = [_label(item) for score, item in scored if score >= 0.35]
        return None, alternatives

    @staticmethod
    def _humidity_speech_alias_match(
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        requested_key = _humidity_speech_key(requested_name)
        if not requested_key:
            return None
        matches = [
            item
            for item in candidates
            if _label(item) and _humidity_speech_key(_label(item)) == requested_key
        ]
        return matches[0] if len(matches) == 1 else None

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        answer = await super()._control_device(requested_name, action)
        if answer.get("intent") not in {
            "fallback-ambiguous-device",
            "fallback-device-not-found",
        }:
            return answer

        # The MCP label filter may not equate spoken numbers with digits. Retry
        # against the complete live switch inventory before involving Ollama.
        live_result = await self._live_devices("Switch")
        candidates = self._device_rows(live_result.data)
        match, alternatives = self._match_device(requested_name, candidates)
        if match:
            resolved_label = _label(match)
            resolved = dict(await super()._control_device(resolved_label, action))
            if normalise_spoken_device_name(requested_name) != normalise_spoken_device_name(
                resolved_label
            ):
                resolved.update(
                    {
                        "speech_alias_applied": True,
                        "heard_device_name": requested_name,
                        "resolved_device_name": resolved_label,
                    }
                )
            return resolved

        # Speech-to-text often hears "dehumidifier" as "humidifier". Treat those
        # words as equivalent only when every other label token (including its
        # number) matches and exactly one live switch candidate exists.
        speech_alias = self._humidity_speech_alias_match(requested_name, candidates)
        if speech_alias:
            resolved_label = _label(speech_alias)
            resolved = await super()._control_device(resolved_label, action)
            resolved = dict(resolved)
            resolved.update(
                {
                    "speech_alias_applied": True,
                    "heard_device_name": requested_name,
                    "resolved_device_name": resolved_label,
                }
            )
            resolved["message"] = (
                f'Interpreted “{requested_name}” as “{resolved_label}” from speech.\n'
                + str(resolved.get("message") or "")
            ).strip()
            return resolved

        enriched = dict(answer)
        enriched.update(
            {
                "requested_name": requested_name,
                "requested_action": action,
                "alternatives": alternatives[:5],
                "normalised_requested_name": normalise_spoken_device_name(
                    requested_name
                ),
            }
        )
        if alternatives:
            enriched["message"] = (
                "I could not find an exact device match. Closest matches: "
                + ", ".join(alternatives[:5])
                + "."
            )
            enriched["intent"] = "fallback-ambiguous-device"
        return enriched

__all__ = [
    "AttentionFastFallbackRouter",
    "FastFallbackRouter",
    "GroupFastFallbackRouter",
    "SpeechFastFallbackRouter",
    "VerifiedFastFallbackRouter",
    "classify_age_only_device",
    "normalise_spoken_device_name",
]

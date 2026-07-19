from __future__ import annotations

import asyncio
import re
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_groups import FastFallbackRouter as GroupFastFallbackRouter
from fast_fallback_live import live_attributes
from mcp_client import MCPError
from presenter import (
    compact_number,
    display_payload,
    first_mapping,
    first_value,
    format_memory_kb,
    safe_debug,
)


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
        live_call = self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": True,
                "format": "detailed",
                "fields": list(_DEVICE_HEALTH_FIELDS),
            },
        )

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


__all__ = ["FastFallbackRouter", "classify_age_only_device"]

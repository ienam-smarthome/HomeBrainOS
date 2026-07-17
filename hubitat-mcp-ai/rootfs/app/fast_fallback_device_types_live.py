from __future__ import annotations

from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_device_types import DeviceTypeSpec
from fast_fallback_device_types_compat import FastFallbackRouter as CompatibleDeviceTypeRouter
from fast_fallback_live import live_attributes
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, first_value, normalise_text, safe_debug


# Use Hubitat's actual capability filter wherever a standard capability exists.
# This is more reliable than downloading every selected device and trying to infer
# its class locally.
_CAPABILITY_FILTERS: dict[str, tuple[str, ...]] = {
    "motion": ("Motion Sensor",),
    "contact": ("Contact Sensor",),
    "temperature": ("Temperature Measurement",),
    "humidity": ("Relative Humidity Measurement",),
    "presence": ("Presence Sensor",),
    "illuminance": ("Illuminance Measurement",),
    "battery": ("Battery",),
    "thermostat": ("Thermostat",),
    "lock": ("Lock",),
    "smoke": ("Smoke Detector",),
    "carbon-monoxide": ("Carbon Monoxide Detector",),
    "water": ("Water Sensor",),
    "power": ("Power Meter",),
    "energy": ("Energy Meter",),
    "light": ("Switch",),
    "switch": ("Switch",),
    "outlet": ("Switch",),
    "fan": ("Fan Control",),
    "valve": ("Valve",),
    "button": ("Pushable Button", "Holdable Button"),
    "alarm": ("Alarm",),
    "acceleration": ("Acceleration Sensor",),
    "sensor": ("Sensor",),
}

# Kingpanther's summary currentStates contains these common attributes. Other
# classes use a capability-filtered detailed call so the response stays small.
_SUMMARY_STATE_TYPES = {
    "motion",
    "contact",
    "temperature",
    "humidity",
    "battery",
    "light",
    "switch",
    "outlet",
    "sensor",
}

# These filters deliberately return a broad class and still need local name/state
# classification to split lights from sockets and generic switches.
_LOCAL_FILTER_AFTER_CAPABILITY = {"light", "switch", "outlet"}

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


class FastFallbackRouter(CompatibleDeviceTypeRouter):
    """Capability-first device inventories with truthful zero-result handling."""

    async def _device_type_inventory(self, spec: DeviceTypeSpec) -> dict[str, Any]:
        result, rows, evidence = await self._matching_rows(spec)
        rows = self._dedupe_rows(rows)
        rows.sort(
            key=lambda item: (
                _normalise(self._room_name(item)),
                _normalise(_label(item)),
            )
        )

        items: list[dict[str, Any]] = []
        lines: list[str] = []
        state_count = 0
        attention_count = 0
        for item in rows[:60]:
            label = _label(item) or f"Device {_device_id(item)}"
            attrs = live_attributes(item)
            state = self._state_for_type(spec, attrs)
            if state != "Available":
                state_count += 1
            tone = self._tone_for_state(state)
            if tone == "warning":
                attention_count += 1
            room = self._room_name(item) or "No room assigned"
            device_type = normalise_text(
                first_value(item, "deviceType", "type", "driverName", "category")
                or evidence.get("type_label")
                or "Hubitat device"
            )
            subtitle = " · ".join(bit for bit in (room, device_type) if bit)
            items.append(
                {
                    "icon": spec.icon,
                    "title": label,
                    "value": state,
                    "subtitle": subtitle,
                    "tone": tone,
                }
            )
            lines.append(f"- {label}: {state} ({room})")

        classification_complete = bool(evidence.get("classification_complete"))
        if rows:
            message = f"{len(rows)} {spec.title.lower()} found:\n" + "\n".join(lines)
            subtitle = f"{len(rows)} selected Hubitat device{'' if len(rows) == 1 else 's'}"
        elif classification_complete:
            message = (
                f"No {spec.title.lower()} were found among the devices selected in "
                "MCP Rule Server."
            )
            subtitle = "No matching selected devices"
        else:
            selected_count = evidence.get("selected_count")
            count_text = (
                f"{selected_count} selected devices"
                if isinstance(selected_count, int)
                else "the selected devices"
            )
            message = (
                f"MCP returned {count_text}, but did not expose enough capability or live-state "
                f"evidence to identify {spec.title.lower()}. I cannot confirm that the count is zero."
            )
            subtitle = "Type evidence incomplete"

        metrics = [
            {"label": "Devices", "value": str(len(rows)) if classification_complete or rows else "Unknown", "icon": spec.icon},
            {"label": "Live states", "value": str(state_count), "icon": "📡"},
        ]
        if attention_count:
            metrics.append(
                {"label": "Need attention", "value": str(attention_count), "icon": "⚠️"}
            )

        display = display_payload(
            "device-type-inventory",
            spec.title,
            subtitle=subtitle,
            metrics=metrics,
            items=items,
            note=(
                "Standard device classes are selected by Hubitat capabilityFilter. "
                "Live values come from currentStates or capability-filtered attributes. "
                "Devices not selected in MCP Rule Server cannot appear."
            ),
        )
        response = self._response(
            message,
            f"fallback-device-type-{spec.key}",
            True,
            result,
        )
        response["display"] = display
        response["device_type"] = spec.key
        response["device_count"] = len(rows) if classification_complete or rows else None
        response["technical"] = safe_debug(
            {
                "device_type": spec.key,
                "matched_devices": rows,
                "state_count": state_count,
                "attention_count": attention_count,
                "evidence": evidence,
            }
        )
        return response

    async def _matching_rows(
        self,
        spec: DeviceTypeSpec,
    ) -> tuple[MCPToolResult, list[dict[str, Any]], dict[str, Any]]:
        filters = _CAPABILITY_FILTERS.get(spec.key, ())
        source_results: list[MCPToolResult] = []
        rows: list[dict[str, Any]] = []
        matched_filters: list[str] = []

        for capability in filters:
            detailed = spec.key not in _SUMMARY_STATE_TYPES
            result = await self._capability_devices(capability, detailed=detailed)
            source_results.append(result)
            candidates = self._device_rows(result.data)
            if spec.key in _LOCAL_FILTER_AFTER_CAPABILITY:
                candidates = [
                    item for item in candidates if self._matches_type(spec, item)
                ]
            # The server has already performed the authoritative exact capability
            # match for all other classes, so do not require the response to repeat
            # capability metadata before accepting the devices.
            if candidates:
                matched_filters.append(capability)
                rows.extend(candidates)

        rows = self._dedupe_rows(rows)
        if rows:
            combined = self._combined_result(spec, source_results, rows)
            return combined, rows, {
                "classification_complete": True,
                "method": "capability-filter",
                "capability_filters": list(filters),
                "matched_filters": matched_filters,
                "selected_count": self._selected_count(source_results),
                "type_label": " / ".join(matched_filters[:2]) or spec.title.rstrip("s"),
            }

        # A capability spelling difference or an older MCP build must not produce a
        # false zero. Fetch one lightweight all-device summary and classify common
        # types from live currentStates and labels.
        summary = await self._summary_devices()
        source_results.append(summary)
        summary_rows = self._device_rows(summary.data)
        locally_matched = [
            item for item in summary_rows if self._matches_type(spec, item)
        ]
        locally_matched = self._dedupe_rows(locally_matched)
        if locally_matched:
            combined = self._combined_result(spec, source_results, locally_matched)
            return combined, locally_matched, {
                "classification_complete": True,
                "method": "summary-live-state-fallback",
                "capability_filters": list(filters),
                "selected_count": len(summary_rows),
                "type_label": spec.title.rstrip("s"),
            }

        # Capability-filtered zero is authoritative when the calls succeeded. For
        # classes without a standard capability and without usable summary evidence,
        # report unknown rather than claiming zero.
        complete = bool(filters) and all(not result.is_error for result in source_results[:-1])
        combined = self._combined_result(spec, source_results, [])
        return combined, [], {
            "classification_complete": complete,
            "method": "capability-filter-zero" if complete else "insufficient-evidence",
            "capability_filters": list(filters),
            "selected_count": len(summary_rows),
            "type_label": spec.title.rstrip("s"),
        }

    async def _capability_devices(
        self,
        capability: str,
        *,
        detailed: bool,
    ) -> MCPToolResult:
        fields = _DETAILED_FIELDS if detailed else _SUMMARY_FIELDS
        result = await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": detailed,
                "format": "detailed" if detailed else "summary",
                "capabilityFilter": capability,
                "fields": list(fields),
            },
        )
        if result.is_error:
            raise MCPError(
                result.text or f"Device lookup for capability {capability} failed"
            )
        return result

    async def _summary_devices(self) -> MCPToolResult:
        result = await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": list(_SUMMARY_FIELDS),
            },
        )
        if result.is_error:
            raise MCPError(result.text or "Device summary lookup failed")
        return result

    @staticmethod
    def _selected_count(results: list[MCPToolResult]) -> int | None:
        counts: list[int] = []
        for result in results:
            data = result.data
            if not isinstance(data, dict):
                continue
            for key in ("unfilteredTotal", "total", "count"):
                value = data.get(key)
                if isinstance(value, (int, float)):
                    counts.append(int(value))
                    break
        return max(counts) if counts else None

    @staticmethod
    def _combined_result(
        spec: DeviceTypeSpec,
        results: list[MCPToolResult],
        rows: list[dict[str, Any]],
    ) -> MCPToolResult:
        return MCPToolResult(
            name="hub_list_devices",
            arguments={"deviceType": spec.key},
            raw={
                "sources": [
                    {
                        "name": result.name,
                        "arguments": result.arguments,
                        "is_error": result.is_error,
                    }
                    for result in results
                ]
            },
            text="",
            data={
                "devices": rows,
                "count": len(rows),
                "sourceCalls": len(results),
            },
            is_error=False,
        )


__all__ = ["FastFallbackRouter"]

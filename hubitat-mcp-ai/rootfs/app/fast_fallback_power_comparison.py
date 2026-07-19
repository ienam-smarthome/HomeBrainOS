from __future__ import annotations

import re
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_multi_control import FastFallbackRouter as MultiControlFastFallbackRouter
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, safe_debug


_POWER_COMPARISON_TERMS = (
    "most power",
    "highest power",
    "most watts",
    "highest watts",
    "highest wattage",
    "biggest power draw",
    "largest power draw",
    "using the most",
    "drawing the most",
    "consuming the most",
)

_POWER_ATTRIBUTE_KEYS = {
    "power",
    "currentpower",
    "activepower",
    "instantaneouspower",
    "powerconsumption",
    "loadpower",
}

_AGGREGATE_POWER_TERMS = (
    "octopus live meter",
    "whole home",
    "whole house",
    "whole-home",
    "whole-house",
    "house power",
    "home power",
    "smart meter",
    "grid power",
    "total power",
)


def is_power_comparison_query(query: str) -> bool:
    q = _normalise(query).strip(" .!?")
    if not q:
        return False
    if any(term in q for term in _POWER_COMPARISON_TERMS):
        return "power" in q or "watt" in q or any(
            word in q for word in ("using", "drawing", "consuming")
        )
    return bool(
        re.search(
            r"\b(?:which|what)\s+(?:device|appliance|socket|outlet|plug)\b.*"
            r"\b(?:most|highest|largest|biggest)\b.*\b(?:power|watts?|wattage)\b",
            q,
        )
    )


def _normalise_attribute_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _raw_value_and_unit(raw: Any, unit_hint: Any = None) -> tuple[Any, str]:
    unit = str(unit_hint or "").strip()
    value = raw
    if isinstance(raw, dict):
        value = raw.get("currentValue")
        if value in (None, ""):
            value = raw.get("value")
        if value in (None, ""):
            value = raw.get("currentState")
        unit = str(raw.get("unit") or raw.get("units") or unit).strip()
    return value, unit


def _watts(value: Any, unit: str = "") -> float | None:
    value, nested_unit = _raw_value_and_unit(value, unit)
    unit = nested_unit or unit
    if value in (None, "") or isinstance(value, bool):
        return None

    text = str(value).strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))

    unit_text = str(unit or "").strip().lower()
    if not unit_text:
        suffix = re.search(r"([a-zA-Zµμ]+)\s*$", text)
        unit_text = suffix.group(1).lower() if suffix else "w"

    if unit_text in {"kw", "kilowatt", "kilowatts"}:
        number *= 1000.0
    elif unit_text in {"mw", "milliwatt", "milliwatts"}:
        number /= 1000.0
    elif unit_text in {"µw", "μw", "uw", "microwatt", "microwatts"}:
        number /= 1_000_000.0
    elif unit_text not in {"w", "watt", "watts", ""}:
        # Do not reinterpret energy, current, voltage or percentage attributes as
        # instantaneous power merely because they contain a number.
        return None

    if not (-1_000_000.0 < number < 1_000_000.0):
        return None
    return number


def power_reading(item: dict[str, Any]) -> tuple[float, str] | None:
    """Return one instantaneous power reading in watts and its source attribute."""

    for container_key in ("currentStates", "state", "states", "attributes"):
        container = item.get(container_key)
        if isinstance(container, dict):
            for key, raw in container.items():
                normalised = _normalise_attribute_name(key)
                if normalised not in _POWER_ATTRIBUTE_KEYS:
                    continue
                value, unit = _raw_value_and_unit(raw)
                watts = _watts(value, unit)
                if watts is not None:
                    return watts, str(key)
        elif isinstance(container, list):
            for entry in container:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or entry.get("attribute") or entry.get("key")
                normalised = _normalise_attribute_name(name)
                if normalised not in _POWER_ATTRIBUTE_KEYS:
                    continue
                value, unit = _raw_value_and_unit(entry)
                watts = _watts(value, unit)
                if watts is not None:
                    return watts, str(name)

    for key, raw in item.items():
        if _normalise_attribute_name(key) not in _POWER_ATTRIBUTE_KEYS:
            continue
        value, unit = _raw_value_and_unit(raw)
        watts = _watts(value, unit)
        if watts is not None:
            return watts, str(key)
    return None


def is_aggregate_power_meter(item: dict[str, Any]) -> bool:
    text = _normalise(
        " ".join(
            str(item.get(key) or "")
            for key in ("label", "name", "displayName", "type", "deviceType")
        )
    )
    return any(term in text for term in _AGGREGATE_POWER_TERMS)


def format_watts(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1000:
        shown = f"{value / 1000.0:.2f}".rstrip("0").rstrip(".")
        return f"{shown} kW"
    if absolute >= 100:
        return f"{value:.0f} W"
    shown = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{shown} W"


class FastFallbackRouter(MultiControlFastFallbackRouter):
    """Final router with fresh, deterministic instantaneous-power ranking."""

    async def answer(self, query: str) -> dict[str, Any]:
        if is_power_comparison_query(query):
            return await self._power_comparison()
        return await super().answer(query)

    async def _fresh_detailed_power_devices(self) -> MCPToolResult:
        index = getattr(self, "device_index", None)
        if index is not None:
            broker = getattr(index, "client", None)
            invalidate = getattr(broker, "invalidate", None)
            if callable(invalidate):
                await invalidate("devices")
            else:
                await index.invalidate()
            result = await index.capability_result(
                "Power Meter",
                detailed=True,
                force=True,
            )
        else:
            result = await self._capability_devices("Power Meter", detailed=True)

        if result.is_error:
            raise MCPError(result.text or "Detailed Power Meter lookup failed")
        return result

    async def _fallback_detailed_devices(self) -> MCPToolResult | None:
        index = getattr(self, "device_index", None)
        if index is not None:
            result = await index.metadata_result(force=True)
            if result.is_error:
                return None
            return result

        result = await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": True,
                "format": "detailed",
                "fields": [
                    "id",
                    "name",
                    "label",
                    "room",
                    "attributes",
                    "disabled",
                    "lastActivity",
                ],
            },
        )
        return None if result.is_error else result

    async def _power_comparison(self) -> dict[str, Any]:
        result = await self._fresh_detailed_power_devices()
        rows = self._device_rows(result.data)
        fallback_used = False

        readings = self._power_rows(rows)
        if not readings:
            fallback = await self._fallback_detailed_devices()
            if fallback is not None:
                fallback_rows = self._device_rows(fallback.data)
                fallback_readings = self._power_rows(fallback_rows)
                if fallback_readings:
                    result = fallback
                    rows = fallback_rows
                    readings = fallback_readings
                    fallback_used = True

        individual = sorted(
            (item for item in readings if not item["aggregate"]),
            key=lambda item: (-item["watts"], item["label"].lower()),
        )
        aggregate = sorted(
            (item for item in readings if item["aggregate"]),
            key=lambda item: (-item["watts"], item["label"].lower()),
        )

        if individual:
            winner = individual[0]
            message = (
                f"{winner['label']} is currently using the most power at "
                f"{format_watts(winner['watts'])}."
            )
            if len(individual) > 1:
                runners = ", ".join(
                    f"{item['label']} {format_watts(item['watts'])}"
                    for item in individual[1:4]
                )
                if runners:
                    message += f" Next highest: {runners}."
            if aggregate:
                meter = aggregate[0]
                message += (
                    f" The whole-home meter is reporting {format_watts(meter['watts'])}; "
                    "it is shown separately because it is not an individual device load."
                )
            success = True
            title = "Highest current power use"
            subtitle = f"{len(individual)} individual live reading{'' if len(individual) == 1 else 's'}"
        elif aggregate:
            meter = aggregate[0]
            message = (
                f"The whole-home meter is reporting {format_watts(meter['watts'])}, but no "
                "individual selected device returned a current numeric Power Meter reading."
            )
            success = True
            title = "Whole-home power only"
            subtitle = "No individual live readings"
        else:
            message = (
                f"I found {len(rows)} selected Power Meter device"
                f"{'' if len(rows) == 1 else 's'}, but none returned a current numeric power "
                "value in the detailed MCP attributes. Check that the metering devices expose "
                "the standard Power Meter `power` attribute."
            )
            success = False
            title = "Current power unavailable"
            subtitle = "Detailed Power Meter read returned no numeric watts"

        ranked = individual[:8]
        items = [
            {
                "icon": "⚡",
                "title": item["label"],
                "value": format_watts(item["watts"]),
                "subtitle": item["room"],
                "tone": "warning" if index == 0 and item["watts"] > 0 else None,
            }
            for index, item in enumerate(ranked)
        ]
        items.extend(
            {
                "icon": "🏠",
                "title": item["label"],
                "value": format_watts(item["watts"]),
                "subtitle": "Whole-home aggregate · not ranked as a device",
            }
            for item in aggregate[:1]
        )

        display = display_payload(
            "power-comparison",
            title,
            subtitle=subtitle,
            metrics=[
                {"label": "Power meters found", "value": str(len(rows)), "icon": "🔌"},
                {"label": "Numeric readings", "value": str(len(readings)), "icon": "📡"},
                {
                    "label": "Highest device",
                    "value": format_watts(individual[0]["watts"]) if individual else "Unavailable",
                    "icon": "⚡",
                },
            ],
            items=items,
            note=(
                "Values come from a fresh detailed Hubitat Power Meter capability read. "
                "Energy totals in kWh are not compared with instantaneous power in W. "
                "Whole-home meters are displayed separately from individual devices."
            ),
        )
        response = self._response(
            message,
            "fallback-current-power-comparison",
            success,
            result,
        )
        response.update(
            {
                "display": display,
                "power_readings": readings,
                "individual_reading_count": len(individual),
                "aggregate_reading_count": len(aggregate),
                "technical": safe_debug(
                    {
                        "capability_filter": "Power Meter",
                        "detailed": True,
                        "fallback_all_detailed_used": fallback_used,
                        "power_meter_rows": rows,
                        "normalised_readings": readings,
                    }
                ),
            }
        )
        return response

    def _power_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        readings: list[dict[str, Any]] = []
        for item in rows:
            reading = power_reading(item)
            if reading is None:
                continue
            watts, source_attribute = reading
            # Negative whole-home values normally mean export rather than consumption.
            # Preserve them for transparency but do not rank negative individual loads.
            if watts < 0 and not is_aggregate_power_meter(item):
                continue
            readings.append(
                {
                    "id": _device_id(item),
                    "label": _label(item) or f"Device {_device_id(item)}",
                    "room": self._room_name(item) or "No room assigned",
                    "watts": watts,
                    "shown": format_watts(watts),
                    "source_attribute": source_attribute,
                    "aggregate": is_aggregate_power_meter(item),
                }
            )
        return readings


__all__ = [
    "FastFallbackRouter",
    "format_watts",
    "is_aggregate_power_meter",
    "is_power_comparison_query",
    "power_reading",
]

from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from fallback_router import _device_id, _label, _normalise
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, safe_debug
from semantic_read_intent import SemanticReadIntent


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    key: str
    title: str
    capability: str
    attribute_names: tuple[str, ...]
    unit: str
    icon: str
    aggregate_mode: str = "average"
    aggregate_terms: tuple[str, ...] = ()


_SPECS: dict[str, MeasurementSpec] = {
    "power": MeasurementSpec(
        "power",
        "Current power",
        "Power Meter",
        (
            "power",
            "currentpower",
            "activepower",
            "instantaneouspower",
            "powerconsumption",
            "loadpower",
        ),
        "W",
        "⚡",
        aggregate_mode="sum",
        aggregate_terms=(
            "octopus live meter",
            "whole home",
            "whole house",
            "whole-home",
            "whole-house",
            "smart meter",
            "grid power",
            "total power",
        ),
    ),
    "temperature": MeasurementSpec(
        "temperature",
        "Temperature",
        "Temperature Measurement",
        ("temperature",),
        "°C",
        "🌡️",
    ),
    "humidity": MeasurementSpec(
        "humidity",
        "Humidity",
        "Relative Humidity Measurement",
        ("humidity", "relativehumidity"),
        "%",
        "💧",
    ),
    "battery": MeasurementSpec(
        "battery",
        "Battery level",
        "Battery",
        ("battery", "batterylevel"),
        "%",
        "🔋",
    ),
    "illuminance": MeasurementSpec(
        "illuminance",
        "Illuminance",
        "Illuminance Measurement",
        ("illuminance", "lux"),
        "lx",
        "☀️",
    ),
    "energy": MeasurementSpec(
        "energy",
        "Energy",
        "Energy Meter",
        ("energy", "energyconsumption", "totalenergy"),
        "kWh",
        "📈",
        aggregate_mode="sum",
        aggregate_terms=(
            "octopus live meter",
            "whole home",
            "whole house",
            "whole-home",
            "whole-house",
            "smart meter",
            "grid energy",
            "total energy",
        ),
    ),
}


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


def _number_and_unit(value: Any, unit: str = "") -> tuple[float, str] | None:
    value, nested_unit = _raw_value_and_unit(value, unit)
    if value in (None, "") or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    unit_text = str(nested_unit or unit or "").strip().lower()
    if not unit_text:
        suffix = re.search(r"([a-zA-Z°%µμ]+)\s*$", text)
        unit_text = suffix.group(1).lower() if suffix else ""
    return number, unit_text


def _canonical_value(spec: MeasurementSpec, value: Any, unit: str = "") -> float | None:
    parsed = _number_and_unit(value, unit)
    if parsed is None:
        return None
    number, unit_text = parsed

    if spec.key == "power":
        if unit_text in {"kw", "kilowatt", "kilowatts"}:
            number *= 1000.0
        elif unit_text in {"mw", "milliwatt", "milliwatts"}:
            number /= 1000.0
        elif unit_text in {"µw", "μw", "uw", "microwatt", "microwatts"}:
            number /= 1_000_000.0
        elif unit_text not in {"", "w", "watt", "watts"}:
            return None
    elif spec.key == "energy":
        if unit_text in {"wh", "watt-hour", "watt-hours"}:
            number /= 1000.0
        elif unit_text in {"mwh", "megawatt-hour", "megawatt-hours"}:
            number *= 1000.0
        elif unit_text not in {"", "kwh", "kilowatt-hour", "kilowatt-hours"}:
            return None
    elif spec.key == "temperature":
        if unit_text in {"f", "°f", "fahrenheit"}:
            number = (number - 32.0) * 5.0 / 9.0
        elif unit_text not in {"", "c", "°c", "celsius"}:
            return None
    elif spec.key in {"humidity", "battery"}:
        if unit_text not in {"", "%", "percent", "percentage"}:
            return None
    elif spec.key == "illuminance":
        if unit_text not in {"", "lx", "lux"}:
            return None

    if not (-10_000_000.0 < number < 10_000_000.0):
        return None
    return number


def measurement_reading(
    item: dict[str, Any],
    spec: MeasurementSpec,
) -> tuple[float, str] | None:
    aliases = set(spec.attribute_names)
    for container_key in ("currentStates", "state", "states", "attributes"):
        container = item.get(container_key)
        if isinstance(container, dict):
            entries = container.items()
            for key, raw in entries:
                if _normalise_attribute_name(key) not in aliases:
                    continue
                value, unit = _raw_value_and_unit(raw)
                number = _canonical_value(spec, value, unit)
                if number is not None:
                    return number, str(key)
        elif isinstance(container, list):
            for entry in container:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or entry.get("attribute") or entry.get("key")
                if _normalise_attribute_name(name) not in aliases:
                    continue
                value, unit = _raw_value_and_unit(entry)
                number = _canonical_value(spec, value, unit)
                if number is not None:
                    return number, str(name)

    for key, raw in item.items():
        if _normalise_attribute_name(key) not in aliases:
            continue
        value, unit = _raw_value_and_unit(raw)
        number = _canonical_value(spec, value, unit)
        if number is not None:
            return number, str(key)
    return None


def format_measurement(spec: MeasurementSpec, value: float) -> str:
    if spec.key == "power":
        if abs(value) >= 1000:
            shown = f"{value / 1000.0:.2f}".rstrip("0").rstrip(".")
            return f"{shown} kW"
        if abs(value) >= 100:
            return f"{value:.0f} W"
        shown = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{shown} W"
    if spec.key == "energy":
        if abs(value) >= 1000:
            shown = f"{value / 1000.0:.2f}".rstrip("0").rstrip(".")
            return f"{shown} MWh"
        shown = f"{value:.3f}".rstrip("0").rstrip(".")
        return f"{shown} kWh"
    if spec.key == "temperature":
        return f"{value:.1f}°C"
    if spec.key in {"humidity", "battery"}:
        return f"{value:.0f}%"
    if spec.key == "illuminance":
        return f"{value:.0f} lx"
    return f"{value:g} {spec.unit}".strip()


def _is_aggregate_meter(item: dict[str, Any], spec: MeasurementSpec) -> bool:
    if not spec.aggregate_terms:
        return False
    text = _normalise(
        " ".join(
            str(item.get(key) or "")
            for key in ("label", "name", "displayName", "type", "deviceType")
        )
    )
    return any(term in text for term in spec.aggregate_terms)


def _matches_name(value: str, requested: tuple[str, ...]) -> bool:
    normalised = _normalise(value)
    if not requested:
        return True
    targets = tuple(_normalise(item) for item in requested if item)
    return any(normalised == target or target in normalised or normalised in target for target in targets)


class SemanticMetricComparisonExecutor:
    """Execute validated AI read intents using authoritative Hubitat measurements."""

    def __init__(self, router: Any) -> None:
        self.router = router

    async def execute(
        self,
        intent: SemanticReadIntent,
        *,
        query: str = "",
    ) -> dict[str, Any]:
        spec = _SPECS.get(intent.metric)
        if spec is None:
            raise ValueError(f"Unsupported comparison metric: {intent.metric}")

        result = await self._fresh_capability_result(spec)
        rows = self.router._device_rows(result.data)
        readings = self._measurement_rows(rows, spec)
        fallback_used = False

        if not readings:
            fallback = await self._fallback_detailed_result()
            if fallback is not None:
                fallback_rows = self.router._device_rows(fallback.data)
                fallback_readings = self._measurement_rows(fallback_rows, spec)
                if fallback_readings:
                    result = fallback
                    rows = fallback_rows
                    readings = fallback_readings
                    fallback_used = True

        scoped = self._scope_rows(readings, intent)
        aggregate = [item for item in scoped if item["aggregate"]]
        individual = [item for item in scoped if not item["aggregate"]]
        entities = self._group_rows(individual, intent, spec)
        reverse = intent.operation != "min"
        entities.sort(
            key=lambda item: (
                -item["value"] if reverse else item["value"],
                item["label"].lower(),
            )
        )

        answer = self._build_response(
            intent,
            spec,
            result,
            rows,
            readings,
            entities,
            aggregate,
            fallback_used=fallback_used,
            query=query,
        )
        return answer

    async def _fresh_capability_result(self, spec: MeasurementSpec) -> MCPToolResult:
        index = getattr(self.router, "device_index", None)
        if index is not None:
            broker = getattr(index, "client", None)
            invalidate = getattr(broker, "invalidate", None)
            if callable(invalidate):
                await invalidate("devices")
            else:
                await index.invalidate()
            result = await index.capability_result(
                spec.capability,
                detailed=True,
                force=True,
            )
        else:
            result = await self.router._capability_devices(
                spec.capability,
                detailed=True,
            )
        if result.is_error:
            raise MCPError(result.text or f"Detailed {spec.capability} lookup failed")
        return result

    async def _fallback_detailed_result(self) -> MCPToolResult | None:
        index = getattr(self.router, "device_index", None)
        if index is not None:
            result = await index.metadata_result(force=True)
            return None if result.is_error else result
        result = await self.router._execute_catalog_tool(
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

    def _measurement_rows(
        self,
        rows: list[dict[str, Any]],
        spec: MeasurementSpec,
    ) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for item in rows:
            reading = measurement_reading(item, spec)
            if reading is None:
                continue
            value, source_attribute = reading
            aggregate = _is_aggregate_meter(item, spec)
            if spec.key == "power" and value < 0 and not aggregate:
                continue
            found.append(
                {
                    "id": _device_id(item),
                    "label": _label(item) or f"Device {_device_id(item)}",
                    "room": self.router._room_name(item) or "No room assigned",
                    "value": value,
                    "shown": format_measurement(spec, value),
                    "source_attribute": source_attribute,
                    "aggregate": aggregate,
                }
            )
        return found

    @staticmethod
    def _scope_rows(
        readings: list[dict[str, Any]],
        intent: SemanticReadIntent,
    ) -> list[dict[str, Any]]:
        rows = list(readings)
        if intent.scope_kind == "room" and intent.scope_name:
            target = _normalise(intent.scope_name)
            rows = [
                item
                for item in rows
                if target == _normalise(item["room"]) or target in _normalise(item["room"])
            ]
        if intent.scope_kind == "entities" and intent.entity_names:
            key = "room" if intent.group_by == "room" else "label"
            rows = [item for item in rows if _matches_name(item[key], intent.entity_names)]
        return rows

    @staticmethod
    def _group_rows(
        rows: list[dict[str, Any]],
        intent: SemanticReadIntent,
        spec: MeasurementSpec,
    ) -> list[dict[str, Any]]:
        if intent.group_by == "device":
            return [
                {
                    "label": item["label"],
                    "room": item["room"],
                    "value": item["value"],
                    "source_count": 1,
                    "device_ids": [item["id"]],
                }
                for item in rows
            ]

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in rows:
            grouped.setdefault(item["room"], []).append(item)
        entities: list[dict[str, Any]] = []
        for room, values in grouped.items():
            numbers = [float(item["value"]) for item in values]
            combined = sum(numbers) if spec.aggregate_mode == "sum" else fmean(numbers)
            entities.append(
                {
                    "label": room,
                    "room": room,
                    "value": combined,
                    "source_count": len(values),
                    "device_ids": [item["id"] for item in values],
                }
            )
        return entities

    def _build_response(
        self,
        intent: SemanticReadIntent,
        spec: MeasurementSpec,
        result: MCPToolResult,
        rows: list[dict[str, Any]],
        readings: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        aggregate: list[dict[str, Any]],
        *,
        fallback_used: bool,
        query: str,
    ) -> dict[str, Any]:
        noun = "room" if intent.group_by == "room" else "device"
        ranked = entities[: intent.top_n]
        operation_label = {
            "max": "highest",
            "min": "lowest",
            "rank": "ranked",
        }[intent.operation]

        if entities:
            winner = entities[0]
            if intent.operation == "rank":
                message = f"{spec.title} ranking:\n" + "\n".join(
                    f"{index}. {item['label']}: {format_measurement(spec, item['value'])}"
                    for index, item in enumerate(ranked, start=1)
                )
                title = f"{spec.title} ranking"
            else:
                message = (
                    f"{winner['label']} has the {operation_label} current {spec.title.lower()} "
                    f"at {format_measurement(spec, winner['value'])}."
                )
                runners = entities[1 : max(1, intent.top_n)]
                if runners:
                    message += " Next: " + ", ".join(
                        f"{item['label']} {format_measurement(spec, item['value'])}"
                        for item in runners
                    ) + "."
                title = f"{operation_label.title()} {spec.title.lower()}"

            if aggregate:
                meter = sorted(aggregate, key=lambda item: -item["value"])[0]
                message += (
                    f" The whole-home meter is {format_measurement(spec, meter['value'])}; "
                    f"it is shown separately and not ranked as an individual {noun}."
                )
            success = True
            subtitle = f"{len(entities)} {noun}{'' if len(entities) == 1 else 's'} with live readings"
        elif aggregate:
            meter = sorted(aggregate, key=lambda item: -item["value"])[0]
            message = (
                f"The whole-home meter is {format_measurement(spec, meter['value'])}, but no "
                f"individual selected {noun} returned a numeric {spec.title.lower()} reading."
            )
            title = f"Whole-home {spec.title.lower()} only"
            subtitle = f"No individual {noun} readings"
            success = True
        else:
            message = (
                f"I found {len(rows)} selected {spec.capability} device"
                f"{'' if len(rows) == 1 else 's'}, but none returned a current numeric "
                f"{spec.title.lower()} value for this comparison."
            )
            title = f"{spec.title} unavailable"
            subtitle = "No numeric live readings"
            success = False

        items = [
            {
                "icon": spec.icon,
                "title": item["label"],
                "value": format_measurement(spec, item["value"]),
                "subtitle": (
                    f"{item['source_count']} source readings"
                    if intent.group_by == "room"
                    else item["room"]
                ),
                "tone": "warning" if index == 0 and intent.operation != "min" else None,
            }
            for index, item in enumerate(ranked)
        ]
        items.extend(
            {
                "icon": "🏠",
                "title": item["label"],
                "value": format_measurement(spec, item["value"]),
                "subtitle": "Whole-home aggregate · not included in individual ranking",
            }
            for item in sorted(aggregate, key=lambda row: -row["value"])[:1]
        )

        display = display_payload(
            "semantic-metric-comparison",
            title,
            subtitle=subtitle,
            metrics=[
                {"label": "Metric", "value": spec.title, "icon": spec.icon},
                {"label": "Live readings", "value": str(len(readings)), "icon": "📡"},
                {"label": "Compared", "value": str(len(entities)), "icon": "⚖️"},
            ],
            items=items,
            note=(
                f"A local AI model interpreted the read-only question as {intent.metric}/{intent.operation}. "
                f"Python then fetched fresh detailed {spec.capability} evidence and calculated the result. "
                "The model did not choose or calculate the winning value."
            ),
        )
        response = self.router._response(
            message,
            f"semantic-{intent.metric}-{intent.operation}-{intent.group_by}",
            success,
            result,
        )
        response.update(
            {
                "display": display,
                "metric": intent.metric,
                "operation": intent.operation,
                "group_by": intent.group_by,
                "measurement_readings": readings,
                "ranked_entities": entities,
                "technical": safe_debug(
                    {
                        "query": query,
                        "capability_filter": spec.capability,
                        "detailed": True,
                        "fallback_all_detailed_used": fallback_used,
                        "capability_rows": rows,
                        "normalised_readings": readings,
                        "ranked_entities": entities,
                        "aggregate_readings": aggregate,
                    }
                ),
            }
        )
        return response


__all__ = [
    "MeasurementSpec",
    "SemanticMetricComparisonExecutor",
    "format_measurement",
    "measurement_reading",
]

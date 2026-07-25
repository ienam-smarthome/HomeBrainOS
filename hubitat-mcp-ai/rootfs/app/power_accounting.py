from __future__ import annotations

import re
from typing import Any

from control_focus_octopus_energy import (
    _device_rows,
    _display_value,
    _period_from_label,
)
from device_read_shapes import detailed_device_arguments
from fallback_router import _device_id, _label, _normalise
from presenter import display_payload, safe_debug
from semantic_metric_comparison import (
    _SPECS,
    _is_aggregate_meter,
    format_measurement,
    measurement_reading,
)


_ACCOUNTING_TERMS = (
    "unaccounted power",
    "power unaccounted",
    "unmonitored power",
    "unknown power",
    "power coverage",
    "energy coverage",
    "meter coverage",
    "compare whole house",
    "compare whole-house",
    "compare octopus",
    "whole house versus devices",
    "whole-house versus devices",
    "whole house vs devices",
    "whole-house vs devices",
    "difference between whole house",
    "difference between octopus",
    "why is my electricity usage high",
    "why is electricity usage high",
    "where is the rest of the power",
)


def is_power_accounting_query(query: str) -> bool:
    q = _normalise(str(query or "")).strip(" .!?")
    if not q:
        return False

    if any(term in q for term in _ACCOUNTING_TERMS):
        return True

    has_difference = any(
        term in q
        for term in (
            "difference",
            "gap",
            "missing",
            "unaccounted",
            "unmonitored",
            "unknown",
            "coverage",
        )
    )
    has_power = any(
        term in q
        for term in (
            "power",
            "electricity",
            "watt",
            "watts",
            "octopus",
            "whole house",
            "whole-house",
        )
    )
    return has_difference and has_power


def _number_from_display(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    match = re.search(
        r"([-+]?\d+(?:\.\d+)?)\s*(k?w)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    number = float(match.group(1))
    if match.group(2).lower() == "kw":
        number *= 1000.0
    return number


def _whole_house_power(
    rows: list[dict[str, Any]],
) -> tuple[float | None, dict[str, Any] | None]:
    candidates: list[tuple[float, dict[str, Any]]] = []

    for row in rows:
        label = _normalise(_label(row))
        period = _period_from_label(_label(row))

        if period != "power":
            continue
        if "octopus" not in label:
            continue

        value = _number_from_display(_display_value(row))
        if value is not None:
            candidates.append((value, row))

    if not candidates:
        return None, None

    # There should be one Octopus current-power display. Selecting the largest
    # numeric candidate is deterministic if duplicate aliases are exposed.
    candidates.sort(
        key=lambda item: (
            -item[0],
            _normalise(_label(item[1])),
        )
    )
    return candidates[0]


def _individual_power_readings(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    spec = _SPECS["power"]
    unique: dict[str, dict[str, Any]] = {}

    for row in rows:
        if bool(row.get("disabled")):
            continue
        if _is_aggregate_meter(row, spec):
            continue

        reading = measurement_reading(row, spec)
        if reading is None:
            continue

        value, attribute = reading
        key = (
            str(_device_id(row) or "").strip()
            or _normalise(_label(row))
        )
        if not key:
            continue

        unique[key] = {
            "id": str(_device_id(row) or ""),
            "label": _label(row) or "Unknown device",
            "room": row.get("room"),
            "value": float(value),
            "attribute": attribute,
        }

    return sorted(
        unique.values(),
        key=lambda item: (
            -float(item["value"]),
            str(item["label"]).lower(),
        ),
    )


class PowerAccountingService:
    def __init__(self, application: Any) -> None:
        self.application = application

    async def answer(self, query: str) -> dict[str, Any]:
        desired = detailed_device_arguments()
        supported = getattr(
            self.application.mcp,
            "supported_arguments",
            None,
        )
        arguments = (
            await supported("hub_list_devices", desired)
            if callable(supported)
            else desired
        )
        result = await self.application.mcp.call_tool(
            "hub_list_devices",
            arguments,
        )

        if result.is_error:
            return {
                "success": False,
                "route": "mcp-power-accounting",
                "intent": "verified-power-accounting",
                "message": (
                    "The live Hubitat device snapshot could not be read, so "
                    "whole-house power coverage could not be calculated."
                ),
                "model": None,
                "technical": safe_debug(
                    {
                        "query": query,
                        "error": result.text,
                    }
                ),
            }

        rows = _device_rows(result.data)
        whole_house_w, meter_row = _whole_house_power(rows)
        readings = _individual_power_readings(rows)

        active = [
            item
            for item in readings
            if float(item["value"]) > 0.05
        ]
        idle = [
            item
            for item in readings
            if float(item["value"]) <= 0.05
        ]
        monitored_w = sum(float(item["value"]) for item in active)

        if whole_house_w is None:
            message = (
                "The individual monitored devices total "
                f"{format_measurement(_SPECS['power'], monitored_w)}, "
                "but no live Octopus whole-house power value was available."
            )
            coverage = None
            difference_w = None
        else:
            difference_w = whole_house_w - monitored_w
            coverage = (
                monitored_w / whole_house_w * 100.0
                if whole_house_w > 0
                else None
            )

            if difference_w >= 0:
                message = (
                    f"Whole-house power is "
                    f"{format_measurement(_SPECS['power'], whole_house_w)}. "
                    f"Individually monitored devices account for "
                    f"{format_measurement(_SPECS['power'], monitored_w)}, "
                    f"leaving "
                    f"{format_measurement(_SPECS['power'], difference_w)} "
                    "unaccounted for."
                )
            else:
                message = (
                    f"Whole-house power is "
                    f"{format_measurement(_SPECS['power'], whole_house_w)}, "
                    f"while individual device readings total "
                    f"{format_measurement(_SPECS['power'], monitored_w)}. "
                    f"The device total is "
                    f"{format_measurement(_SPECS['power'], abs(difference_w))} "
                    "higher, which usually indicates overlapping meters or "
                    "readings captured at slightly different moments."
                )

            if coverage is not None:
                message += f" Monitoring coverage is {coverage:.1f}%."

        top = active[:5]
        if top:
            message += "\n\nLargest monitored loads:\n" + "\n".join(
                f"{index}. {item['label']}: "
                f"{format_measurement(_SPECS['power'], float(item['value']))}"
                for index, item in enumerate(top, start=1)
            )

        metrics = [
            {
                "label": "Whole house",
                "value": (
                    format_measurement(
                        _SPECS["power"],
                        whole_house_w,
                    )
                    if whole_house_w is not None
                    else "Unavailable"
                ),
                "icon": "🏠",
            },
            {
                "label": "Monitored devices",
                "value": format_measurement(
                    _SPECS["power"],
                    monitored_w,
                ),
                "icon": "🔌",
            },
            {
                "label": "Unaccounted",
                "value": (
                    format_measurement(
                        _SPECS["power"],
                        difference_w,
                    )
                    if difference_w is not None
                    else "Unavailable"
                ),
                "icon": "❓",
            },
            {
                "label": "Coverage",
                "value": (
                    f"{coverage:.1f}%"
                    if coverage is not None
                    else "Unavailable"
                ),
                "icon": "📊",
            },
        ]

        display = display_payload(
            "power-accounting",
            "Whole-house power accounting",
            subtitle=(
                f"{len(active)} active and {len(idle)} idle monitored readings"
            ),
            metrics=metrics,
            items=[
                {
                    "icon": "⚡",
                    "title": item["label"],
                    "value": format_measurement(
                        _SPECS["power"],
                        float(item["value"]),
                    ),
                    "subtitle": str(
                        item.get("room") or "No room assigned"
                    ),
                    "tone": "warning" if index == 0 else None,
                }
                for index, item in enumerate(active[:10])
            ],
            note=(
                "The Octopus current-power display is treated as the "
                "whole-house meter and is not added to the individual-device "
                "total. Differences can include unmonitored circuits, standby "
                "loads and small timing differences between device updates."
            ),
        )
        display["summary"] = message

        return {
            "success": whole_house_w is not None,
            "route": "mcp-power-accounting",
            "intent": "verified-power-accounting",
            "message": message,
            "display": display,
            "whole_house_power_w": whole_house_w,
            "whole_house_meter": (
                {
                    "id": str(_device_id(meter_row) or ""),
                    "label": _label(meter_row),
                }
                if meter_row is not None
                else None
            ),
            "monitored_device_power_w": monitored_w,
            "unaccounted_power_w": difference_w,
            "coverage_percent": coverage,
            "active_reading_count": len(active),
            "idle_reading_count": len(idle),
            "active_power_readings": active,
            "model": None,
            "answered_by": (
                "Deterministic Octopus and Hubitat power accounting"
            ),
            "technical": safe_debug(
                {
                    "query": query,
                    "whole_house_power_w": whole_house_w,
                    "monitored_device_power_w": monitored_w,
                    "unaccounted_power_w": difference_w,
                    "coverage_percent": coverage,
                    "active_readings": active,
                    "idle_readings": idle,
                    "meter_label": (
                        _label(meter_row)
                        if meter_row is not None
                        else None
                    ),
                }
            ),
        }


__all__ = [
    "PowerAccountingService",
    "is_power_accounting_query",
]

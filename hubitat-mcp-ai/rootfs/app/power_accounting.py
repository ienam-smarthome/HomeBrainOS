from __future__ import annotations

import re
from datetime import datetime, timezone
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

    # Live power accounting compares the current whole-house value with current
    # device readings. Historical usage, bills and energy totals need a
    # different evidence route.
    historical_terms = (
        "today",
        "yesterday",
        "this week",
        "last week",
        "this month",
        "last month",
        "bill",
        "billing",
        "kwh",
        "kilowatt hour",
        "kilowatt-hour",
    )
    if any(term in q for term in historical_terms):
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


def _parse_activity(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None

    if text.isdigit():
        return _parse_activity(int(text))

    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        parsed = None

    if parsed is None:
        for pattern in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
        ):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _activity_text(row: dict[str, Any]) -> str | None:
    value = (
        row.get("lastActivity")
        or row.get("last_activity")
        or row.get("lastUpdated")
        or row.get("last_updated")
    )
    return str(value).strip() if value not in (None, "") else None


def _format_accounting_power(value: float) -> str:
    number = float(value)
    if abs(number) >= 1000:
        shown = f"{number / 1000.0:.2f}".rstrip("0").rstrip(".")
        return f"{shown} kW"
    if number.is_integer():
        return f"{number:.0f} W"
    return f"{number:.1f} W"


def _whole_house_power(
    rows: list[dict[str, Any]],
) -> tuple[
    float | None,
    dict[str, Any] | None,
    str | None,
]:
    candidates: list[
        tuple[
            tuple[int, int, int, float, str],
            float,
            dict[str, Any],
            str,
        ]
    ] = []
    spec = _SPECS["power"]

    for row in rows:
        label = _normalise(_label(row))
        period = _period_from_label(_label(row))

        if period != "power" or "octopus" not in label:
            continue

        structured = measurement_reading(row, spec)
        if structured is not None:
            value = float(structured[0])
            source = "structured-power-attribute"
            structured_score = 1
        else:
            value = _number_from_display(_display_value(row))
            source = "display-text-fallback"
            structured_score = 0

        if value is None:
            continue

        activity = _parse_activity(_activity_text(row))
        activity_score = (
            activity.timestamp()
            if activity is not None
            else float("-inf")
        )
        exact_label = int(
            label == "octopus meter current power"
            or label == "octopus live meter display power"
        )
        enabled = int(not bool(row.get("disabled")))

        # Prefer exact current-power labels, enabled rows, structured evidence
        # and the newest timestamp. The numeric value is deliberately not used
        # as a quality score.
        score = (
            exact_label,
            enabled,
            structured_score,
            activity_score,
            label,
        )
        candidates.append((score, value, row, source))

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    _score, value, row, source = candidates[0]
    return value, row, source

def _individual_power_readings(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    spec = _SPECS["power"]
    unique: dict[str, dict[str, Any]] = {}

    for row in rows:
        if bool(row.get("disabled")):
            continue

        label = _normalise(_label(row))
        period = _period_from_label(_label(row))

        # Exclude every whole-house Octopus current-power representation,
        # including structured power attributes that the generic aggregate
        # detector may not identify.
        if "octopus" in label and period == "power":
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

        candidate = {
            "id": str(_device_id(row) or ""),
            "label": _label(row) or "Unknown device",
            "room": row.get("room"),
            "value": float(value),
            "attribute": attribute,
            "value_source": f"structured-{attribute}",
            "last_activity": _activity_text(row),
        }

        existing = unique.get(key)
        if existing is None:
            unique[key] = candidate
            continue

        existing_time = _parse_activity(
            existing.get("last_activity")
        )
        candidate_time = _parse_activity(
            candidate.get("last_activity")
        )

        if candidate_time is not None and (
            existing_time is None
            or candidate_time > existing_time
        ):
            unique[key] = candidate

    return sorted(
        unique.values(),
        key=lambda item: (
            -float(item["value"]),
            str(item["label"]).lower(),
        ),
    )


def _reading_quality(
    meter_row: dict[str, Any] | None,
    readings: list[dict[str, Any]],
) -> dict[str, Any]:
    timestamps: list[tuple[str, datetime]] = []

    if meter_row is not None:
        parsed = _parse_activity(_activity_text(meter_row))
        if parsed is not None:
            timestamps.append(("whole_house_meter", parsed))

    for item in readings:
        parsed = _parse_activity(item.get("last_activity"))
        if parsed is not None:
            timestamps.append((str(item.get("label") or "device"), parsed))

    if len(timestamps) < 2:
        return {
            "quality": "unknown",
            "timestamp_count": len(timestamps),
            "maximum_skew_seconds": None,
            "newest_activity": (
                timestamps[0][1].isoformat()
                if timestamps
                else None
            ),
            "oldest_activity": (
                timestamps[0][1].isoformat()
                if timestamps
                else None
            ),
        }

    values = [item[1] for item in timestamps]
    newest = max(values)
    oldest = min(values)
    skew = max(0.0, (newest - oldest).total_seconds())

    if skew <= 30:
        quality = "good"
    elif skew <= 120:
        quality = "mixed"
    else:
        quality = "stale"

    return {
        "quality": quality,
        "timestamp_count": len(timestamps),
        "maximum_skew_seconds": skew,
        "newest_activity": newest.isoformat(),
        "oldest_activity": oldest.isoformat(),
    }


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
        whole_house_w, meter_row, meter_value_source = (
            _whole_house_power(rows)
        )
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
        reading_quality = _reading_quality(meter_row, readings)

        if whole_house_w is None:
            message = (
                "The individual monitored devices total "
                f"{_format_accounting_power(monitored_w)}, "
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
                    f"{_format_accounting_power(whole_house_w)}. "
                    f"Individually monitored devices account for "
                    f"{_format_accounting_power(monitored_w)}, "
                    f"leaving "
                    f"{_format_accounting_power(difference_w)} "
                    "unaccounted for."
                )
            else:
                message = (
                    f"Whole-house power is "
                    f"{_format_accounting_power(whole_house_w)}, "
                    f"while individual device readings total "
                    f"{_format_accounting_power(monitored_w)}. "
                    f"The device total is "
                    f"{_format_accounting_power(abs(difference_w))} "
                    "higher, which usually indicates overlapping meters or "
                    "readings captured at slightly different moments."
                )

            if coverage is not None:
                message += f" Monitoring coverage is {coverage:.1f}%."

        quality_name = str(
            reading_quality.get("quality") or "unknown"
        ).title()
        skew_seconds = reading_quality.get(
            "maximum_skew_seconds"
        )
        if skew_seconds is None:
            message += (
                " Reading timestamp quality is unknown because the "
                "gateway did not expose enough activity timestamps."
            )
        else:
            message += (
                f" Reading timestamp quality is {quality_name} "
                f"with a maximum skew of {skew_seconds:.0f} seconds."
            )

        top = active[:5]
        if top:
            message += "\n\nLargest monitored loads:\n" + "\n".join(
                f"{index}. {item['label']}: "
                f"{_format_accounting_power(float(item['value']))}"
                for index, item in enumerate(top, start=1)
            )

        metrics = [
            {
                "label": "Whole house",
                "value": (
                    _format_accounting_power(
                        whole_house_w,
                    )
                    if whole_house_w is not None
                    else "Unavailable"
                ),
                "icon": "🏠",
            },
            {
                "label": "Monitored devices",
                "value": _format_accounting_power(
                    monitored_w,
                ),
                "icon": "🔌",
            },
            {
                "label": "Unaccounted",
                "value": (
                    _format_accounting_power(
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
                    "value": _format_accounting_power(
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
            "whole_house_value_source": meter_value_source,
            "reading_quality": reading_quality,
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
                    "whole_house_value_source": meter_value_source,
                    "reading_quality": reading_quality,
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

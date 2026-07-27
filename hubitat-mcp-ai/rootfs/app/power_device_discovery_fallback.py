from __future__ import annotations

import asyncio
from typing import Any

import power_accounting as _power


_EXPLICIT_POWER_TERMS = (
    "power meter",
    "powermeter",
    "power measurement",
    "powermeasurement",
    "power attribute",
    "powerattribute",
    "capability power",
    "current power",
    "metering plug",
    "power monitoring",
)

_METERING_DEVICE_TERMS = (
    "tasmota",
    "mqtt",
    "smart plug",
    "smartplug",
    "metering plug",
    "power plug",
    "socket",
    "outlet",
    "innr sp",
    "tuya zigbee metering",
)

_APPLIANCE_TERMS = (
    "fridge",
    "freezer",
    "washing machine",
    "washer",
    "dryer",
    "dishwasher",
    "dehumidifier",
    "microwave",
    "kettle",
    "iron",
    "television",
    " tv",
    "computer",
    " pc",
    "mesh",
    "boiler",
    "heater",
    "fan",
)

_EXCLUDED_TERMS = (
    "block ",
    "cudy ",
    "motion",
    "contact",
    "temperature",
    "humidity",
    "illuminance",
    "lux",
    "battery",
    "presence",
)


def _searchable(row: dict[str, Any]) -> str:
    return _power._normalise(
        " ".join(
            str(row.get(key) or "")
            for key in (
                "label",
                "name",
                "displayName",
                "deviceType",
                "type",
                "driverType",
                "category",
                "capabilities",
                "attributes",
                "currentStates",
            )
        )
    )


def power_candidate_score(row: dict[str, Any]) -> int:
    if bool(row.get("disabled")):
        return 0

    label = _power._normalise(_power._label(row))
    text = _searchable(row)

    if "octopus" in label and ("power" in label or "current" in label):
        return 1000

    reading = _power.measurement_reading(row, _power._SPECS["power"])
    if reading is not None:
        return 900

    score = 0
    if any(term in text for term in _EXPLICIT_POWER_TERMS):
        score = max(score, 800)
    if any(term in text for term in _METERING_DEVICE_TERMS):
        score = max(score, 500)
    if any(term in f" {label}" for term in _APPLIANCE_TERMS):
        score = max(score, 250)

    if any(term in f" {label}" for term in _EXCLUDED_TERMS) and score < 800:
        return 0
    return score


async def targeted_power_detail_rows(
    client: Any,
    inventory_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranked = [
        (power_candidate_score(row), row)
        for row in inventory_rows
        if _power._device_id(row) not in (None, "")
    ]
    ranked = [(score, row) for score, row in ranked if score > 0]
    ranked.sort(
        key=lambda item: (
            -item[0],
            _power._normalise(_power._label(item[1])),
            str(_power._device_id(item[1]) or ""),
        )
    )
    ranked = ranked[: _power._MAX_POWER_DETAIL_PROBES]

    async def get_one(row: dict[str, Any]) -> Any:
        return await client.call_tool(
            "hub_get_device",
            {"deviceId": str(_power._device_id(row))},
        )

    responses = await asyncio.gather(
        *(get_one(row) for _score, row in ranked),
        return_exceptions=True,
    )

    detail_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []

    for (score, candidate), response in zip(ranked, responses):
        device_id = str(_power._device_id(candidate) or "")
        label = _power._label(candidate)
        selected.append({"id": device_id, "label": label, "score": score})

        if isinstance(response, Exception):
            failures.append(
                {
                    "device_id": device_id,
                    "label": label,
                    "error": str(response).strip() or type(response).__name__,
                }
            )
            continue
        if response.is_error:
            failures.append(
                {
                    "device_id": device_id,
                    "label": label,
                    "error": response.text or "hub_get_device failed",
                }
            )
            continue
        detail_rows.extend(_power._accounting_device_rows(response.data))

    numeric_readings = [
        row
        for row in detail_rows
        if _power.measurement_reading(row, _power._SPECS["power"]) is not None
    ]
    return detail_rows, {
        "candidate_count": len(ranked),
        "candidate_ids": [item["id"] for item in selected],
        "candidate_labels": [item["label"] for item in selected],
        "candidate_scores": selected,
        "detail_row_count": len(detail_rows),
        "numeric_power_reading_count": len(numeric_readings),
        "failure_count": len(failures),
        "failures": failures,
    }


def install_power_device_discovery_fallback() -> None:
    """Install the expanded fallback without adding an application.ask layer."""

    _power._targeted_power_detail_rows = targeted_power_detail_rows


__all__ = [
    "install_power_device_discovery_fallback",
    "power_candidate_score",
    "targeted_power_detail_rows",
]

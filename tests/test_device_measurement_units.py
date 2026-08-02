from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import resolve_device_candidate  # noqa: E402


def test_exact_resolution_adds_standard_temperature_unit() -> None:
    resolution = resolve_device_candidate(
        "Bathroom Meter",
        [{
            "id": "1",
            "label": "Bathroom Meter",
            "attributes": {"temperature": 27.0, "humidity": 58},
        }],
    )

    assert resolution.target is not None
    assert resolution.target["attributeUnits"]["temperature"] == "°C"
    assert resolution.target["attributeUnits"]["humidity"] == "%"


def test_reported_device_unit_overrides_standard_default() -> None:
    resolution = resolve_device_candidate(
        "Outdoor Sensor",
        [{
            "id": "2",
            "label": "Outdoor Sensor",
            "currentStates": [
                {"name": "temperature", "currentValue": 72, "unit": "°F"},
            ],
        }],
    )

    assert resolution.target is not None
    assert resolution.target["attributeUnits"]["temperature"] == "°F"


def test_non_measurement_resolution_does_not_add_empty_units() -> None:
    original = {"id": "3", "label": "Front Door", "attributes": {"contact": "closed"}}
    resolution = resolve_device_candidate("Front Door", [original])

    assert resolution.target == original
    assert "attributeUnits" not in resolution.target


def test_resolution_does_not_mutate_inventory_record() -> None:
    original = {"id": "4", "label": "Bedroom Meter", "temperature": 24.5}
    resolution = resolve_device_candidate("Bedroom Meter", [original])

    assert resolution.target is not None
    assert resolution.target is not original
    assert "attributeUnits" not in original
    assert resolution.target["attributeUnits"]["temperature"] == "°C"

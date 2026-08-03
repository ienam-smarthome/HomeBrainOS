from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from run_named_device_soak import validate_named_device_result  # noqa: E402


def valid_result() -> dict:
    return {
        "success": True,
        "message": "Bathroom Meter is reporting 27.0°C.",
        "evidence": [
            {
                "tool": "hub_read_devices",
                "success": True,
                "arguments": {"tool": "hub_list_devices", "args": {}},
            },
            {
                "tool": "homebrain_resolve_device",
                "success": True,
                "arguments": {"name": "Bathroom Meter"},
            },
        ],
        "metrics": {
            "outcome": "success",
            "counters": {"tool_calls": 2},
            "timings_ms": {"total": 600},
        },
        "metric_rows": [
            {"label": "Tool calls", "value": "2"},
            {"label": "Outcome", "value": "success"},
        ],
    }


def test_named_device_soak_accepts_entity_first_resolution() -> None:
    assert validate_named_device_result(
        valid_result(), device_name="Bathroom Meter"
    ) == []


def test_named_device_soak_accepts_expected_outcome() -> None:
    assert validate_named_device_result(
        valid_result(),
        device_name="Bathroom Meter",
        expected_outcome="success",
    ) == []


def test_named_device_soak_rejects_unexpected_outcome() -> None:
    errors = validate_named_device_result(
        valid_result(),
        device_name="Bathroom Meter",
        expected_outcome="unresolved",
    )

    assert (
        "metrics outcome 'success' did not match expected 'unresolved'"
        in errors
    )


def test_named_device_soak_rejects_name_as_hubitat_filter() -> None:
    result = valid_result()
    result["evidence"][0]["arguments"]["args"] = {
        "filter": "Bathroom Meter"
    }

    errors = validate_named_device_result(result, device_name="Bathroom Meter")

    assert "device name was forwarded through Hubitat's filter field" in errors


def test_named_device_soak_requires_successful_resolver_receipt() -> None:
    result = valid_result()
    result["evidence"][1]["success"] = False

    errors = validate_named_device_result(result, device_name="Bathroom Meter")

    assert "named-device resolver did not succeed" in errors


def test_named_device_soak_requires_exact_requested_name() -> None:
    result = valid_result()
    result["evidence"][1]["arguments"]["name"] = "Bedroom 1 Meter"

    errors = validate_named_device_result(result, device_name="Bathroom Meter")

    assert "resolver did not receive the requested device name" in errors


def test_named_device_soak_keeps_metric_privacy_validation() -> None:
    result = valid_result()
    result["metrics"]["device_name"] = "Bathroom Meter"

    errors = validate_named_device_result(result, device_name="Bathroom Meter")

    assert any("privacy-sensitive metric key" in error for error in errors)

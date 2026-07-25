from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from device_read_shapes import (
    DETAILED_DEVICE_FIELDS,
    detailed_device_arguments,
)


EXPECTED_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "attributes",
    "disabled",
    "lastActivity",
]


def test_canonical_detailed_device_shape():
    assert list(DETAILED_DEVICE_FIELDS) == EXPECTED_FIELDS
    assert detailed_device_arguments() == {
        "detailed": True,
        "format": "detailed",
        "fields": EXPECTED_FIELDS,
    }


def test_request_shape_returns_fresh_field_list():
    first = detailed_device_arguments()
    second = detailed_device_arguments()

    assert first is not second
    assert first["fields"] is not second["fields"]

    first["fields"].append("unexpected")
    assert second["fields"] == EXPECTED_FIELDS


def test_power_and_octopus_use_shared_shape():
    power = (
        APP_DIR / "semantic_metric_comparison_live.py"
    ).read_text(encoding="utf-8")

    octopus = (
        APP_DIR / "control_focus_octopus_energy.py"
    ).read_text(encoding="utf-8")

    assert "detailed_device_arguments()" in power
    assert "detailed_device_arguments()" in octopus


def test_legacy_octopus_reader_removed():
    hybrid = (
        APP_DIR / "hybrid_assistant_mode.py"
    ).read_text(encoding="utf-8")

    assert "class OctopusEnergySummary:" not in hybrid
    assert (
        "octopus_service = OctopusLiveMeterSummary(application)"
        in hybrid
    )


def test_shared_shape_matches_broker_cache_key_requirements():
    power_args = detailed_device_arguments()
    octopus_args = detailed_device_arguments()

    assert power_args == octopus_args

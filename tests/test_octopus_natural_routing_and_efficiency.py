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

from control_focus_octopus_energy import (
    _has_live_display_value,
    is_octopus_display_query,
)


def test_natural_octopus_family_queries_route_to_summary():
    accepted = [
        "show octopus",
        "show octopus devices",
        "show octopus meter",
        "list octopus sensors",
        "display the octopus meters",
        "find octopus",
    ]

    for query in accepted:
        assert is_octopus_display_query(query) is True


def test_unrelated_octopus_text_does_not_claim_the_route():
    rejected = [
        "turn on octopus lamp",
        "disable octopus controller",
        "what is an octopus",
    ]

    for query in rejected:
        assert is_octopus_display_query(query) is False


def test_octopus_source_uses_single_primary_inventory_pass():
    source = (
        APP_DIR / "control_focus_octopus_energy.py"
    ).read_text(encoding="utf-8")

    assert "for detailed in (False, True)" not in source
    assert "await enriched_devices(force=True)" not in source
    assert "missing_values = [" in source
    assert '"rows": rows' not in source
    assert '"live_value_count"' in source
    assert '"displays": [' in source


def test_octopus_placeholder_identity_is_not_a_live_value():
    placeholder = {
        "id": "7433",
        "name": "Octopus Live Meter Display Today",
        "label": "Octopus Meter Energy Today",
        "currentStates": {
            "display": "Octopus Live Meter Display Today",
        },
    }
    real_value = {
        "id": "7433",
        "name": "Octopus Live Meter Display Today",
        "label": "Octopus Meter Energy Today",
        "currentStates": {
            "valueStr": "4.8 kWh",
        },
    }

    assert _has_live_display_value(placeholder) is False
    assert _has_live_display_value(real_value) is True


def test_octopus_inventory_does_not_use_narrow_legacy_label_filter():
    source = (
        APP_DIR / "control_focus_octopus_energy.py"
    ).read_text(encoding="utf-8")

    assert '"labelFilter": "Octopus Live Meter Display"' not in source
    assert "detailed_device_arguments()" in source

    shared_shape = (
        APP_DIR / "device_read_shapes.py"
    ).read_text(encoding="utf-8")
    assert '"detailed": True' in shared_shape
    assert '"format": "detailed"' in shared_shape
    assert "_is_octopus_meter_row(row)" in source

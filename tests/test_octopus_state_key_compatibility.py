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
    _display_value,
    _unwrap_state,
)


def test_unwrap_state_accepts_hubitat_current_value_case():
    value, unit = _unwrap_state(
        {
            "name": "html",
            "currentValue": "<b>4.8 kWh</b><br>£1.48 today",
            "unitOfMeasurement": "kWh",
        }
    )

    assert value == "4.8 kWh £1.48 today"
    assert unit == "kWh"


def test_display_value_reads_camel_case_attribute_entry():
    row = {
        "id": "t",
        "label": "Octopus Live Meter Display Today",
        "attributes": [
            {
                "name": "html",
                "currentValue": "<b>4.8 kWh</b><br>£1.48 today",
            }
        ],
    }

    assert _display_value(row) == "4.8 kWh £1.48 today"

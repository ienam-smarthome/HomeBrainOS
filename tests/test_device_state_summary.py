from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_state_summary import device_attributes  # noqa: E402


def test_device_attributes_merges_all_hubitat_state_shapes():
    device = {
        "attributes": [{"name": "battery", "currentValue": 14}],
        "currentStates": [
            {"name": "presence", "currentValue": "present"},
            {"name": "motion", "value": "active"},
        ],
        "states": {"contact": "open"},
    }

    assert device_attributes(device) == {
        "battery": 14,
        "presence": "present",
        "motion": "active",
        "contact": "open",
    }


def test_later_live_state_overrides_older_attribute_value():
    device = {
        "attributes": {"switch": "off"},
        "states": {"switch": "off"},
        "currentStates": [{"name": "switch", "currentValue": "on"}],
    }

    assert device_attributes(device)["switch"] == "on"

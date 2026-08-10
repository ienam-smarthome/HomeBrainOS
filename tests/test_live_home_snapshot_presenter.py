from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from deterministic_tool_presenter import present_tool_result  # noqa: E402


def test_live_home_snapshot_uses_natural_switch_and_offline_wording():
    message = present_tool_result(
        "homebrain_home_snapshot",
        {
            "presence": [{"label": "Enamul"}, {"label": "Samah"}],
            "active_rooms": [{"name": "Bathroom"}],
            "active_motion": [{"label": "Bathroom Presence Sensor"}],
            "lights_on": [{"label": "Bathroom Light"}],
            "switches_on": [
                {"label": "Fridge"},
                {"label": "Freezer"},
            ],
            "low_batteries": [{"label": "Fridge Door", "battery": 14}],
            "alerts": [
                {"label": "Iron", "status": "offline", "source": "connectivity"},
                {
                    "label": "Roborock Q7 Max",
                    "status": "offline",
                    "source": "connectivity",
                },
            ],
        },
    )

    assert "**At home:** Enamul and Samah." in message
    assert "**Switches:** 2 non-light switches are on: Fridge and Freezer." in message
    assert (
        "**Attention needed:** 2 devices are flagged: "
        "Iron (offline) and Roborock Q7 Max (offline)."
    ) in message
    assert "Other switches on" not in message
    assert "**Alerts:**" not in message


def test_home_snapshot_distinguishes_a_hub_alert_from_a_connectivity_alert():
    """Regression test: device_query_service.py merges two different alert
    sources into one "alerts" bucket -- a genuine connectivity signal
    (healthStatus/networkStatus/rtt) and the device's raw hubAlerts text
    (which can carry battery, tamper, or firmware warnings unrelated to
    connectivity). Every entry used to render with the same hardcoded
    "offline or unavailable" wording regardless of source, misreporting
    the actual alert reason for a hubAlerts-sourced entry.
    """

    message = present_tool_result(
        "homebrain_home_snapshot",
        {
            "alerts": [
                {
                    "label": "Front Door Lock",
                    "status": "low battery",
                    "source": "hub_alert",
                },
                {
                    "label": "Hallway Motion",
                    "status": "offline",
                    "source": "connectivity",
                },
            ],
        },
    )

    assert "offline or unavailable" not in message
    assert "Front Door Lock (low battery)" in message
    assert "Hallway Motion (offline)" in message

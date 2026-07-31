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
                {"label": "Iron"},
                {"label": "Roborock Q7 Max"},
            ],
        },
    )

    assert "**At home:** Enamul and Samah." in message
    assert "**Switches:** 2 non-light switches are on: Fridge and Freezer." in message
    assert (
        "**Attention needed:** 2 devices are offline or unavailable: "
        "Iron and Roborock Q7 Max."
    ) in message
    assert "Other switches on" not in message
    assert "**Alerts:**" not in message

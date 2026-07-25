from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)

sys.path.insert(0, str(APP_DIR))

from control_focus_mode import ControlFocusMode
from control_focus_power_summary_safe import (
    install_control_focus_power_summary_safe,
)


class FakeMetricExecutor:
    async def execute(self, intent, *, query):
        return {
            "measurement_readings": [
                {
                    "id": "1",
                    "label": "Fridge",
                    "room": "Appliances",
                    "value": 79.0,
                    "aggregate": False,
                },
                {
                    "id": "2",
                    "label": "Microwave",
                    "room": "Appliances",
                    "value": 0.0,
                    "aggregate": False,
                },
                {
                    "id": "3",
                    "label": "Whole home",
                    "room": "",
                    "value": 150.0,
                    "aggregate": True,
                },
            ]
        }


def test_power_summary_technical_diagnostics_are_compact():
    install_control_focus_power_summary_safe()

    instance = object.__new__(ControlFocusMode)
    instance.metric_executor = FakeMetricExecutor()

    answer = asyncio.run(
        instance.power_summary("show power devices")
    )

    technical = answer["technical"]
    if isinstance(technical, str):
        technical = json.loads(technical)

    assert "normalised_readings" not in technical
    assert "active_readings" not in technical
    assert "idle_readings" not in technical
    assert "aggregate_readings" not in technical

    assert technical == {
        "query": "show power devices",
        "numeric_reading_count": 2,
        "active_reading_count": 1,
        "idle_reading_count": 1,
        "active_total_w": 79.0,
        "aggregate_reading_count": 1,
        "active_device_labels": ["Fridge"],
        "idle_device_labels": ["Microwave"],
    }

    assert len(answer["active_power_readings"]) == 1
    assert len(answer["idle_power_readings"]) == 1
    assert len(answer["aggregate_power_readings"]) == 1
    assert answer["active_power_total_w"] == 79.0


def test_webui_does_not_render_identical_display_title_twice():
    source = (
        APP_DIR / "webui_homebrain.py"
    ).read_text(encoding="utf-8")

    assert (
        "if(displayTitle!==(title.textContent||''))"
        "output.appendChild(el('div','result-title',displayTitle))"
        in source
    )

    assert (
        "output.appendChild(el('div','result-title',"
        "answer.display.title||'Result'))"
        not in source
    )

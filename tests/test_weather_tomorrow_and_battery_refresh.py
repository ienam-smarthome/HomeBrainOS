from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("weather_battery_refresh", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


def forecast_html():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%a")
    day_after = (datetime.now() + timedelta(days=2)).strftime("%a")
    return (
        "<div>Lewisham</div><div>SE13</div><div>Daily</div>"
        "<div>Tod</div><div>Partly cloudy</div><div>28C/17C</div>"
        "<div>0%</div><div>0mm</div>"
        f"<div>{tomorrow}</div><div>Showers</div><div>22C/15C</div>"
        "<div>60%</div><div>3mm</div>"
        f"<div>{day_after}</div><div>Overcast</div><div>20C/14C</div>"
        "<div>10%</div><div>0mm</div>"
    )


class FakeMain:
    def all_devices(self):
        return [
            {
                "id": "weather",
                "label": "Weather Open-Meteo",
                "category": "weather",
                "attributes": {
                    "weatherSummary": (
                        "Partly cloudy with a high of 28C and a low of 17C. "
                        "Current temperature is 21C and feels like 21C. "
                        "Precipitation now is Dry 0.00mm. Chance of precipitation is 0%."
                    ),
                    "weatherSummaryLine": "Partly cloudy, High 28C, Low 17C, Current 21C",
                    "threedayfcstTile": forecast_html(),
                },
            },
            {
                "id": "trv",
                "label": "Livingroom TRV",
                "category": "Heating",
                "attributes": {},
            },
            {
                "id": "door",
                "label": "Fridge Door",
                "category": "Sensor",
                "attributes": {"battery": 19},
            },
        ]

    def maker_get(self, path, timeout=8):
        if path == "devices/trv":
            return {
                "id": "trv",
                "label": "Livingroom TRV",
                "attributes": [{"name": "battery", "currentValue": 12}],
            }
        if path == "devices/door":
            return {
                "id": "door",
                "label": "Fridge Door",
                "attributes": [{"name": "battery", "currentValue": 19}],
            }
        if path == "devices/weather":
            return self.all_devices()[0]
        return {}


def test_tomorrow_tile_parser_extracts_actual_day_column():
    attrs = FakeMain().all_devices()[0]["attributes"]
    result = module._tomorrow_forecast(attrs)
    assert result["available"] is True
    assert result["condition"].lower() == "showers"
    assert result["high"] == "22"
    assert result["low"] == "15"
    assert result["chance"] == "60"
    assert result["amount"] == "3"


def test_tomorrow_answer_is_not_blank():
    answer = module.improved_weather_answer(FakeMain(), "will it rain tomorrow")
    assert answer["message"].startswith("Tomorrow:")
    assert "Showers" in answer["message"]
    assert "rain chance 60%" in answer["message"]
    assert answer["message"] != "Tomorrow: ."


def test_weather_answer_repairs_degree_mojibake():
    cleaned = module._clean_display_text("Now: 21\u00c2\u00b0C. Today: 28\u00c2\u00b0C.")
    assert cleaned == "Now: 21\u00b0C. Today: 28\u00b0C."


def test_live_detail_refresh_finds_trv_battery():
    rows = module.authoritative_low_batteries(FakeMain())
    assert [(row["label"], row["battery"]) for row in rows] == [
        ("Livingroom TRV", 12.0),
        ("Fridge Door", 19.0),
    ]


def test_low_battery_answer_lists_both_devices():
    answer = module.authoritative_low_battery_answer(FakeMain(), "which batteries are low")
    assert "Livingroom TRV: 12%" in answer["message"]
    assert "Fridge Door: 19%" in answer["message"]
    assert answer["count"] == 2
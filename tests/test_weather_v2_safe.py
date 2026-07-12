from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("weather_v2_safe", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


def row_major_tile() -> str:
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%a")
    after = (datetime.now() + timedelta(days=2)).strftime("%a")
    return (
        "<div>Lewisham</div><div>SE13</div><div>Daily</div>"
        f"<div>Tod</div><div>{tomorrow}</div><div>{after}</div>"
        "<div>Icon</div><div>Cond</div>"
        "<div>Mostly sunny</div><div>Overcast</div><div>Showers</div>"
        "<div>H/L</div>"
        "<div>28C/17C</div><div>27C/16C</div><div>22C/15C</div>"
        "<div>Chance Rain</div>"
        "<div>0%</div><div>10%</div><div>60%</div>"
        "<div>Rain</div>"
        "<div>0mm</div><div>0mm</div><div>3mm</div>"
    )


class FakeMain:
    def all_devices(self):
        return [{
            "id": "weather",
            "label": "Weather Open-Meteo",
            "category": "weather",
            "attributes": {
                "weatherSummary": (
                    "Mostly sunny with a high of 28C and a low of 17C. "
                    "Current temperature is 21C and feels like 21C. "
                    "Precipitation now is Dry 0.00mm. "
                    "Chance of precipitation is 0%."
                ),
                "weatherSummaryLine": "Mostly sunny, High 28C, Low 17C, Current 21C",
                "threedayfcstTile": row_major_tile(),
            },
        }]

    def maker_get(self, path, timeout=8):
        return self.all_devices()[0]


def test_tomorrow_row_major_tile():
    result = module._tomorrow_forecast(FakeMain().all_devices()[0]["attributes"])
    assert result["available"] is True
    assert result["condition"].lower() == "overcast"
    assert result["high"] == "27"
    assert result["low"] == "16"
    assert result["chance"] == "10"
    assert result["amount"] == "0"


def test_weather_tomorrow():
    answer = module.improved_weather_answer(FakeMain(), "weather tomorrow")
    assert answer["message"].startswith("Tomorrow: Overcast.")
    assert "high 27\u00b0C, low 16\u00b0C" in answer["message"]
    assert "rain chance 10%" in answer["message"]


def test_rain_today_leads_with_rain():
    answer = module.improved_weather_answer(FakeMain(), "will it rain today")
    assert answer["message"].startswith("Today: No rain is expected.")
    assert "rain chance 0%" in answer["message"]


def test_rain_tomorrow_leads_with_rain():
    answer = module.improved_weather_answer(FakeMain(), "will it rain tomorrow")
    assert answer["message"].startswith("Tomorrow: Rain is possible.")
    assert "rain chance 10%" in answer["message"]
    assert "forecast rain 0 mm" in answer["message"]

from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from routing import is_fast_path_query  # noqa: E402
from weather_presenter_v2 import present_weather  # noqa: E402


WEATHER_DATA = {
    "devices": [
        {
            "id": "weather-1",
            "label": "Open-Meteo Weather",
            "attributes": [
                {
                    "name": "weatherSummary",
                    "currentValue": (
                        "Weather summary for Lewisham, SE13 updated at 18:19. "
                        "Mostly sunny with a high of 28C and a low of 17C. "
                        "Current temperature is 26C and feels like 24C. "
                        "Precipitation now is Dry 0.00mm. "
                        "Chance of precipitation is 0%."
                    ),
                },
                {"name": "temperature", "currentValue": 25.8},
                {"name": "humidity", "currentValue": 40},
                {
                    "name": "threedayfcstTile",
                    "currentValue": (
                        "<div>Today</div><div>Tomorrow</div><div>Sat</div>"
                        "<div>Mostly sunny</div><div>Showers</div><div>Cloudy</div>"
                        "<div>28°C / 17°C</div><div>22°C / 15°C</div><div>21°C / 14°C</div>"
                        "<div>0%</div><div>60%</div><div>30%</div>"
                        "<div>0 mm</div><div>3 mm</div><div>1 mm</div>"
                    ),
                },
            ],
        }
    ]
}


def test_tomorrow_and_rain_queries_use_fast_path():
    assert is_fast_path_query("what is the weather tomorrow") is True
    assert is_fast_path_query("will it rain tomorrow") is True
    assert is_fast_path_query("will it rain today") is True
    assert is_fast_path_query("weather forecast for tomorrow") is True


def test_tomorrow_weather_is_period_specific():
    message, display = present_weather(
        WEATHER_DATA,
        "what is the weather tomorrow",
    )

    assert message.startswith("Tomorrow:")
    assert "Showers" in message
    assert "high 22°C, low 15°C" in message
    assert "rain chance 60%" in message
    assert "forecast rain 3 mm" in message
    assert "Mostly sunny with a high of 28C" not in message
    assert display["title"] == "Weather tomorrow"
    metrics = {item["label"]: item["value"] for item in display["metrics"]}
    assert metrics["Condition"] == "Showers"
    assert metrics["High"] == "22°C"
    assert metrics["Low"] == "15°C"
    assert metrics["Rain chance"] == "60%"


def test_rain_today_answers_the_rain_question_directly():
    message, display = present_weather(WEATHER_DATA, "will it rain today")

    assert message.startswith("Today: No rain is expected.")
    assert "rain chance 0%" in message
    assert "currently Dry 0.00mm" in message
    assert "Weather summary for Lewisham" not in message
    assert display["title"] == "Rain today"
    assert display["subtitle"].startswith("No rain is expected")


def test_rain_tomorrow_uses_forecast_values():
    message, display = present_weather(WEATHER_DATA, "will it rain tomorrow")

    assert message.startswith("Tomorrow: Rain is likely.")
    assert "rain chance 60%" in message
    assert "forecast rain 3 mm" in message
    assert "conditions Showers" in message
    assert display["title"] == "Rain tomorrow"

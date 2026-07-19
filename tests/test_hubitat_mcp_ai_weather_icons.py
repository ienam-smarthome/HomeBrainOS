from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from weather_presenter_icons import present_weather, weather_condition_icon  # noqa: E402


def _payload(condition: str, precipitation: str = "Dry 0.00mm"):
    return {
        "devices": [
            {
                "id": "weather-1",
                "label": "Home Weather",
                "type": "Virtual Weather Device",
                "attributes": [
                    {
                        "name": "weatherSummary",
                        "currentValue": (
                            f"Weather summary for Lewisham, SE13 updated at 13:34. "
                            f"{condition} with a high of 23C and a low of 14C. "
                            f"Current temperature is 22C and feels like 19C. "
                            f"Precipitation now is {precipitation}. "
                            "Chance of precipitation is 0%."
                        ),
                    },
                    {"name": "temperature", "currentValue": "22"},
                    {"name": "humidity", "currentValue": "32"},
                    {"name": "precipitationNow", "currentValue": precipitation},
                ],
            }
        ]
    }


def _condition_metric(display):
    return next(item for item in display["metrics"] if item["label"] == "Condition")


def test_mostly_sunny_dry_condition_does_not_show_rain_icon():
    _message, display = present_weather(_payload("Mostly sunny"), "What is the weather?")

    condition = _condition_metric(display)
    assert condition["value"] == "Mostly sunny"
    assert condition["icon"] == "🌤️"
    assert condition["icon"] != "🌦️"
    assert "rain" not in condition["icon"]


def test_rain_conditions_keep_a_rain_icon():
    assert weather_condition_icon("Light rain") == "🌧️"
    assert weather_condition_icon("Showers") == "🌧️"
    assert weather_condition_icon("Thunderstorms") == "⛈️"


def test_dry_condition_icon_mapping_covers_common_conditions():
    assert weather_condition_icon("Sunny") == "☀️"
    assert weather_condition_icon("Clear") == "☀️"
    assert weather_condition_icon("Partly cloudy") == "⛅"
    assert weather_condition_icon("Mostly cloudy") == "🌥️"
    assert weather_condition_icon("Cloudy") == "☁️"
    assert weather_condition_icon("Fog") == "🌫️"


def test_release_metadata_is_0435():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    weather_route = (APP_DIR / "fast_fallback_weather.py").read_text(encoding="utf-8")

    assert "version: '0.4.35-alpha'" in config
    assert 'PREVIOUS_RELEASE_VERSION = "0.4.34-alpha"' in entrypoint
    assert 'RELEASE_VERSION = "0.4.35-alpha"' in entrypoint
    assert "from weather_presenter_icons import present_weather" in weather_route

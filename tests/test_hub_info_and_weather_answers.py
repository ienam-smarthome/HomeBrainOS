from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("hub_weather_intelligence", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


HUB_HTML = """
<table>
<tr><td>Name</td><td>Hub C8 Pro</td></tr>
<tr><td>Version</td><td>C-8 Pro / 2.5.1.125</td></tr>
<tr><td>Free Mem</td><td>875.47 MB</td></tr>
<tr><td>CPU Load/Load%</td><td>0.85 / 24.5 %</td></tr>
<tr><td>DB Size</td><td>168 MB</td></tr>
<tr><td>Last Restart</td><td>09Jul2026 23:46</td></tr>
<tr><td>Uptime</td><td>2d:9h:26m:46s</td></tr>
<tr><td>Temperature</td><td>49.2 °C</td></tr>
<tr><td>Matter Enabled/Status</td><td>true / online</td></tr>
</table>
"""


class Response:
    text = HUB_HTML

    def raise_for_status(self):
        return None


class Requests:
    def get(self, url, timeout=5):
        assert url.endswith("/local/hubInfoOutput.html")
        return Response()


class FakeMain:
    CONFIG = {"hubitat_base_url": "http://192.168.1.239"}
    requests = Requests()

    def all_devices(self):
        tomorrow = (datetime.now().weekday() + 1) % 7
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        tomorrow_name = day_names[tomorrow]
        return [
            {
                "id": "weather",
                "label": "Weather Open-Meteo",
                "category": "weather",
                "attributes": {
                    "temperature": 21,
                    "weatherSummary": (
                        "Weather summary for Lewisham, SE13 updated at 09:19. "
                        "Partly cloudy with a high of 28C and a low of 17C. "
                        "Current temperature is 21C and feels like 21C. "
                        "Precipitation now is Dry 0.00mm. Chance of precipitation is 0%."
                    ),
                    "weatherSummaryLine": "Partly cloudy, High 28C, Low 17C, Current 21C",
                    "threedayfcstTile": (
                        f"<div>Tod</div><div>Overcast</div><div>28C/17C</div>"
                        f"<div>Chance Rain</div><div>0%</div><div>0mm</div>"
                        f"<div>{tomorrow_name}</div><div>Showers</div><div>22C/15C</div>"
                        f"<div>Chance Rain</div><div>60%</div><div>3mm</div>"
                    ),
                },
            }
        ]


def test_hub_info_parser_and_cpu_answer():
    answer = module.hub_cpu_advisor_answer(FakeMain(), "CPU advisor")
    assert answer["intent"] == "hub_status"
    assert "Hub C8 Pro status from live Hub Info" in answer["message"]
    assert "CPU load: 0.85 / 24.5 %" in answer["message"]
    assert "Free memory: 875.47 MB" in answer["message"]
    assert "Temperature: 49.2 °C" in answer["message"]
    assert "Database size: 168 MB" in answer["message"]


def test_weather_now_is_clearly_labelled():
    answer = module.improved_weather_answer(FakeMain(), "what is the weather now")
    assert answer["period"] == "now"
    assert answer["message"].startswith("Now:")
    assert "21°C now" in answer["message"]
    assert "precipitation now: Dry 0.00mm" in answer["message"]


def test_weather_today_is_distinct():
    answer = module.improved_weather_answer(FakeMain(), "weather today")
    assert answer["period"] == "today"
    assert answer["message"].startswith("Today:")
    assert "high 28°C, low 17°C" in answer["message"]
    assert "rain chance 0%" in answer["message"]


def test_weather_tomorrow_includes_rain():
    answer = module.improved_weather_answer(FakeMain(), "will it rain tomorrow")
    assert answer["period"] == "tomorrow"
    assert answer["message"].startswith("Tomorrow:")
    assert "Showers" in answer["message"]
    assert "rain chance 60%" in answer["message"]
    assert "forecast rain 3 mm" in answer["message"]


def test_weather_overview_separates_periods():
    answer = module.improved_weather_answer(FakeMain(), "weather")
    assert "Now:" in answer["message"]
    assert "Today:" in answer["message"]
    assert "Tomorrow:" in answer["message"]
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("authoritative_intelligence", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


REPORT_HTML = """
<div><h3>OFFLINE</h3><div>Roborock Q7 Max - last seen 2d ago</div></div>
<div><h3>LOW BATTERY</h3>
<div>Livingroom TRV - 12% battery - last seen 38m ago</div>
<div>Fridge Door - 19% battery - last seen 0m ago</div>
</div>
<div><h3>OK</h3><div>None</div></div>
"""


class FakeMain:
    HOUSEHOLD_PEOPLE = ["Enamul", "Samah", "Tahmid", "Muhsena"]

    def __init__(self):
        self.CONFIG = {}
        self.app = SimpleNamespace(routes=[], version="old")
        self.APP_VERSION = "old"

    def all_devices(self):
        return [
            {"id": "p1", "label": "Enamul Khan", "category": "presence", "attributes": {"presence": "not present"}},
            {"id": "p2", "label": "Samah Khan", "category": "presence", "attributes": {"presence": "present"}},
            {"id": "p3", "label": "Tahmid Khan", "category": "presence", "attributes": {"presence": "present"}},
            {"id": "p4", "label": "Muhsena Khan", "category": "presence", "attributes": {"presence": "present"}},
            {"id": "w1", "label": "Weather Open-Meteo", "category": "weather", "attributes": {}},
            {"id": "r1", "label": "Device Status Report Display", "category": "report", "attributes": {}},
            {"id": "b1", "label": "Fridge Door", "attributes": {"battery": 19}},
        ]

    def maker_get(self, path, timeout=8):
        if path == "devices/p1":
            return {
                "id": "p1",
                "label": "Enamul Khan",
                "attributes": [
                    {"name": "presence", "currentValue": "not present"},
                    {"name": "tile", "currentValue": "<div>At Home since yesterday 11:10 PM</div>"},
                ],
            }
        if path == "devices/w1":
            return {
                "id": "w1",
                "attributes": [
                    {
                        "name": "weatherSummary",
                        "currentValue": (
                            "Partly cloudy with a high of 28C and a low of 17C. "
                            "Current temperature is 21C and feels like 21C. "
                            "Precipitation now is Dry 0.00mm. Chance of precipitation is 0%."
                        ),
                    },
                    {"name": "weatherSummaryLine", "currentValue": "Partly cloudy, High 28C, Low 17C, Current 21C"},
                    {"name": "temperature", "currentValue": 21},
                ],
            }
        if path == "devices/r1":
            return {
                "id": "r1",
                "attributes": [{"name": "reportHtml", "currentValue": REPORT_HTML}],
            }
        return {}


def test_life360_tile_overrides_stale_presence():
    result = module.authoritative_people_home(FakeMain())
    assert result["count"] == 4
    assert result["home"] == ["Enamul", "Samah", "Tahmid", "Muhsena"]


def test_family_answer_reports_everyone_home():
    answer = module.authoritative_family_answer(FakeMain(), "who is home")
    assert answer["message"].startswith("Everyone is home:")
    assert answer["count"] == 4


def test_report_html_is_authoritative_for_low_batteries():
    rows = module.authoritative_low_batteries(FakeMain())
    assert [row["label"] for row in rows] == ["Livingroom TRV", "Fridge Door"]
    assert [row["battery"] for row in rows] == [12.0, 19.0]
    assert rows[0]["source"] == "Device Status Report"


def test_low_battery_answer_lists_both_reported_devices():
    answer = module.authoritative_low_battery_answer(FakeMain(), "which batteries are low")
    assert "Livingroom TRV: 12%" in answer["message"]
    assert "Fridge Door: 19%" in answer["message"]
    assert answer["count"] == 2


def test_weather_detail_is_fetched_on_demand():
    device = module._authoritative_weather_device(FakeMain())
    assert device is not None
    assert device["attributes"]["weatherSummary"]
    answer = module.improved_weather_answer(FakeMain(), "what is the weather")
    assert "Now:" in answer["message"]
    assert "21Â°C" in answer["message"]
    assert "Today:" in answer["message"]


def test_display_cleaner_fixes_entities_and_mojibake():
    source = "\u00e2\u20ac\u00a2 CPU &deg;C \u00c2\u00a3"
    cleaned = module._clean_display_text(source)
    assert cleaned == "- CPU \u00b0C \u00a3"


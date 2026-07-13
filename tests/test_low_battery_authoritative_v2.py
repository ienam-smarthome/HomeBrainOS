from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("low_battery_v2", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


REPORT_HTML = (
    "<div>[OFFLINE]</div>"
    "<div>None</div>"
    "<div>[LOW BATTERY] 2</div>"
    "<div>\U0001FAAB Livingroom TRV - 12% battery - last seen 38m ago</div>"
    "<div>\u2022 Fridge Door: 19%</div>"
    "<div>[NO CHANGE]</div>"
    "<div>Hallway Motion - last changed 4h ago</div>"
)


class PriorityMain:
    CONFIG = {"battery_detail_refresh_limit": 2}

    def __init__(self):
        self.updated = []
        self.calls = []

    def all_devices(self):
        fillers = [
            {
                "id": f"sensor-{index}",
                "label": f"Generic Sensor {index}",
                "category": "sensor",
                "attributes": {},
            }
            for index in range(20)
        ]
        return fillers + [
            {
                "id": "trv",
                "label": "Livingroom TRV",
                "category": "Heating",
                "capabilities": ["Battery", "Thermostat"],
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
        self.calls.append(path)
        if path == "devices/trv":
            return {
                "id": "trv",
                "label": "Livingroom TRV",
                "category": "Heating",
                "attributes": [{"name": "battery", "currentValue": 12}],
            }
        if path == "devices/door":
            return {
                "id": "door",
                "label": "Fridge Door",
                "category": "Sensor",
                "attributes": [{"name": "battery", "currentValue": 19}],
            }
        return {}

    def update_cached_device_snapshot(self, device):
        self.updated.append(device)


class ReportMain:
    CONFIG = {}

    def __init__(self):
        self.app = SimpleNamespace(routes=[], version="old")
        self.APP_VERSION = "old"

    def all_devices(self):
        return [
            {
                "id": "wrong-report",
                "label": "Device Status Report",
                "category": "report",
                "attributes": {},
            },
            {
                "id": "display-report",
                "label": "Device Status Report Display",
                "category": "report",
                # In production reportText arrives through the Hubitat event
                # stream and is persisted in the device cache. Cached dashboard
                # reads must consume it without calling Maker API.
                "attributes": {"reportText": REPORT_HTML},
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
        if path == "devices/display-report":
            return {
                "id": "display-report",
                "label": "Device Status Report Display",
                "attributes": [
                    {"name": "reportText", "currentValue": REPORT_HTML},
                ],
            }
        return {}

    def dashboard_summary(self, live=False):
        return {
            "low_batteries": 1,
            "low_battery_devices": [
                {"id": "door", "label": "Fridge Door", "room": "Kitchen", "battery": 19}
            ],
        }


def test_priority_refresh_reaches_trv_before_generic_sensors():
    fake = PriorityMain()
    rows = module.authoritative_low_batteries(fake)
    assert [(row["label"], row["battery"]) for row in rows] == [
        ("Livingroom TRV", 12.0),
        ("Fridge Door", 19.0),
    ]
    assert "devices/trv" in fake.calls
    assert any(item.get("label") == "Livingroom TRV" and item.get("battery") == 12 for item in fake.updated)


def test_report_parser_supports_bracket_headings_bullets_and_no_change_section():
    rows = module._extract_low_battery_report(REPORT_HTML)
    assert [(row["label"], row["battery"]) for row in rows] == [
        ("Livingroom TRV", 12.0),
        ("Fridge Door", 19.0),
    ]


def test_cached_status_report_skips_empty_parent_and_uses_display_report():
    rows = module.authoritative_low_batteries(ReportMain(), refresh_live=False)
    assert [(row["label"], row["battery"]) for row in rows] == [
        ("Livingroom TRV", 12.0),
        ("Fridge Door", 19.0),
    ]


def test_dashboard_tile_uses_same_authoritative_rows():
    fake = ReportMain()
    module.wrap_dashboard_low_batteries(fake)
    summary = fake.dashboard_summary()
    assert summary["low_batteries"] == 2
    assert [item["label"] for item in summary["low_battery_devices"]] == [
        "Livingroom TRV",
        "Fridge Door",
    ]


def test_answer_explains_data_sources():
    answer = module.authoritative_low_battery_answer(ReportMain(), "which batteries are low")
    assert answer["count"] == 2
    assert "Livingroom TRV: 12%" in answer["message"]
    assert "Fridge Door: 19%" in answer["message"]
    assert "Source:" in answer["message"]

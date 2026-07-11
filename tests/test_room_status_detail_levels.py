from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("room_status_intelligence", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class FakeMain:
    def all_devices(self):
        return [
            {
                "id": "b1",
                "label": "Bathroom Meter",
                "room": "Bathroom",
                "category": "sensor",
                "attributes": {"temperature": 23.1, "humidity": 68, "battery": 76},
            },
            {
                "id": "b2",
                "label": "Bathroom Fan",
                "room": "Bathroom",
                "category": "switch",
                "attributes": {"switch": "on", "power": 18},
            },
            {
                "id": "b3",
                "label": "Bathroom Motion",
                "room": "Bathroom",
                "category": "motion",
                "attributes": {"motion": "inactive", "battery": 14},
            },
            {
                "id": "h1",
                "label": "Hallway Light",
                "room": "Hallway",
                "category": "light",
                "attributes": {"switch": "off"},
            },
        ]


def test_glance_room_status_is_focused():
    answer = module.focused_room_status_answer(FakeMain(), "bathroom status")
    assert answer["detail_level"] == "glance"
    assert "23.1°C" in answer["message"]
    assert "68% humidity" in answer["message"]
    assert "Bathroom Fan: on, using 18 watts" in answer["message"]
    assert "Bathroom Motion: battery 14 percent" in answer["message"]
    assert "Hallway" not in answer["message"]
    assert answer["devices"] == []


def test_detailed_room_status_lists_useful_device_states():
    answer = module.focused_room_status_answer(FakeMain(), "detailed bathroom status")
    assert answer["detail_level"] == "detailed"
    assert "Bathroom Meter:" in answer["message"]
    assert "Bathroom Fan:" in answer["message"]
    assert "Bathroom Motion:" in answer["message"]
    assert answer["device_count"] == 3


def test_diagnostic_room_status_contains_attribute_names():
    answer = module.focused_room_status_answer(FakeMain(), "diagnose bathroom devices")
    assert answer["detail_level"] == "diagnostic"
    assert "temperature=23.1" in answer["message"]
    assert "switch=on" in answer["message"]
    assert "battery=14" in answer["message"]


def test_html_is_removed_from_output():
    assert module._clean_display_text("<b>Fan</b>&nbsp;on") == "Fan on"


def test_room_query_is_intercepted_before_fallback():
    fake = FakeMain()
    fake.app = SimpleNamespace(routes=[], version="old")
    fake.APP_VERSION = "old"
    fake.assistant = lambda query: {"success": True, "message": "fallback"}
    module.wrap_assistant(fake)
    answer = fake.assistant("bathroom status")
    assert answer["intent"] == "room_status"
    assert answer["local_first"] is True
    assert "Bathroom Fan" in answer["message"]
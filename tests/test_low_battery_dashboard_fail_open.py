from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("battery_dashboard_fail_open", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class FakeMain:
    CONFIG = {}

    def dashboard_summary(self, live=False):
        return {
            "lights_on": 4,
            "people_home": 4,
            "low_batteries": 1,
            "low_battery_devices": [
                {"label": "Fridge Door", "battery": 19}
            ],
        }


def test_dashboard_returns_original_summary_when_enrichment_raises(monkeypatch):
    fake = FakeMain()

    def boom(*args, **kwargs):
        raise RuntimeError("battery enrichment failed")

    monkeypatch.setattr(module, "authoritative_low_batteries", boom)
    module.wrap_dashboard_low_batteries(fake)

    summary = fake.dashboard_summary(live=True)
    assert summary["lights_on"] == 4
    assert summary["people_home"] == 4
    assert summary["low_batteries"] == 1
    assert fake._homebrain_low_battery_last_error == "battery enrichment failed"


def test_dashboard_preserves_original_summary_when_no_rows(monkeypatch):
    fake = FakeMain()
    monkeypatch.setattr(
        module,
        "authoritative_low_batteries",
        lambda *args, **kwargs: [],
    )
    module.wrap_dashboard_low_batteries(fake)

    summary = fake.dashboard_summary()
    assert summary["low_batteries"] == 1
    assert summary["low_battery_devices"][0]["label"] == "Fridge Door"


def test_dashboard_uses_authoritative_rows_when_available(monkeypatch):
    fake = FakeMain()
    monkeypatch.setattr(
        module,
        "authoritative_low_batteries",
        lambda *args, **kwargs: [
            {
                "id": "trv",
                "label": "Livingroom TRV",
                "room": "Living Room",
                "battery": 12.0,
                "source": "Device Status Report",
                "sources": ["Device Status Report"],
            },
            {
                "id": "door",
                "label": "Fridge Door",
                "room": "Kitchen",
                "battery": 19.0,
                "source": "cached Maker API",
                "sources": ["cached Maker API"],
            },
        ],
    )
    module.wrap_dashboard_low_batteries(fake)

    summary = fake.dashboard_summary()
    assert summary["low_batteries"] == 2
    assert [item["label"] for item in summary["low_battery_devices"]] == [
        "Livingroom TRV",
        "Fridge Door",
    ]

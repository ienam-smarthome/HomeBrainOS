from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "homebrainos" / "rootfs" / "app" / "natural_intelligence.py"
spec = importlib.util.spec_from_file_location("battery_summary_refresh", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


ROWS = [
    {
        "id": "trv",
        "label": "Livingroom TRV",
        "battery": 12.0,
        "source": "live Maker API",
        "sources": ["live Maker API"],
    },
    {
        "id": "door",
        "label": "Fridge Door",
        "battery": 19.0,
        "source": "cached Maker API",
        "sources": ["cached Maker API"],
    },
]


class FakeMain:
    CONFIG = {}

    def __init__(self):
        self.rebuild_calls = []

    def rebuild_summary_cache(self, reason="manual"):
        self.rebuild_calls.append(reason)
        return {
            "low_batteries": 2,
            "low_battery_devices": [
                {"label": "Livingroom TRV", "battery": 12},
                {"label": "Fridge Door", "battery": 19},
            ],
        }


def test_low_battery_answer_rebuilds_dashboard_summary(monkeypatch):
    fake = FakeMain()
    monkeypatch.setattr(
        module,
        "authoritative_low_batteries",
        lambda *args, **kwargs: [dict(item) for item in ROWS],
    )

    answer = module.authoritative_low_battery_answer(
        fake,
        "which batteries are low",
    )

    assert answer["count"] == 2
    assert fake.rebuild_calls == ["low-battery-answer"]
    assert answer["dashboard"]["low_batteries"] == 2


def test_dashboard_rebuild_failure_does_not_break_answer(monkeypatch):
    fake = FakeMain()

    def fail(reason="manual"):
        raise RuntimeError("summary rebuild failed")

    fake.rebuild_summary_cache = fail
    monkeypatch.setattr(
        module,
        "authoritative_low_batteries",
        lambda *args, **kwargs: [dict(item) for item in ROWS],
    )

    answer = module.authoritative_low_battery_answer(
        fake,
        "which batteries are low",
    )

    assert answer["success"] is True
    assert answer["count"] == 2
    assert answer["dashboard"] is None
    assert answer["dashboard_refresh_error"] == "summary rebuild failed"


def test_unrelated_question_does_not_rebuild(monkeypatch):
    fake = FakeMain()
    monkeypatch.setattr(
        module,
        "authoritative_low_batteries",
        lambda *args, **kwargs: [dict(item) for item in ROWS],
    )

    assert module.authoritative_low_battery_answer(fake, "turn on hallway") is None
    assert fake.rebuild_calls == []

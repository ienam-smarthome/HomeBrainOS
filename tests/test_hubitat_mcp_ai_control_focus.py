from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_focus_mode import (  # noqa: E402
    ControlFocusMode,
    is_control_followup,
    is_power_summary_query,
    is_verified_read_query,
)


class FakeMetricExecutor:
    async def execute(self, intent, *, query: str = ""):
        assert intent.metric == "power"
        assert intent.operation == "rank"
        return {
            "success": True,
            "message": "old ranking",
            "measurement_readings": [
                {
                    "id": "1",
                    "label": "Computer",
                    "room": "Multimedia",
                    "value": 77.0,
                    "aggregate": False,
                },
                {
                    "id": "2",
                    "label": "Fan Switch (Tuya Local)",
                    "room": "Ventilation",
                    "value": 14.9,
                    "aggregate": False,
                },
                {
                    "id": "3",
                    "label": "Halo3000x socket power",
                    "room": "Sockets",
                    "value": 7.3,
                    "aggregate": False,
                },
                {
                    "id": "4",
                    "label": "Fridge",
                    "room": "Appliances",
                    "value": 0.0,
                    "aggregate": False,
                },
            ],
            "technical": {
                "aggregate_readings": [
                    {
                        "label": "Whole home meter",
                        "value": 110.0,
                        "aggregate": True,
                    }
                ]
            },
        }


class FakeApplication:
    VERSION = "0.7.1"


def make_service(*, enabled: bool = True, reads: bool = True) -> ControlFocusMode:
    return ControlFocusMode(
        FakeApplication(),
        FakeMetricExecutor(),
        enabled=enabled,
        allow_verified_reads=reads,
    )


def test_show_power_consumption_is_a_verified_summary_not_a_device_name():
    assert is_power_summary_query("Show power consumption")
    assert is_power_summary_query("Show current power usage")
    assert is_power_summary_query("List power readings")
    assert not is_power_summary_query("Which device is using the most power?")

    answer = asyncio.run(make_service().power_summary("Show power consumption"))

    assert answer["success"] is True
    assert answer["route"] == "mcp-power-summary"
    assert answer["intent"] == "verified-power-summary"
    assert answer["active_power_total_w"] == 99.2
    assert [item["label"] for item in answer["active_power_readings"]] == [
        "Computer",
        "Fan Switch (Tuya Local)",
        "Halo3000x socket power",
    ]
    assert [item["label"] for item in answer["idle_power_readings"]] == ["Fridge"]
    assert "Computer: 77 W" in answer["message"]
    assert "Total across 3 active individual readings: 99.2 W" in answer["message"]
    assert "0 W / idle readings: Fridge" in answer["message"]
    assert "Whole-home meter: 110 W" in answer["message"]
    assert answer.get("model") is None


def test_control_focus_allows_controls_confirmations_and_verified_reads_only():
    service = make_service()

    assert service.allows("Turn off Bedroom 1 Light")
    assert service.allows("Make Livingroom Light 1 comfortable for watching TV")
    assert service.allows("Which device is using the most power?")
    assert service.allows("Are any devices offline or stale?")
    assert service.allows("Show power consumption")
    assert service.allows("Yes")
    assert service.allows("2")
    assert service.allows("Livingroom Light 2")
    assert not service.allows("What should I improve in the bathroom ventilation setup?")
    assert not service.allows("What are the three most important issues at home?")


def test_scope_response_is_clear_instead_of_fuzzy_device_matching():
    answer = make_service().scope_response("What should I improve in the bathroom?")

    assert answer["success"] is True
    assert answer["route"] == "control-focus"
    assert answer["intent"] == "control-focus-scope"
    assert "Device control and verified live reads only" in answer["display"]["subtitle"]
    assert "Broader AI analysis is disabled" in answer["message"]
    assert "closest matches" not in answer["message"].lower()


def test_control_focus_helpers_do_not_break_confirmation_or_status_queries():
    assert is_control_followup("No")
    assert is_control_followup("Livingroom Light 1")
    assert is_verified_read_query("Is Bedroom 1 Light on?")
    assert is_verified_read_query("Show all devices")
    assert is_verified_read_query("Which room is warmest?")


def test_release_configuration_and_late_installation_are_aligned():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    domains = (APP_DIR / "ai_evidence_domains.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    changelog = (ROOT / "hubitat-mcp-ai" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert 'version: "0.7.1"' in config
    assert 'RELEASE_VERSION = "0.7.1"' in entrypoint
    assert "control_focus_mode_enabled: true" in config
    assert "control_focus_allow_verified_reads: true" in config
    assert "install_control_focus_mode(" in domains
    assert "planner_module.is_ai_evidence_query = lambda _query: False" in domains
    assert "## 0.7.1" in changelog

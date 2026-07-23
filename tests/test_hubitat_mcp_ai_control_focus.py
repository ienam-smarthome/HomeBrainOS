from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import ai_evidence_planner as planner_module  # noqa: E402
from automation_recommendation import AutomationRecommendationService  # noqa: E402
from automation_recommendation_webui import (  # noqa: E402
    install_automation_recommendation_route_precedence,
)
from control_focus_mode import (  # noqa: E402
    ControlFocusMode,
    is_control_followup,
    is_power_summary_query,
    is_verified_read_query,
)
from control_focus_power_summary_safe import (  # noqa: E402
    install_control_focus_power_summary_safe,
)
from hybrid_assistant_mode import (  # noqa: E402
    OctopusEnergySummary,
    is_direct_control_query,
    is_hybrid_ai_query,
    is_octopus_energy_query,
)
from mcp_client import MCPToolResult  # noqa: E402


install_control_focus_power_summary_safe()


class FakeMetricExecutor:
    async def execute(self, intent, *, query: str = ""):
        assert intent.metric == "power"
        assert intent.operation == "rank"
        return {
            "success": True,
            "message": "old ranking",
            "measurement_readings": [
                {"id": "1", "label": "Computer", "room": "Multimedia", "value": 77.0, "aggregate": False},
                {"id": "2", "label": "Fan Switch (Tuya Local)", "room": "Ventilation", "value": 14.9, "aggregate": False},
                {"id": "3", "label": "Halo3000x socket power", "room": "Sockets", "value": 7.3, "aggregate": False},
                {"id": "4", "label": "Fridge", "room": "Appliances", "value": 0.0, "aggregate": False},
                {"id": "whole-home", "label": "Whole home meter", "room": "Energy", "value": 110.0, "aggregate": True},
            ],
            "technical": '{"aggregate_readings":[{"value":110.0}]}',
        }


class FakeApplication:
    VERSION = "0.8.1"


def make_service(*, enabled: bool = True, reads: bool = True) -> ControlFocusMode:
    return ControlFocusMode(FakeApplication(), FakeMetricExecutor(), enabled=enabled, allow_verified_reads=reads)


class FakeOctopusMCP:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def supported_arguments(self, _tool: str, desired: dict):
        return dict(desired)

    async def invalidate(self, _category: str):
        return None

    async def call_tool(self, name: str, arguments: dict):
        assert name == "hub_list_devices"
        self.calls.append(dict(arguments))
        detailed = bool(arguments.get("detailed"))
        if detailed:
            devices = [
                {"id": "p", "label": "Octopus Live Meter Display Power", "room": "Octopus Energy", "attributes": [{"name": "power", "currentValue": "540 W"}]},
                {"id": "t", "label": "Octopus Live Meter Display Today", "room": "Octopus Energy", "attributes": [{"name": "html", "currentValue": "<b>4.8 kWh</b><br>£1.48 today"}]},
                {"id": "y", "label": "Octopus Live Meter Display Yesterday", "room": "Octopus Energy", "attributes": [{"name": "display", "currentValue": "5.2 kWh · £1.61"}]},
                {"id": "w", "label": "Octopus Live Meter Display Week", "room": "Octopus Energy", "attributes": [{"name": "display", "currentValue": "31.7 kWh · £9.72"}]},
            ]
        else:
            devices = [
                {"id": "p", "label": "Octopus Live Meter Display Power", "room": "Octopus Energy", "currentStates": {"power": "540 W"}},
                {"id": "t", "label": "Octopus Live Meter Display Today", "room": "Octopus Energy", "currentStates": {}},
                {"id": "y", "label": "Octopus Live Meter Display Yesterday", "room": "Octopus Energy", "currentStates": {}},
                {"id": "w", "label": "Octopus Live Meter Display Week", "room": "Octopus Energy", "currentStates": {}},
            ]
        return MCPToolResult(name=name, arguments=arguments, raw={}, text="", data={"devices": devices}, is_error=False)


class FakeOctopusApplication:
    VERSION = "0.8.1"

    def __init__(self) -> None:
        self.mcp = FakeOctopusMCP()


def test_show_power_consumption_is_a_verified_summary_not_a_device_name():
    assert is_power_summary_query("Show power consumption")
    assert is_power_summary_query("Show current power usage")
    assert is_power_summary_query("List power readings")
    assert is_power_summary_query("show power")
    assert is_power_summary_query("show power devices")
    assert is_power_summary_query("show device power")
    assert not is_power_summary_query("Which device is using the most power?")

    answer = asyncio.run(make_service().power_summary("Show power consumption"))

    assert answer["success"] is True
    assert answer["route"] == "mcp-power-summary"
    assert answer["active_power_total_w"] == 99.2
    assert [item["label"] for item in answer["aggregate_power_readings"]] == ["Whole home meter"]
    assert "Computer: 77 W" in answer["message"]
    assert "Total across 3 active individual readings: 99.2 W" in answer["message"]
    assert "Whole-home meter: 110 W" in answer["message"]
    assert answer.get("model") is None


def test_hybrid_routing_keeps_controls_fast_and_sends_unhandled_reads_to_ai():
    assert is_direct_control_query("Turn on Bedroom 1 Light")
    assert is_direct_control_query("Set Livingroom Light 1 to 30%")
    assert is_direct_control_query("Make Livingroom Light 1 comfortable for watching TV")
    assert not is_direct_control_query("Show power consumption")
    assert not is_direct_control_query("Show octopus live meter display")
    assert not is_direct_control_query("Why is electricity usage high?")

    assert is_hybrid_ai_query("What should I improve in the bathroom ventilation setup?")
    assert is_hybrid_ai_query("Why is electricity usage high right now?")
    assert is_hybrid_ai_query("Tell me what looks unusual at home")
    assert not is_hybrid_ai_query("Turn on Bedroom 1 Light")
    assert not is_hybrid_ai_query("Show power consumption")
    assert not is_hybrid_ai_query("Show octopus live meter display")


def test_automation_recommendation_skill_precedes_universal_ai_fallback():
    query = "Suggest one useful automation for the devices I have"
    assert AutomationRecommendationService.matches(query)
    assert is_hybrid_ai_query(query)

    original = planner_module.is_ai_evidence_query
    planner_module.is_ai_evidence_query = is_hybrid_ai_query
    try:
        install_automation_recommendation_route_precedence()
        assert planner_module.is_ai_evidence_query(query) is False
        assert planner_module.is_ai_evidence_query("Why is electricity usage high right now?") is True
    finally:
        planner_module.is_ai_evidence_query = original


def test_octopus_family_and_period_queries_are_verified_fast_reads():
    assert is_octopus_energy_query("Show octopus live meter display")
    assert is_octopus_energy_query("Total power consumption today")
    assert is_octopus_energy_query("Show whole house energy this week")
    assert not is_octopus_energy_query("Show power consumption")

    app = FakeOctopusApplication()
    service = OctopusEnergySummary(app)

    today = asyncio.run(service.answer("Total power consumption today"))
    assert today["route"] == "mcp-octopus-energy"
    assert today["model"] is None
    assert [item["period"] for item in today["octopus_readings"]] == ["today"]
    assert "4.8 kWh" in today["message"]
    assert "£1.48" in today["message"]

    all_displays = asyncio.run(service.answer("Show octopus live meter display"))
    assert "Whole-house power: 540 W" in all_displays["message"]
    assert "Today: 4.8 kWh" in all_displays["message"]
    assert "Yesterday: 5.2 kWh" in all_displays["message"]
    assert len(all_displays["octopus_readings"]) == 4


def test_control_focus_remains_available_only_as_an_optional_restriction():
    service = make_service()
    assert service.allows("Turn off Bedroom 1 Light")
    assert service.allows("Which device is using the most power?")
    assert service.allows("Show power consumption")
    assert not service.allows("What should I improve in the bathroom ventilation setup?")

    answer = service.scope_response("What should I improve in the bathroom?")
    assert answer["route"] == "control-focus"
    assert "Broader AI analysis is disabled" in answer["message"]
    assert "closest matches" not in answer["message"].lower()


def test_control_focus_helpers_do_not_break_confirmation_or_status_queries():
    assert is_control_followup("No")
    assert is_control_followup("Livingroom Light 1")
    assert is_verified_read_query("Is Bedroom 1 Light on?")
    assert is_verified_read_query("Show all devices")
    assert is_verified_read_query("Which room is warmest?")


def test_release_configuration_and_hybrid_installation_are_aligned():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    domains = (APP_DIR / "ai_evidence_domains.py").read_text(encoding="utf-8")
    hybrid = (APP_DIR / "hybrid_assistant_mode.py").read_text(encoding="utf-8")
    safe_power = (APP_DIR / "control_focus_power_summary_safe.py").read_text(encoding="utf-8")
    automation_ui = (APP_DIR / "automation_recommendation_webui.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    changelog = (ROOT / "hubitat-mcp-ai" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "version:" in config
    assert "PREVIOUS_RELEASE_VERSION" in entrypoint
    assert "RELEASE_VERSION" in entrypoint
    assert "hybrid_assistant_mode_enabled: true" in config
    assert "control_focus_mode_enabled: false" in config
    assert "install_hybrid_assistant_query_policy()" in entrypoint
    assert "install_hybrid_verified_read_routes" in entrypoint
    assert 'option_bool("hybrid_assistant_mode_enabled", True)' in domains
    assert "restricted_focus_enabled" in domains
    assert "planner_module.is_ai_evidence_query = is_hybrid_ai_query" in hybrid
    assert "install_automation_recommendation_route_precedence()" in automation_ui
    assert 'isinstance(technical, dict)' in safe_power
    assert 'answer.get("measurement_readings")' in safe_power
    assert "# Hubitat MCP AI changelog" in changelog

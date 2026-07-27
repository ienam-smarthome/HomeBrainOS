from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from thermostat_summary_guard import (  # noqa: E402
    correct_thermostat_summary,
    install_thermostat_summary_guard,
)


def thermostat_device():
    return {
        "id": 4382,
        "label": "Thermostat",
        "currentStates": [
            {"name": "temperature", "currentValue": "24.0"},
            {"name": "heatingSetpoint", "currentValue": "12.0"},
            {"name": "thermostatSetpoint", "currentValue": "12.0"},
            {"name": "coolingSetpoint", "currentValue": "35.0"},
            {"name": "thermostatMode", "currentValue": "heat"},
        ],
    }


class Result:
    def __init__(self, data):
        self.is_error = False
        self.data = data


class MCP:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_list_devices":
            return Result(
                {
                    "devices": [
                        {
                            "id": 7001,
                            "label": "Bedroom 1 TRV",
                            "currentStates": [{"name": "temperature", "currentValue": "21.0"}],
                        },
                        {
                            "id": 4382,
                            "label": "Thermostat",
                            "currentStates": [{"name": "temperature", "currentValue": "24.0"}],
                        },
                    ]
                }
            )
        assert name == "hub_get_device"
        assert arguments == {"deviceId": "4382"}
        return Result({"device": thermostat_device()})


def test_corrects_measured_temperature_described_as_setpoint():
    message = "The living room is warm, and the thermostat is set to 24°C."
    corrected, evidence = correct_thermostat_summary(message, [thermostat_device()])

    assert "thermostat room temperature is 24°C" in corrected
    assert "heating setpoint is 12°C" in corrected
    assert "set to 24°C" not in corrected
    assert evidence == {
        "device": "Thermostat",
        "measured_temperature": 24.0,
        "heating_setpoint": 12.0,
        "claimed_setpoint": 24.0,
        "reason": "measured-temperature-was-described-as-setpoint",
    }


def test_does_not_change_a_correct_setpoint_statement():
    message = "The thermostat is set to 12°C."
    corrected, evidence = correct_thermostat_summary(message, [thermostat_device()])
    assert corrected == message
    assert evidence is None


def test_live_wrapper_updates_message_and_display_summary_from_mcp_state():
    async def original_ask(_request):
        message = "Everything is calm and the thermostat is set to 24°C."
        return {
            "success": True,
            "route": "ollama+mcp",
            "message": message,
            "display": {"summary": message},
        }

    mcp = MCP()
    application = SimpleNamespace(ask=original_ask, mcp=mcp, device_index=None)
    install_thermostat_summary_guard(application)
    answer = asyncio.run(application.ask(SimpleNamespace(query="What's happening?")))

    assert answer["thermostat_semantics_corrected"] is True
    assert "heating setpoint is 12°C" in answer["message"]
    assert answer["display"]["summary"] == answer["message"]
    assert mcp.calls == [
        ("hub_list_devices", {}),
        ("hub_get_device", {"deviceId": "4382"}),
    ]
    assert answer["thermostat_summary_guard_read"]["source"] == "hub_get_device"


def test_direct_thermostat_question_returns_live_temperature_and_setpoints():
    async def original_ask(_request):
        raise AssertionError("AI route should not run for direct thermostat state")

    mcp = MCP()
    application = SimpleNamespace(ask=original_ask, mcp=mcp, device_index=None)
    install_thermostat_summary_guard(application)
    answer = asyncio.run(
        application.ask(SimpleNamespace(query="What is the thermostat temperature and setpoint?"))
    )

    assert answer["route"] == "mcp-thermostat-live-state"
    assert "room temperature is 24°C" in answer["message"]
    assert "heating setpoint is 12°C" in answer["message"]
    assert "cooling setpoint is 35°C" in answer["message"]
    assert answer["display"]["metrics"][0]["label"] == "Room temperature"
    assert mcp.calls == [
        ("hub_list_devices", {}),
        ("hub_get_device", {"deviceId": "4382"}),
    ]
    assert [item["name"] for item in answer["tools_used"]] == [
        "hub_list_devices",
        "hub_get_device",
    ]


def test_exact_reported_setpoint_phrase_never_reaches_ai():
    async def original_ask(_request):
        raise AssertionError("AI route should not run for the exact setpoint question")

    mcp = MCP()
    application = SimpleNamespace(ask=original_ask, mcp=mcp, device_index=None)
    install_thermostat_summary_guard(application)
    answer = asyncio.run(
        application.ask(SimpleNamespace(query="What is the thermostat setpoint"))
    )

    assert answer["route"] == "mcp-thermostat-live-state"
    assert "heating setpoint is 12°C" in answer["message"]
    assert mcp.calls == [
        ("hub_list_devices", {}),
        ("hub_get_device", {"deviceId": "4382"}),
    ]


def test_runtime_bridge_uses_already_composed_thermostat_registry():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    bridge = (APP_DIR / "runtime_route_bridge.py").read_text(encoding="utf-8")

    assert '"summary-thermostat-registry"' in entrypoint
    assert entrypoint.index("auxiliary_request_layers.finalize()") < entrypoint.index(
        "install_runtime_route_bridge(_core.application)"
    )
    assert "install_thermostat_summary_guard(application)" not in bridge
    assert bridge.count("install_cancellable_ask(application)") == 1


def test_wrapper_ignores_unrelated_queries():
    async def original_ask(_request):
        return {"message": "The thermostat is set to 24°C."}

    application = SimpleNamespace(ask=original_ask)
    install_thermostat_summary_guard(application)
    answer = asyncio.run(application.ask(SimpleNamespace(query="Tell me a joke")))
    assert answer["message"] == "The thermostat is set to 24°C."

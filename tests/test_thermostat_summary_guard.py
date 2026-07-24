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


def test_live_wrapper_updates_message_and_display_summary():
    class Index:
        async def enriched_devices(self):
            return [thermostat_device()]

    async def original_ask(_request):
        message = "Everything is calm and the thermostat is set to 24°C."
        return {
            "success": True,
            "route": "ollama+mcp",
            "message": message,
            "display": {"summary": message},
        }

    application = SimpleNamespace(ask=original_ask, device_index=Index())
    install_thermostat_summary_guard(application)
    answer = asyncio.run(
        application.ask(SimpleNamespace(query="What's happening?"))
    )

    assert answer["thermostat_semantics_corrected"] is True
    assert "heating setpoint is 12°C" in answer["message"]
    assert answer["display"]["summary"] == answer["message"]


def test_wrapper_ignores_unrelated_queries():
    class Index:
        async def enriched_devices(self):
            raise AssertionError("device index should not be read")

    async def original_ask(_request):
        return {"message": "The thermostat is set to 24°C."}

    application = SimpleNamespace(ask=original_ask, device_index=Index())
    install_thermostat_summary_guard(application)
    answer = asyncio.run(application.ask(SimpleNamespace(query="Tell me a joke")))
    assert answer["message"] == "The thermostat is set to 24°C."

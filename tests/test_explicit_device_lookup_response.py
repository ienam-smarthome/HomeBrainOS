from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import (
    _apply_device_lookup_response_policy,
    _is_explicit_device_lookup,
)


class FakeAgent:
    async def _answer_from_targeted_device_search(self, query, history, error):
        return {
            "success": True,
            "route": "mcp-fast",
            "message": "The sensor is not reporting a lux value.",
            "mcp_response": {
                "devices": [
                    {
                        "id": "999",
                        "name": "Illuminance Sensor",
                        "label": "FP2 Bedroom 3 Lux",
                        "room": "Bedroom 3",
                        "disabled": False,
                        "currentStates": {},
                    }
                ]
            },
        }


def test_lookup_intent_does_not_include_value_question():
    assert _is_explicit_device_lookup("Find FP2 Bedroom 3 Lux")
    assert _is_explicit_device_lookup("Locate the front door sensor")
    assert not _is_explicit_device_lookup("What is the lux reading from FP2 Bedroom 3 Lux?")


@pytest.mark.asyncio
async def test_find_sensor_returns_identity_room_type_and_availability():
    application = SimpleNamespace(ollama=FakeAgent())
    planner_answer = {
        "message": "It is not currently reporting a lux value.",
        "tools_used": [{"name": "homebrain_search_devices", "success": True}],
    }
    result = await _apply_device_lookup_response_policy(
        application,
        "Find FP2 Bedroom 3 Lux",
        [],
        planner_answer,
    )
    assert result["message"] == (
        "Found FP2 Bedroom 3 Lux in Bedroom 3. "
        "Device type: Illuminance Sensor. Status: available."
    )
    assert result["lookup_response_policy_corrected"] is True
    assert result["lookup_device"]["id"] == "999"
    assert "not reporting" not in result["message"].lower()


@pytest.mark.asyncio
async def test_value_question_is_left_for_value_reading_route():
    application = SimpleNamespace(ollama=FakeAgent())
    answer = {
        "message": "Reading response",
        "tools_used": [{"name": "homebrain_search_devices", "success": True}],
    }
    result = await _apply_device_lookup_response_policy(
        application,
        "What is the lux reading from FP2 Bedroom 3 Lux?",
        [],
        answer,
    )
    assert result is answer

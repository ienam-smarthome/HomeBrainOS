from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import _answer_terminal_entity_read


class Result:
    def __init__(self, data):
        self.data = data
        self.is_error = False


class MCP:
    def __init__(self, current_states=None):
        self.current_states = (
            {"illuminance": 212} if current_states is None else current_states
        )

    async def supported_arguments(self, name, desired):
        return {"ids": desired["ids"]}

    async def call_tool(self, name, arguments):
        if name == "hub_list_devices":
            return Result({"devices": [{
                "id": "123",
                "name": "Illuminance Sensor",
                "label": "FP2 Bedroom 3 Lux",
                "room": "Bedroom 3",
                "disabled": False,
                "currentStates": {},
            }]})
        assert name == "hub_read_devices"
        assert arguments == {"ids": ["123"]}
        return Result({"devices": [{
            "id": "123",
            "label": "FP2 Bedroom 3 Lux",
            "currentStates": self.current_states,
        }]})


def app(current_states=None):
    return SimpleNamespace(mcp=MCP(current_states), VERSION="0.10.38")


def test_find_is_terminal_identity_lookup():
    answer = asyncio.run(_answer_terminal_entity_read(app(), "Find FP2 Bedroom 3 Lux"))
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "device-lookup"
    assert "Found FP2 Bedroom 3 Lux in Bedroom 3" in answer["message"]
    assert "lux value" not in answer["message"].lower()


def test_lux_question_reads_authoritative_attribute():
    answer = asyncio.run(_answer_terminal_entity_read(app(), "What is the lux reading from FP2 Bedroom 3 Lux?"))
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "device-attribute-read"
    assert answer["value"] == 212
    assert answer["message"] == "FP2 Bedroom 3 Lux is 212 lux."
    assert [item["name"] for item in answer["tools_used"]] == ["hub_list_devices", "hub_read_devices"]


def test_lux_question_reads_list_shaped_current_state_record():
    answer = asyncio.run(
        _answer_terminal_entity_read(
            app([{"name": "illuminance", "currentValue": 212}]),
            "What is the lux reading from FP2 Bedroom 3 Lux?",
        )
    )

    assert answer["success"] is True
    assert answer["value"] == 212
    assert answer["message"] == "FP2 Bedroom 3 Lux is 212 lux."


def test_lux_alias_and_zero_value_are_not_treated_as_missing():
    answer = asyncio.run(
        _answer_terminal_entity_read(
            app([{"attribute": "illuminanceLevel", "value": 0}]),
            "What is the illuminance value of FP2 Bedroom 3 Lux?",
        )
    )

    assert answer["success"] is True
    assert answer["value"] == 0
    assert answer["message"] == "FP2 Bedroom 3 Lux is 0 lux."

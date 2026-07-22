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
            "currentStates": {"illuminance": 212},
        }]})


def app():
    return SimpleNamespace(mcp=MCP(), VERSION="0.10.37")


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

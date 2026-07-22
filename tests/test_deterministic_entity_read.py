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
    return SimpleNamespace(mcp=MCP(current_states), VERSION="0.10.40")


class MultiDeviceMCP:
    def __init__(self, devices, states_by_id):
        self.devices = devices
        self.states_by_id = states_by_id
        self.read_ids = []

    async def supported_arguments(self, name, desired):
        return {"ids": desired["ids"]}

    async def call_tool(self, name, arguments):
        if name == "hub_list_devices":
            return Result({"devices": self.devices})
        assert name == "hub_read_devices"
        device_id = arguments["ids"][0]
        self.read_ids.append(device_id)
        device = next(item for item in self.devices if item["id"] == device_id)
        return Result({"devices": [{
            "id": device_id,
            "label": device["label"],
            "currentStates": self.states_by_id[device_id],
        }]})


def multi_device_app(devices, states_by_id):
    mcp = MultiDeviceMCP(devices, states_by_id)
    return SimpleNamespace(mcp=mcp, VERSION="0.10.40"), mcp


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


def test_named_humidity_read_prefers_attribute_capable_device_over_room_light():
    application, mcp = multi_device_app(
        [
            {"id": "light", "label": "Bathroom Light", "room": "Bathroom", "currentStates": {"switch": "off"}},
            {"id": "climate", "label": "Bathroom Climate Sensor", "room": "Bathroom", "currentStates": {"humidity": 46}},
        ],
        {
            "light": [{"name": "switch", "currentValue": "off"}],
            "climate": [{"name": "relativeHumidity", "currentValue": 46}],
        },
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "What is the bathroom humidity?"))

    assert answer["success"] is True
    assert answer["message"] == "Bathroom Climate Sensor is 46 %."
    assert mcp.read_ids == ["climate"]


def test_named_temperature_read_supports_natural_word_order():
    application, _ = multi_device_app(
        [{"id": "bedroom", "label": "Bedroom 1 Sensor", "room": "Bedroom 1", "currentStates": {"temperature": 21.5}}],
        {"bedroom": [{"attribute": "temp", "value": 21.5}]},
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "What temperature is Bedroom 1?"))

    assert answer["success"] is True
    assert answer["message"] == "Bedroom 1 Sensor is 21.5 °C."


def test_named_power_read_supports_how_much_wording():
    application, _ = multi_device_app(
        [{"id": "freezer", "label": "Freezer (MQTT)", "room": "Kitchen", "currentStates": {"switch": "on"}}],
        {"freezer": [
            {"name": "switch", "currentValue": "on"},
            {"name": "energy", "currentValue": 522.732},
            {"name": "power", "currentValue": 77},
        ]},
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "How much power is the freezer using?"))

    assert answer["success"] is True
    assert answer["value"] == 77
    assert answer["message"] == "Freezer (MQTT) is 77 W."
    assert [item["name"] for item in answer["tools_used"]] == ["hub_list_devices", "hub_read_devices"]


def test_named_power_read_accepts_sparse_mcp_inventory_aliases():
    class SparseInventoryMCP:
        def __init__(self):
            self.calls = []

        async def supported_arguments(self, name, desired):
            return {"deviceIds": desired["deviceIds"]}

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_list_devices":
                return Result({"items": [{
                    "deviceId": "5313",
                    "displayName": "Freezer (MQTT)",
                }]})
            assert name == "hub_read_devices"
            assert arguments == {"deviceIds": ["5313"]}
            return Result({"devices": [{
                "deviceId": "5313",
                "deviceLabel": "Freezer (MQTT)",
                "attributes": [
                    {"name": "switch", "currentValue": "on"},
                    {"name": "power", "currentValue": 77},
                ],
            }]})

    mcp = SparseInventoryMCP()
    application = SimpleNamespace(mcp=mcp, VERSION="0.10.40")

    answer = asyncio.run(_answer_terminal_entity_read(application, "How much power is the freezer using?"))

    assert answer["success"] is True
    assert answer["device_id"] == "5313"
    assert answer["device_label"] == "Freezer (MQTT)"
    assert answer["message"] == "Freezer (MQTT) is 77 W."
    assert [name for name, _ in mcp.calls] == ["hub_list_devices", "hub_read_devices"]


def test_aggregate_and_period_queries_remain_owned_by_semantic_reader():
    application, mcp = multi_device_app([], {})

    assert asyncio.run(_answer_terminal_entity_read(application, "Which device uses the most power?")) is None
    assert asyncio.run(_answer_terminal_entity_read(application, "How much energy did we use yesterday?")) is None
    assert mcp.read_ids == []

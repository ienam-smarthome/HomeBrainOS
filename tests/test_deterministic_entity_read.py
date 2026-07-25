from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import _answer_terminal_entity_read, _device_id, _room_metric_candidates


class Result:
    def __init__(self, data):
        self.data = data
        self.is_error = False


class MCP:
    def __init__(self, current_states=None):
        self.current_states = (
            {"illuminance": 212} if current_states is None else current_states
        )

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
        assert name == "hub_get_device"
        assert arguments == {"deviceId": "123"}
        return Result({"devices": [{
            "id": "123",
            "label": "FP2 Bedroom 3 Lux",
            "currentStates": self.current_states,
        }]})


def app(current_states=None):
    return SimpleNamespace(mcp=MCP(current_states), VERSION="0.10.41")


class MultiDeviceMCP:
    def __init__(self, devices, states_by_id):
        self.devices = devices
        self.states_by_id = states_by_id
        self.read_ids = []

    async def call_tool(self, name, arguments):
        if name == "hub_list_devices":
            return Result({"devices": self.devices})
        assert name == "hub_get_device"
        device_id = arguments["deviceId"]
        self.read_ids.append(device_id)
        device = next(item for item in self.devices if item["id"] == device_id)
        return Result({"devices": [{
            "id": device_id,
            "label": device["label"],
            "currentStates": self.states_by_id[device_id],
        }]})


def multi_device_app(devices, states_by_id):
    mcp = MultiDeviceMCP(devices, states_by_id)
    return SimpleNamespace(mcp=mcp, VERSION="0.10.41"), mcp


def test_find_is_terminal_identity_lookup():
    answer = asyncio.run(_answer_terminal_entity_read(app(), "Find FP2 Bedroom 3 Lux"))
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "device-lookup"
    assert "Found FP2 Bedroom 3 Lux in Bedroom 3" in answer["message"]
    assert "lux value" not in answer["message"].lower()


def test_find_all_devices_returns_complete_inventory_not_named_lookup_error():
    answer = asyncio.run(_answer_terminal_entity_read(app(), "find all devices"))

    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "device-inventory"
    assert answer["success"] is True
    assert answer["device_count"] == 1
    assert answer["message"] == "Found 1 selected Hubitat device. They are assigned across 1 room."
    assert answer["device_inventory"] == [
        {
            "id": "123",
            "label": "FP2 Bedroom 3 Lux",
            "room": "Bedroom 3",
            "device_type": "Illuminance Sensor",
            "disabled": False,
            "state": "State unavailable",
            "state_attribute": None,
            "state_available": False,
            "state_icon": "📱",
            "state_tone": "muted",
        }
    ]
    assert answer["display"]["title"] == "All Hubitat devices"
    assert answer["display"]["items"][0]["title"] == "FP2 Bedroom 3 Lux"
    assert answer["display"]["items"][0]["value"] == "State unavailable"
    assert [item["name"] for item in answer["tools_used"]] == ["hub_list_devices"]


def test_find_all_devices_projects_recognised_primary_states_without_detail_reads():
    devices = [
        {"id": "1", "label": "Kitchen Light", "currentStates": {"switch": "on"}},
        {"id": "2", "label": "Front Door", "currentStates": [{"name": "contact", "currentValue": "open"}]},
        {"id": "3", "label": "Hall Motion", "current_states": {"motion": {"value": "inactive"}}},
        {"id": "4", "label": "Study Sensor", "attributes": {"temperature": 21.5}},
        {"id": "5", "label": "Freezer", "states": [{"attribute": "power", "value": 77}]},
        {"id": "6", "label": "Old Plug", "currentStates": {"switch": "off"}, "disabled": True},
        {"id": "7", "label": "Hall Lux", "currentStates": {"illuminance": 212}},
    ]
    application, mcp = multi_device_app(devices, {})

    answer = asyncio.run(_answer_terminal_entity_read(application, "show all devices"))

    states = {
        item["label"]: (item["state"], item["state_attribute"], item["state_available"])
        for item in answer["device_inventory"]
    }
    assert states == {
        "Freezer": ("77 W", "power", True),
        "Front Door": ("Open", "contact", True),
        "Hall Lux": ("212 lux", "illuminance", True),
        "Hall Motion": ("Inactive", "motion", True),
        "Kitchen Light": ("On", "switch", True),
        "Old Plug": ("Disabled", None, False),
        "Study Sensor": ("21.5°C", "temperature", True),
    }
    assert mcp.read_ids == []
    assert [item["name"] for item in answer["tools_used"]] == ["hub_list_devices"]


def test_lux_question_reads_authoritative_attribute():
    answer = asyncio.run(_answer_terminal_entity_read(app(), "What is the lux reading from FP2 Bedroom 3 Lux?"))
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "device-attribute-read"
    assert answer["value"] == 212
    assert answer["message"] == "FP2 Bedroom 3 Lux is 212 lux."
    assert [item["name"] for item in answer["tools_used"]] == ["hub_list_devices", "hub_get_device"]


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
    assert answer["message"] == "Bathroom Climate humidity is 46%."
    assert mcp.read_ids == ["climate"]


def test_named_temperature_read_supports_natural_word_order():
    application, _ = multi_device_app(
        [{"id": "bedroom", "label": "Bedroom 1 Sensor", "room": "Bedroom 1", "currentStates": {"temperature": 21.5}}],
        {"bedroom": [{"attribute": "temp", "value": 21.5}]},
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "What temperature is Bedroom 1?"))

    assert answer["success"] is True
    assert answer["message"] == "Bedroom 1 Sensor is 21.5°C."


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
    assert [item["name"] for item in answer["tools_used"]] == ["hub_list_devices", "hub_get_device"]


def test_named_power_read_accepts_sparse_mcp_inventory_aliases():
    class SparseInventoryMCP:
        def __init__(self):
            self.calls = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_list_devices":
                return Result({"items": [{
                    "deviceId": "5313",
                    "displayName": "Freezer (MQTT)",
                }]})
            assert name == "hub_get_device"
            assert arguments == {"deviceId": "5313"}
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
    assert [name for name, _ in mcp.calls] == ["hub_list_devices", "hub_get_device"]


def test_named_power_read_accepts_current_state_value_key():
    application, _ = multi_device_app(
        [{"id": "freezer", "label": "Freezer (MQTT)", "room": "Kitchen"}],
        {"freezer": [{"name": "power", "currentState": 77}]},
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "How much power is the freezer using?"))

    assert answer["success"] is True
    assert answer["message"] == "Freezer (MQTT) is 77 W."


def test_room_metric_read_probes_bounded_candidates_until_attribute_is_found():
    application, mcp = multi_device_app(
        [
            {"id": "a", "label": "Environmental Sensor A", "room": {"name": "Bathroom"}},
            {"id": "b", "label": "Environmental Sensor B", "room": {"name": "Bathroom"}},
            {"id": "c", "label": "Kitchen Sensor", "room": {"name": "Kitchen"}},
            {"id": "d", "label": "Bathroom Light", "room": {"name": "Bathroom"}},
        ],
        {
            "a": [{"name": "temperature", "currentValue": 23.1}],
            "b": [{"name": "humidity", "currentValue": 61}],
            "c": [{"name": "humidity", "currentValue": 48}],
            "d": [{"name": "switch", "currentValue": "off"}],
        },
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "What is the bathroom humidity?"))

    assert answer["success"] is True
    assert answer["device_id"] == "b"
    assert answer["message"] == "Environmental B humidity is 61%."
    assert answer["devices_probed"] == 2
    assert mcp.read_ids == ["a", "b"]


def test_named_energy_read_uses_authoritative_device_detail():
    application, _ = multi_device_app(
        [{"id": "freezer", "label": "Freezer (MQTT)", "room": "Kitchen"}],
        {"freezer": [{"name": "energyMeter", "currentValue": 522.732}]},
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "How much energy is the freezer using?"))

    assert answer["success"] is True
    assert answer["message"] == "Freezer (MQTT) is 522.732 kWh."


def test_named_battery_read_uses_attribute_alias():
    application, _ = multi_device_app(
        [{"id": "contact", "label": "Hallway Contact", "room": "Hallway"}],
        {"contact": [{"key": "batteryLevel", "displayValue": 88}]},
    )

    answer = asyncio.run(_answer_terminal_entity_read(application, "What is the battery level of Hallway Contact?"))

    assert answer["success"] is True
    assert answer["message"] == "Hallway Contact is 88%."


def test_aggregate_and_period_queries_remain_owned_by_semantic_reader():
    application, mcp = multi_device_app([], {})

    assert asyncio.run(_answer_terminal_entity_read(application, "Which device uses the most power?")) is None
    assert asyncio.run(_answer_terminal_entity_read(application, "How much energy did we use yesterday?")) is None
    assert mcp.read_ids == []

def test_measurement_wording_formats_humidity_naturally():
    from mcp_agent_orchestrator import _format_attribute_message

    assert _format_attribute_message("Bathroom meter", "humidity", 66, "%") == "Bathroom humidity is 66%."


def test_measurement_wording_preserves_standard_unit_spacing():
    from mcp_agent_orchestrator import _format_attribute_message

    assert _format_attribute_message("Freezer (MQTT)", "power", 74, "W") == "Freezer (MQTT) is 74 W."
    assert _format_attribute_message("FP2 Bedroom 3 Lux", "illuminance", 212, "lux") == "FP2 Bedroom 3 Lux is 212 lux."
    assert _format_attribute_message("Bedroom meter", "temperature", 21.5, "°C") == "Bedroom meter is 21.5°C."


def test_compact_bathroom_meter_name_and_attribute_binding():
    application, mcp = multi_device_app(
        [
            {
                "id": "bathroom",
                "label": "Bathroom meter",
                "room": "Ventilation",
                "currentStates": {},
            },
            {
                "id": "bedroom",
                "label": "Bedroom 1 Meter",
                "room": "Bedroom 1",
                "currentStates": {},
            },
        ],
        {
            "bathroom": {"battery": 66},
            "bedroom": {"battery": 73},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the battery level of BathroomMeter?",
        )
    )

    assert answer["success"] is True
    assert answer["device_id"] == "bathroom"
    assert answer["device_label"] == "Bathroom meter"
    assert answer["value"] == 66
    assert answer["message"] == "Bathroom meter is 66%."
    assert mcp.read_ids == ["bathroom"]


def test_attribute_reader_does_not_switch_to_another_meter():
    application, mcp = multi_device_app(
        [
            {
                "id": "bathroom",
                "label": "Bathroom meter",
                "room": "Ventilation",
                "currentStates": {},
            },
            {
                "id": "bedroom",
                "label": "Bedroom 1 Meter",
                "room": "Bedroom 1",
                "currentStates": {},
            },
        ],
        {
            "bathroom": {},
            "bedroom": {"battery": 73},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the battery level of the bathroom meter?",
        )
    )

    assert answer["success"] is False
    assert answer["device_id"] == "bathroom"
    assert answer["device_label"] == "Bathroom meter"
    assert "did not expose a current battery value" in answer["message"]
    assert "Bedroom 1 Meter" not in answer["message"]
    assert "73%" not in answer["message"]
    assert mcp.read_ids == ["bathroom"]


def test_similarly_scored_meter_names_require_clarification():
    application, mcp = multi_device_app(
        [
            {
                "id": "bedroom-1",
                "label": "Bedroom 1 Meter",
                "room": "Bedroom 1",
                "currentStates": {},
            },
            {
                "id": "bedroom-2",
                "label": "Bedroom 2 Meter",
                "room": "Bedroom 2",
                "currentStates": {},
            },
        ],
        {
            "bedroom-1": {"battery": 73},
            "bedroom-2": {"battery": 81},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the battery level of the bedroom meter?",
        )
    )

    assert answer["success"] is False
    assert answer["intent"] == "device-resolution-ambiguous"
    assert answer["confirmation_required"] is True
    assert set(answer["alternatives"]) == {
        "Bedroom 1 Meter",
        "Bedroom 2 Meter",
    }
    assert answer["entity_resolution"]["status"] == "ambiguous"
    assert mcp.read_ids == []


def test_exact_ordinal_meter_name_resolves_without_clarification():
    application, mcp = multi_device_app(
        [
            {
                "id": "bedroom-1",
                "label": "Bedroom 1 Meter",
                "room": "Bedroom 1",
                "currentStates": {},
            },
            {
                "id": "bedroom-2",
                "label": "Bedroom 2 Meter",
                "room": "Bedroom 2",
                "currentStates": {},
            },
        ],
        {
            "bedroom-1": {"battery": 73},
            "bedroom-2": {"battery": 81},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the battery level of Bedroom 2 Meter?",
        )
    )

    assert answer["success"] is True
    assert answer["device_id"] == "bedroom-2"
    assert answer["device_label"] == "Bedroom 2 Meter"
    assert answer["value"] == 81
    assert mcp.read_ids == ["bedroom-2"]


def test_live_reader_infers_room_prefix_before_device_resolution():
    application, mcp = multi_device_app(
        [
            {
                "id": "trv",
                "label": "Bedroom 2 TRV",
                "room": "Bedroom 2",
                "currentStates": {},
            },
            {
                "id": "mqtt",
                "label": "Bedroom2 (MQTT)",
                "room": "Bedroom 2",
                "currentStates": {},
            },
        ],
        {
            "trv": {"battery": 71},
            "mqtt": {"battery": 64},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the battery level of Bedroom 2 Meter?",
        )
    )

    assert answer["success"] is False
    assert answer["intent"] == "device-attribute-read"
    assert 'could not find a device matching "Bedroom 2 Meter"' in answer["message"]
    assert answer["entity_resolution"]["status"] == "not_found"
    assert mcp.read_ids == []


def test_live_reader_resolves_exact_meter_after_room_prefix_inference():
    application, mcp = multi_device_app(
        [
            {
                "id": "trv",
                "label": "Bedroom 2 TRV",
                "room": "Bedroom 2",
                "currentStates": {},
            },
            {
                "id": "meter",
                "label": "Bedroom 2 Meter",
                "room": "Bedroom 2",
                "currentStates": {},
            },
        ],
        {
            "trv": {"battery": 71},
            "meter": {"battery": 82},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the battery level of Bedroom 2 Meter?",
        )
    )

    assert answer["success"] is True
    assert answer["device_id"] == "meter"
    assert answer["value"] == 82
    assert mcp.read_ids == ["meter"]


def test_room_metric_candidates_are_confined_to_exact_room():
    candidates = _room_metric_candidates(
        [
            {
                "id": "bathroom-meter",
                "label": "Bathroom Meter",
                "room": "Bathroom",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
            {
                "id": "bedroom-meter",
                "label": "Bedroom Meter",
                "room": "Bedroom 2",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
            {
                "id": "bathroom-light",
                "label": "Bathroom Light",
                "room": "Bathroom",
                "capabilities": ["Switch"],
            },
        ],
        "Bathroom",
        "humidity",
    )

    assert [str(_device_id(item)) for item in candidates] == [
        "bathroom-meter",
    ]


def test_room_metric_candidates_prefer_attribute_compatible_device():
    candidates = _room_metric_candidates(
        [
            {
                "id": "light",
                "label": "Bathroom Light",
                "room": "Bathroom",
                "capabilities": ["Switch"],
            },
            {
                "id": "meter",
                "label": "Bathroom Meter",
                "room": "Bathroom",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
        ],
        "Bathroom",
        "humidity",
    )

    assert str(_device_id(candidates[0])) == "meter"


def test_room_metric_candidates_do_not_use_partial_room_matches():
    candidates = _room_metric_candidates(
        [
            {
                "id": "bedroom-2",
                "label": "Bedroom 2 Meter",
                "room": "Bedroom 2",
            },
            {
                "id": "bedroom-20",
                "label": "Bedroom 20 Meter",
                "room": "Bedroom 20",
            },
        ],
        "Bedroom 2",
        "temperature",
    )

    assert [str(_device_id(item)) for item in candidates] == ["bedroom-2"]


def test_natural_room_humidity_question_uses_complete_room_name():
    application, mcp = multi_device_app(
        [
            {
                "id": "bathroom-meter",
                "label": "Bathroom Meter",
                "room": "Bathroom",
                "capabilities": ["RelativeHumidityMeasurement"],
                "currentStates": {},
            },
            {
                "id": "bedroom-meter",
                "label": "Bedroom Meter",
                "room": "Bedroom 2",
                "capabilities": ["RelativeHumidityMeasurement"],
                "currentStates": {},
            },
        ],
        {
            "bathroom-meter": {"humidity": 61},
            "bedroom-meter": {"humidity": 48},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the humidity in the bathroom?",
        )
    )

    assert answer["success"] is True
    assert answer["attribute"] == "humidity"
    assert answer["value"] == 61
    assert answer["device_id"] == "bathroom-meter"
    assert mcp.read_ids == ["bathroom-meter"]


def test_attribute_target_phrase_returns_complete_room_for_room_metric():
    from mcp_agent_orchestrator import _attribute_target_phrase

    assert (
        _attribute_target_phrase(
            "What is the humidity in the bathroom?"
        )
        == "bathroom"
    )


def test_attribute_target_phrase_preserves_living_room():
    from mcp_agent_orchestrator import _attribute_target_phrase

    assert (
        _attribute_target_phrase(
            "What is the temperature in the Living Room?"
        )
        == "living room"
    )


def test_room_metric_inventory_value_is_ranked_first():
    candidates = _room_metric_candidates(
        [
            {
                "id": "capability-only",
                "label": "Bathroom Climate",
                "room": "Bathroom",
                "capabilities": ["RelativeHumidityMeasurement"],
                "currentStates": {},
            },
            {
                "id": "live-value",
                "label": "Bathroom Meter",
                "room": "Bathroom",
                "currentStates": {"humidity": 59},
            },
        ],
        "Bathroom",
        "humidity",
    )

    assert str(_device_id(candidates[0])) == "live-value"


def test_room_metric_excludes_unrelated_devices_when_supported_device_exists():
    candidates = _room_metric_candidates(
        [
            {
                "id": "light",
                "label": "Bathroom Light",
                "room": "Bathroom",
                "capabilities": ["Switch"],
            },
            {
                "id": "presence",
                "label": "Bathroom Presence",
                "room": "Bathroom",
                "capabilities": ["PresenceSensor"],
            },
            {
                "id": "humidity",
                "label": "Bathroom Climate",
                "room": "Bathroom",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
        ],
        "Bathroom",
        "humidity",
    )

    assert [str(_device_id(item)) for item in candidates] == ["humidity"]


def test_room_metric_never_probes_supported_device_from_another_room():
    application, mcp = multi_device_app(
        [
            {
                "id": "bathroom-light",
                "label": "Bathroom Light",
                "room": "Bathroom",
                "capabilities": ["Switch"],
            },
            {
                "id": "bedroom-meter",
                "label": "Bedroom Meter",
                "room": "Bedroom 2",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
        ],
        {
            "bathroom-light": {"switch": "off"},
            "bedroom-meter": {"humidity": 48},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the humidity in the bathroom?",
        )
    )

    assert answer["success"] is False
    assert "No device in Bathroom exposed a current humidity value." == answer["message"]
    assert "bedroom-meter" not in mcp.read_ids


def test_room_metric_reports_room_when_no_candidate_exposes_value():
    application, mcp = multi_device_app(
        [
            {
                "id": "sensor-a",
                "label": "Aqara Hi-P Sensor",
                "room": "Bathroom",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
            {
                "id": "sensor-b",
                "label": "Bathroom Environment",
                "room": "Bathroom",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
        ],
        {
            "sensor-a": {"presence": "present"},
            "sensor-b": {"temperature": 27.8},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the humidity in the bathroom?",
        )
    )

    assert answer["success"] is False
    assert answer["device_id"] == ""
    assert answer["device_label"] == "Bathroom"
    assert answer["message"] == (
        "No device in Bathroom exposed a current humidity value."
    )
    assert mcp.read_ids == ["sensor-a", "sensor-b"]


def test_named_device_read_remains_single_target_only():
    application, mcp = multi_device_app(
        [
            {
                "id": "named",
                "label": "Bathroom Meter",
                "room": "Ventilation",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
            {
                "id": "other",
                "label": "Ventilation Climate",
                "room": "Ventilation",
                "capabilities": ["RelativeHumidityMeasurement"],
            },
        ],
        {
            "named": {"humidity": 59},
            "other": {"humidity": 48},
        },
    )

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "What is the humidity of Bathroom Meter?",
        )
    )

    assert answer["success"] is True
    assert answer["device_id"] == "named"
    assert answer["value"] == 59
    assert mcp.read_ids == ["named"]

from __future__ import annotations
import sys
from pathlib import Path
APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path: sys.path.insert(0, str(APP))
from entity_request_policy import is_targeted_device_request, parse_entity_request

def test_targeted_fan_switch():
    r = parse_entity_request("Find Fan Switch")
    assert r.targeted and r.target_phrase == "fan switch" and r.device_type == "fan"

def test_numbered_living_room_light():
    r = parse_entity_request("Check the second living room light")
    assert r.targeted and r.ordinal == 2 and r.device_type == "light"

def test_sensor_lookup_is_targeted():
    r = parse_entity_request("Find FP2 Bedroom 3 Lux")
    assert r.targeted and r.target_phrase == "fp2 bedroom 3 lux"

def test_room_inventory_is_broad_not_targeted():
    r = parse_entity_request("Show devices in the living room")
    assert r.broad_inventory and not r.targeted


def test_room_first_inventory_is_broad_and_preserves_room():
    for query in ("Find hallway devices", "Show hallway devices"):
        r = parse_entity_request(query)
        assert r.broad_inventory
        assert not r.targeted
        assert r.room == "hallway"


def test_generic_inventory_is_not_targeted():
    assert not is_targeted_device_request("List all devices")


def test_attribute_question_preserves_complete_bathroom_room():
    request = parse_entity_request(
        "What is the humidity in the bathroom?"
    )

    assert request.room == "bathroom"
    assert request.target_phrase == "humidity"


def test_attribute_question_preserves_numbered_room():
    request = parse_entity_request(
        "What is the temperature in Bedroom 2?"
    )

    assert request.room == "bedroom 2"
    assert request.target_phrase == "temperature"


def test_from_room_clause_is_removed_without_truncation():
    request = parse_entity_request(
        "Read humidity from the Living Room"
    )

    assert request.room == "living room"
    assert request.target_phrase == "humidity"

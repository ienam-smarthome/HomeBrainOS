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

def test_generic_inventory_is_not_targeted():
    assert not is_targeted_device_request("List all devices")

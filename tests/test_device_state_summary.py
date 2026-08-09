from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_state_summary import device_attributes, is_light_device  # noqa: E402


def test_device_attributes_merges_all_hubitat_state_shapes():
    device = {
        "attributes": [{"name": "battery", "currentValue": 14}],
        "currentStates": [
            {"name": "presence", "currentValue": "present"},
            {"name": "motion", "value": "active"},
        ],
        "states": {"contact": "open"},
    }

    assert device_attributes(device) == {
        "battery": 14,
        "presence": "present",
        "motion": "active",
        "contact": "open",
    }


def test_later_live_state_overrides_older_attribute_value():
    device = {
        "attributes": {"switch": "off"},
        "states": {"switch": "off"},
        "currentStates": [{"name": "switch", "currentValue": "on"}],
    }

    assert device_attributes(device)["switch"] == "on"


def test_null_value_backfills_from_valuestr_when_numeric():
    """Regression test for a real live failure: Octopus Energy sensors
    (and other Home-Assistant-bridged devices) report a reading only as a
    human-formatted valueStr ("231 W") with value always null, so a power
    query silently had no numeric reading to work with despite the data
    being right there.
    """

    device = {
        "attributes": [
            {"name": "value", "dataType": "NUMBER", "value": None},
            {"name": "valueStr", "dataType": "STRING", "value": "231 W"},
            {"name": "unit", "dataType": "STRING", "value": "none"},
        ],
    }

    attrs = device_attributes(device)

    assert attrs["value"] == 231.0
    assert attrs["valueStr"] == "231 W"


def test_null_value_with_non_numeric_valuestr_is_left_null():
    device = {
        "attributes": [
            {"name": "value", "value": None},
            {"name": "valueStr", "value": "no data yet"},
        ],
    }

    assert device_attributes(device)["value"] is None


def test_real_numeric_value_is_never_overwritten_by_valuestr():
    device = {
        "attributes": [
            {"name": "value", "value": 42},
            {"name": "valueStr", "value": "999 W"},
        ],
    }

    assert device_attributes(device)["value"] == 42


def test_is_light_device_recognises_a_color_bulb_with_no_light_capability_token():
    """Regression test: is_light_device() used to do a crude substring
    search over str(capabilities) for "light"/"bulb" only -- a color bulb
    that advertises ColorControl/ColorTemperature but no capability
    literally containing "light" or "bulb" (a real, common Hubitat
    driver shape) was silently excluded, while device_query_service's own
    separate _matches_device_kind("light") check already correctly
    included it. Both call paths must agree.
    """

    color_bulb = {
        "id": "1",
        "label": "Living Room Bulb",
        "capabilities": ["ColorControl", "ColorTemperature", "Switch"],
    }

    assert is_light_device(color_bulb) is True


def test_is_light_device_recognises_a_lamp_labelled_device_with_no_light_capability():
    """A device labelled "lamp" with only a bare Switch capability (no
    Light/Bulb/ColorControl/ColorTemperature token at all) is still a
    light in every practical sense -- device_query_service's
    _matches_device_kind already covered this via a label check;
    is_light_device() must match it too.
    """

    lamp = {
        "id": "2",
        "label": "Bedroom Lamp",
        "capabilities": ["Switch"],
    }

    assert is_light_device(lamp) is True


def test_is_light_device_excludes_an_ordinary_switch():
    plain_switch = {
        "id": "3",
        "label": "Hallway Switch",
        "capabilities": ["Switch"],
    }

    assert is_light_device(plain_switch) is False

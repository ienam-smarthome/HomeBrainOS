from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_control_service import DeviceControlService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


# Real hallway devices pulled live from the actual Hubitat hub via
# hub_get_device -- this exact pair is what "hallway lights at 11:11pm"
# should resolve to once the smuggled time is stripped.
HALLWAY_LIGHT_1 = {
    "id": "7046", "label": "Hallway Light 1", "roomName": "Hallway",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
HALLWAY_LIGHT_2 = {
    "id": "7037", "label": "Hallway Light 2", "roomName": "Hallway",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
# A real same-room device that is NOT a light, despite advertising Switch --
# "the hallway lights" must exclude this even though it lives in the same
# room, the same way "the lights" (house-wide) already excludes non-light
# switches elsewhere in this file.
HALLWAY_TRV = {
    "id": "7331", "label": "Hallway TRV", "roomName": "Hallway",
    "capabilities": ["Actuator", "Refresh", "Switch", "Thermostat"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


class ControlMCP:
    def __init__(self, devices):
        self.devices = devices
        self.calls = []

    async def get_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_call_device_command":
            command = arguments["args"]["command"]
            return MCPToolResult(
                "hub_manage_devices", arguments, {}, "ok",
                {"success": True, "waitFor": {"converged": True, "value": command}},
            )
        if arguments.get("tool") == "hub_list_devices":
            return MCPToolResult(
                "hub_read_devices", arguments, {}, "ok", {"devices": self.devices}
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))


def recorder(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_smuggled_time_in_device_names_is_refused_not_misexecuted():
    """The bug this guards: a request like 'turn on hallway lights at
    11:11pm' has no dedicated time parameter on this tool, so the model
    puts the whole phrase into device_names. Executing on that raw string
    either silently ignores the requested time and acts immediately (wrong)
    or fails to resolve the device at all because the name is corrupted
    (confusing). Neither is acceptable; this must refuse with a clear
    explanation instead.
    """

    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["hallway lights at 11:11pm"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.is_error is True
    assert result.data["success"] is False
    assert result.data["requested_time"] == "23:11"
    assert "one-time" in result.data["error"].lower() or "one-off" in result.data["error"].lower()
    # Must not have attempted to execute anything against the hub.
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_smuggled_time_in_room_is_also_refused():
    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "hallway at 6am",
        "device_names": [],
        "device_kind": "light",
        "command": "off",
    })

    assert result.is_error is True
    assert result.data["requested_time"] == "06:00"
    assert result.data["room"] == "hallway"
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_normal_immediate_command_is_unaffected_by_the_time_check():
    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Hallway Light 1"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.data["success"] is True
    assert result.data["executed"] == 1
    assert result.data["succeeded"][0]["id"] == "7046"
    executed_commands = [
        arguments for gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    ]
    assert len(executed_commands) == 1
    assert executed_commands[0]["args"]["command"] == "on"


@pytest.mark.asyncio
async def test_invalid_arguments_still_rejected_before_the_time_check():
    mcp = ControlMCP([HALLWAY_LIGHT_1])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Hallway Light 1"],
        "room": "Hallway",  # both room and device_names set -- invalid
        "device_kind": "auto",
        "command": "on",
    })

    assert result.is_error is True
    assert "Provide exactly one of room or device_names" in result.data["error"]


TOILET_LIGHT = {
    "id": "9001", "label": "Toilet Light", "roomName": "Toilet",
    "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


@pytest.mark.asyncio
async def test_smuggled_second_action_is_stripped_and_the_routine_part_still_runs():
    """Regression test for a real live production failure: "turn off toilet
    light and restart the hub" was sent to this tool as a single call with
    device_names=["toilet light and restart the hub"]. A prompt-only fix
    (0.10.356) asked the model not to do this, but the same live model kept
    doing it anyway -- so this is the deterministic backstop: strip the
    recognisable second action, execute the routine part against the
    correctly-resolved device, and tell the user the second action needs
    its own request rather than silently dropping it or corrupting
    resolution."""

    mcp = ControlMCP([TOILET_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["toilet light and restart the hub"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    assert result.data["succeeded"][0]["id"] == "9001"
    assert "restart the hub" in result.data["note"]
    assert "ask for it separately" in result.data["note"]
    executed_commands = [
        arguments for gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    ]
    assert len(executed_commands) == 1
    assert executed_commands[0]["args"]["command"] == "off"
    # The hub must never actually be restarted from this regex match --
    # only the device command tool is called.
    assert all(
        arguments.get("tool") != "hub_restart" for _gateway, arguments in mcp.calls
    )


@pytest.mark.asyncio
async def test_ordinary_device_name_with_no_second_action_is_unaffected():
    mcp = ControlMCP([TOILET_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["toilet light"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    assert "note" not in result.data


BEDROOM1_LIGHT = {
    "id": "7057", "label": "Bedroom 1 Light", "roomName": "Bedroom 1",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
BEDROOM1_FLOOR_LAMP = {
    "id": "7028", "label": "My Floor Lamp", "roomName": "Bedroom 1",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
# Real device pulled live from the actual hub: a smart plug whose label
# normalizes to exactly the same string as the room "Bedroom 1" once its
# "(MQTT)" qualifier is stripped, but which lives in a different room
# ("Sockets"), not "Bedroom 1" at all.
BEDROOM1_MQTT_SOCKET = {
    "id": "7101", "label": "Bedroom1 (MQTT)", "roomName": "Sockets",
    "capabilities": ["Actuator", "Refresh", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


@pytest.mark.asyncio
async def test_room_name_in_device_names_acts_on_the_room_not_a_lookalike_device():
    """Regression test for a real live failure: "turn off Bedroom 1" (a
    real room containing two lights) resolved to a single, unrelated smart
    plug labelled "Bedroom1 (MQTT)" living in a different room, because
    that label happens to normalize to the exact same string as the room
    name and ordinary per-name fuzzy resolution has no room awareness.
    """

    mcp = ControlMCP([BEDROOM1_LIGHT, BEDROOM1_FLOOR_LAMP, BEDROOM1_MQTT_SOCKET])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Bedroom 1"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"7057", "7028"}
    assert "7101" not in succeeded_ids


@pytest.mark.asyncio
async def test_room_plus_lights_suffix_acts_on_every_light_in_that_room_only():
    """Regression test for a real live failure: "turn off the hallway
    lights" fell into ordinary per-name fuzzy resolution (nothing is
    literally labelled "the hallway lights"), which correctly scored every
    "Hallway *" device -- including Hallway TRV, a thermostat that isn't a
    light -- below the confidence floor and reported "Unresolved" with a
    three-way disambiguation offer instead of doing the obviously intended
    room+kind action: turn off every light in the Hallway, and only the
    lights.
    """

    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2, HALLWAY_TRV, BEDROOM1_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["the hallway lights"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"7046", "7037"}
    assert "7331" not in succeeded_ids
    assert "7057" not in succeeded_ids


@pytest.mark.asyncio
async def test_room_plus_switches_suffix_matches_switch_kind_not_lights():
    """The kind word in the suffix must actually gate the result: "hallway
    switches" should behave like device_kind="switch", not "light" -- the
    opposite selection from the "hallway lights" test above, using the
    same three-device room to prove the kind word (not just the room) is
    what determines the result.
    """

    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2, HALLWAY_TRV])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["the hallway switches"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    # device_kind="switch" means Switch-capable AND NOT a light (see
    # _matches_kind's docstring) -- Hallway Light 1/2 are excluded even
    # though they also advertise Switch, leaving only the TRV.
    assert succeeded_ids == {"7331"}


@pytest.mark.asyncio
async def test_a_real_device_name_ending_in_light_is_unaffected():
    """The room+kind-suffix pattern must not hijack an ordinary device name
    that happens to end in the word "Light" (or "Lights") -- "Kitchen
    Light" is a real device label, not a room name, so it must keep
    reaching ordinary per-name resolution untouched.
    """

    mcp = ControlMCP([KITCHEN_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Kitchen Light"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"8001"}


KITCHEN_LIGHT = {
    "id": "8001", "label": "Kitchen Light", "roomName": "Kitchen",
    "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
# A real non-light switch/plug -- "turn off the lights" must never touch
# this even though it shares the generic switch capability every light also
# has.
TV_PLUG = {
    "id": "4221", "label": "TV", "roomName": "Living Room",
    "capabilities": ["Actuator", "Refresh", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


@pytest.mark.asyncio
async def test_bare_the_lights_target_acts_on_every_light_house_wide():
    """Regression test for a real live failure: "turn off the lights"
    (no room, no device name -- an unqualified whole-house request) fell
    into ordinary per-name fuzzy resolution, which has nothing literally
    named "the lights" to match, and reported "Unresolved" with an
    unrelated disambiguation offer (Livingroom TRV / Block Tab-S9-FE /
    Fridge) instead of doing the obviously intended thing: turn off every
    light in the house. A non-light switch/plug (the TV) must not be
    touched by this even though it shares the generic switch capability.
    """

    mcp = ControlMCP([BEDROOM1_LIGHT, KITCHEN_LIGHT, TV_PLUG])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["the lights"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"7057", "8001"}
    assert "4221" not in succeeded_ids


@pytest.mark.asyncio
async def test_all_lights_phrasing_variants_all_resolve_house_wide():
    mcp = ControlMCP([BEDROOM1_LIGHT, KITCHEN_LIGHT])
    service = DeviceControlService(mcp, recorder)

    for phrase in ("all lights", "all the lights", "every light", "the light"):
        result = await service.execute({
            "device_names": [phrase],
            "device_kind": "auto",
            "command": "on",
        })
        succeeded_ids = {item["id"] for item in result.data["succeeded"]}
        assert succeeded_ids == {"7057", "8001"}, phrase


@pytest.mark.asyncio
async def test_no_lights_in_the_house_reports_a_clear_error():
    mcp = ControlMCP([TV_PLUG])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["the lights"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.is_error is True
    assert "No lights were found" in result.data["error"]
    # A live lookup is allowed to confirm no lights exist, but no command
    # dispatch must ever be attempted.
    assert all(
        arguments.get("tool") != "hub_call_device_command"
        for _gateway, arguments in mcp.calls
    )


@pytest.mark.asyncio
async def test_named_light_is_unaffected_by_the_all_lights_target():
    """A specific named light must keep going through ordinary per-name
    resolution -- only the closed set of unqualified aggregate phrasings
    ("the lights", "all lights", etc.) triggers the house-wide path.
    """

    mcp = ControlMCP([KITCHEN_LIGHT, BEDROOM1_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Kitchen Light"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"8001"}


ALREADY_OFF_TOILET_LIGHT = {
    "id": "9002", "label": "Toilet Light", "roomName": "Toilet",
    "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "off"}],
}


@pytest.mark.asyncio
async def test_already_in_state_devices_are_flagged_but_still_commanded():
    """A device whose cached state already matches the requested command
    must still receive the command -- the cache can be stale, and skipping
    a device because it looked "already off" risks silently leaving a
    genuinely-on light untouched. It must, however, come back flagged
    (changed=False) so the presenter can report it separately instead of
    claiming the assistant "turned off" a light that was never on.
    """

    mcp = ControlMCP([BEDROOM1_LIGHT, ALREADY_OFF_TOILET_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["the lights"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    by_id = {item["id"]: item for item in result.data["succeeded"]}
    assert by_id["7057"]["changed"] is True
    assert by_id["7057"]["already_in_state"] is False
    assert by_id["9002"]["changed"] is False
    assert by_id["9002"]["already_in_state"] is True
    # The command must still have been dispatched to the already-off light,
    # not silently skipped.
    dispatched_ids = {
        arguments["args"]["deviceId"]
        for _gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    }
    assert dispatched_ids == {"7057", "9002"}


@pytest.mark.asyncio
async def test_unknown_prior_state_defaults_to_changed():
    """A device with no cached switch attribute at all (identity read
    failed, or a driver that doesn't report it) must default to being
    reported as changed -- silence on prior state must never be
    misread as "already in the requested state" and dropped from the
    summary.
    """

    device_with_unknown_state = {
        "id": "9003", "label": "Mystery Light", "roomName": "Toilet",
        "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    }
    mcp = ControlMCP([device_with_unknown_state])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Mystery Light"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["succeeded"][0]["changed"] is True
    assert result.data["succeeded"][0]["already_in_state"] is False


class LabelFilterControlMCP(ControlMCP):
    """Same as ControlMCP, except get_cached_devices() and a labelFilter
    hub_list_devices lookup are genuinely distinct -- get_cached_devices
    always returns the full inventory (simulating a stale/empty identity
    cache forcing the live fallback path), while a labelFilter lookup
    returns only devices whose label contains it (simulating the real
    Hubitat gateway's own filtering). The plain ControlMCP above ignores
    labelFilter entirely and returns everything regardless, which can't
    reproduce the live "narrow lookup vs. broad manifest" bug this class
    exists to test.
    """

    async def get_cached_devices(self):
        return []

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_call_device_command":
            command = arguments["args"]["command"]
            return MCPToolResult(
                "hub_manage_devices", arguments, {}, "ok",
                {"success": True, "waitFor": {"converged": True, "value": command}},
            )
        if arguments.get("tool") == "hub_list_devices":
            label_filter = (arguments.get("args") or {}).get("labelFilter")
            if label_filter:
                matched = [
                    d for d in self.devices
                    if label_filter.casefold() in str(d.get("label", "")).casefold()
                ]
                return MCPToolResult(
                    "hub_read_devices", arguments, {}, "ok", {"devices": matched}
                )
            return MCPToolResult(
                "hub_read_devices", arguments, {}, "ok", {"devices": self.devices}
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))

    async def full_manifest(self):
        return list(self.devices)


class FieldDefaultingControlMCP(LabelFilterControlMCP):
    """Same as LabelFilterControlMCP, except it also reproduces a second,
    real-Hubitat-gateway behaviour that the plain mocks above never
    modelled: hub_list_devices only includes "capabilities" (and other
    detail fields) when the caller explicitly asks for them via a
    "fields" argument -- call it without one and real device payloads
    come back missing "capabilities" entirely. The labelFilter-scoped and
    room-wide/all-lights lookups in device_control_service.py didn't ask
    for "fields" before 0.10.386, so on a real deployment those lookups
    silently produced capability-less devices; every kind check
    (_is_switch_device / is_light_device, both keyed on "capabilities")
    then failed for otherwise-correct candidates, emptying `eligible` and
    firing the broad full-manifest retry regardless of how good the narrow
    match was.
    """

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_call_device_command":
            command = arguments["args"]["command"]
            return MCPToolResult(
                "hub_manage_devices", arguments, {}, "ok",
                {"success": True, "waitFor": {"converged": True, "value": command}},
            )
        if arguments.get("tool") == "hub_list_devices":
            args = arguments.get("args") or {}
            label_filter = args.get("labelFilter")
            devices = self.devices
            if label_filter:
                devices = [
                    d for d in devices
                    if label_filter.casefold() in str(d.get("label", "")).casefold()
                ]
            if not args.get("fields"):
                devices = [
                    {k: v for k, v in d.items() if k != "capabilities"}
                    for d in devices
                ]
            return MCPToolResult(
                "hub_read_devices", arguments, {}, "ok", {"devices": devices}
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))


LIVINGROOM_LIGHT_1 = {
    "id": "1", "label": "Livingroom Light 1", "roomName": "Living Room",
    "capabilities": ["Light", "Switch"],
}
LIVINGROOM_LIGHT_2 = {
    "id": "2", "label": "Livingroom Light 2", "roomName": "Living Room",
    "capabilities": ["Light", "Switch"],
}
LIVINGROOM_TRV = {
    "id": "4718", "label": "Livingroom TRV", "roomName": "Living Room",
    "capabilities": ["Switch", "ThermostatHeatingSetpoint", "Actuator"],
}


@pytest.mark.asyncio
async def test_auto_kind_live_fallback_includes_lights_not_just_switches():
    """Regression test for a live bug: with device_kind="auto" (what every
    plain "turn on/off <name>" request actually carries), the live-lookup
    fallback paths used to filter candidates with a two-way rule (light,
    or switch-and-not-light) that silently excluded every real light
    whenever resolution had to fall back to a live hub_read_devices call
    instead of the identity cache -- leaving only non-light switches (like
    a thermostat radiator valve) to fuzzy-match against. A single
    unambiguous light target must still resolve to the light, not get
    filtered out of contention.
    """

    other_switch = {
        "id": "99", "label": "Hallway Socket", "roomName": "Hallway",
        "capabilities": ["Switch"],
    }
    mcp = LabelFilterControlMCP([LIVINGROOM_LIGHT_1, LIVINGROOM_TRV, other_switch])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Livingroom Light 1"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"1"}


@pytest.mark.asyncio
async def test_ambiguous_narrow_match_is_not_overridden_by_broader_manifest_retry():
    """Regression test for the exact live failure: "turn on livingroom
    light" resolved against the two real, similarly-named lights should
    come back ambiguous with both offered as choices -- it must not widen
    the search to the full house-wide manifest and let an unrelated
    device (here, a thermostat radiator valve that also happens to share
    "Livingroom" in its name) win as a false "unique" match once the
    kind-filtering bug is fixed and the narrow lookup already produced a
    legitimate judgement call.
    """

    distractors = [
        {"id": str(i), "label": f"Other Device {i}", "roomName": "Elsewhere", "capabilities": ["Switch"]}
        for i in range(3, 33)
    ]
    mcp = LabelFilterControlMCP(
        [LIVINGROOM_LIGHT_1, LIVINGROOM_LIGHT_2, LIVINGROOM_TRV, *distractors]
    )
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["livingroom light"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.data["success"] is False
    assert result.data["choices"] == ["Livingroom Light 1", "Livingroom Light 2"]
    dispatched_ids = {
        arguments["args"]["deviceId"]
        for _gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    }
    assert dispatched_ids == set()
    assert "4718" not in dispatched_ids


@pytest.mark.asyncio
async def test_ambiguous_narrow_match_survives_a_capabilities_dropping_gateway():
    """Regression test for the live gap left after 0.10.385 shipped: the
    user re-tested "turn on livingroom light" against 0.10.385 and it
    still surfaced Livingroom TRV as a disambiguation choice and still
    triggered the full-manifest fallback retry, even though the narrow
    labelFilter lookup reported finding "2 target candidates" first. Root
    cause was that the labelFilter-scoped hub_list_devices call never
    asked for a "fields" list including "capabilities", and a real
    Hubitat gateway call without one omits capability data entirely --
    emptying `eligible` for both real lights and defeating the 0.10.385
    "trust a genuinely narrow ambiguous result" guard. This must resolve
    exactly like the plain LabelFilterControlMCP version above even when
    the mock drops "capabilities" from any hub_list_devices response that
    didn't explicitly request it.
    """

    distractors = [
        {"id": str(i), "label": f"Other Device {i}", "roomName": "Elsewhere", "capabilities": ["Switch"]}
        for i in range(3, 33)
    ]
    mcp = FieldDefaultingControlMCP(
        [LIVINGROOM_LIGHT_1, LIVINGROOM_LIGHT_2, LIVINGROOM_TRV, *distractors]
    )
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["livingroom light"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.data["success"] is False
    assert result.data["choices"] == ["Livingroom Light 1", "Livingroom Light 2"]
    dispatched_ids = {
        arguments["args"]["deviceId"]
        for _gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    }
    assert dispatched_ids == set()
    fallback_manifest_calls = [
        arguments for _gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_devices"
        and not (arguments.get("args") or {}).get("labelFilter")
    ]
    assert fallback_manifest_calls == []


BEDROOM1_LIGHT_2 = {
    "id": "7057", "label": "Bedroom 1 Light", "roomName": "Bedroom 1",
    "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
BEDROOM2_LIGHT = {
    "id": "7058", "label": "Bedroom 2 Light", "roomName": "Bedroom 2",
    "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
BEDROOM3_LIGHT = {
    "id": "7059", "label": "Bedroom 3 Light", "roomName": "Bedroom 3",
    "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


@pytest.mark.asyncio
async def test_all_lights_except_rooms_excludes_every_device_in_those_rooms():
    """Live-requested follow-up to the "all lights" aggregate: "turn off
    all lights except bedroom 2 and bedroom 3" must turn off every light
    except the ones in those two rooms, not fail the way a bare "the
    lights" once did or (worse) ignore the exclusion and hit everything.
    """

    mcp = ControlMCP([BEDROOM1_LIGHT_2, BEDROOM2_LIGHT, BEDROOM3_LIGHT, KITCHEN_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["all lights except bedroom 2 and bedroom 3"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"7057", "8001"}
    dispatched_ids = {
        arguments["args"]["deviceId"]
        for _gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    }
    assert "7058" not in dispatched_ids
    assert "7059" not in dispatched_ids


@pytest.mark.asyncio
async def test_all_lights_except_a_single_named_device():
    mcp = ControlMCP([BEDROOM1_LIGHT_2, KITCHEN_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["all lights except the kitchen light"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"7057"}


@pytest.mark.asyncio
async def test_unresolvable_exclusion_refuses_rather_than_silently_including_it():
    """If the excluded room/device can't be found, this must refuse the
    whole command rather than silently acting on everything -- including
    whatever the user explicitly wanted left alone would be worse than
    asking them to check the name and retry.
    """

    mcp = ControlMCP([BEDROOM1_LIGHT_2, KITCHEN_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["all lights except the nonexistent room"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.is_error is True
    assert "nonexistent room" in result.data["error"]
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_all_lights_except_with_oxford_comma_list():
    devices = [BEDROOM1_LIGHT_2, BEDROOM2_LIGHT, BEDROOM3_LIGHT, KITCHEN_LIGHT]
    mcp = ControlMCP(devices)
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["all lights except bedroom 1, bedroom 2, and bedroom 3"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"8001"}


class FailingControlMCP(ControlMCP):
    """Same as ControlMCP, but every hub_call_device_command dispatch
    fails outright -- reproducing what was observed live for "living room
    light": both Livingroom Light 1 and Livingroom Light 2 landed in the
    "Failed:" bucket (command_sent False), not the "unverified" bucket."""

    async def call_tool(self, gateway, arguments):
        if arguments.get("tool") == "hub_call_device_command":
            self.calls.append((gateway, arguments))
            return MCPToolResult(
                "hub_manage_devices", arguments, {}, "error",
                {"success": False, "error": "Hubitat rejected the command."},
                is_error=True,
            )
        return await super().call_tool(gateway, arguments)


class RaisingControlMCP(ControlMCP):
    """Raise at the transport boundary instead of returning an error result."""

    async def call_tool(self, gateway, arguments):
        if arguments.get("tool") == "hub_call_device_command":
            self.calls.append((gateway, arguments))
            raise RuntimeError("simulated Hubitat transport failure")
        return await super().call_tool(gateway, arguments)


@pytest.mark.asyncio
async def test_dispatch_exception_returns_original_failure_without_unbound_result():
    """A thrown MCP exception must not be replaced by UnboundLocalError."""

    mcp = RaisingControlMCP([HALLWAY_LIGHT_1])
    service = DeviceControlService(mcp, recorder)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await service.execute({
            "device_names": ["Hallway Light 1"],
            "device_kind": "light",
            "command": "on",
        })
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert result.is_error is True
    assert result.data["success"] is False
    assert len(result.data["failed"]) == 1
    failure = result.data["failed"][0]
    assert failure["command_sent"] is False
    assert "simulated Hubitat transport failure" in failure["message"]
    assert "UnboundLocalError" not in failure["message"]
    assert snapshot["counters"]["device_control_failures"] == 1

@pytest.mark.asyncio
async def test_dispatch_failure_records_device_control_failures_metric():
    """Regression test for a live-observed bug: a routine light/switch
    command that failed at the Hubitat dispatch layer touched none of the
    fixed outcome counters, so classify_completed_request() fell through
    to its default "success" -- the WebUI showed a green Success badge
    next to a message that literally read "Failed: <device>.". This
    asserts the new device_control_failures counter closes that gap.
    """

    mcp = FailingControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await service.execute({
            "device_names": ["Hallway Light 1", "Hallway Light 2"],
            "device_kind": "auto",
            "command": "on",
        })
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert result.data["success"] is False
    assert len(result.data["failed"]) == 2
    assert snapshot["counters"]["device_control_failures"] == 1


@pytest.mark.asyncio
async def test_successful_dispatch_does_not_record_device_control_failures_metric():
    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await service.execute({
            "device_names": ["Hallway Light 1", "Hallway Light 2"],
            "device_kind": "auto",
            "command": "on",
        })
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert result.data["success"] is True
    assert "device_control_failures" not in snapshot["counters"]


class ToggleControlMCP:
    """Fake MCP supporting the pre-toggle switch-state read plus the
    subsequent hub_call_device_command dispatch, so toggle's new
    waitFor-based verification (mirroring on/off) can be exercised.
    `converged` controls whether the hub reports the post-toggle state
    actually settled; `initial_switch` controls what the pre-read reports
    the device was doing before the toggle.
    """

    def __init__(self, devices, *, initial_switch: str = "off", converged: bool = True):
        self.devices = devices
        self.initial_switch = initial_switch
        self.converged = converged
        self.calls = []

    async def get_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        tool = arguments.get("tool")
        if tool == "hub_get_device_attribute":
            return MCPToolResult(
                "hub_read_devices", arguments, {}, "ok",
                {"attribute": "switch", "value": self.initial_switch},
            )
        if tool == "hub_call_device_command":
            wait_for = (arguments.get("args") or {}).get("waitFor")
            expected = wait_for.get("expectedValue") if isinstance(wait_for, dict) else None
            return MCPToolResult(
                "hub_manage_devices", arguments, {}, "ok",
                {
                    "success": True,
                    "waitFor": {"converged": self.converged, "value": expected},
                },
            )
        if tool == "hub_list_devices":
            return MCPToolResult(
                "hub_read_devices", arguments, {}, "ok", {"devices": self.devices}
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))


TOGGLE_LAMP = {
    "id": "8001", "label": "Toggle Lamp", "roomName": "Office",
    "capabilities": ["Actuator", "Refresh", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "off"}],
}


@pytest.mark.asyncio
async def test_toggle_verifies_convergence_against_the_computed_opposite_state():
    """Regression test: toggle previously had no verification path at
    all -- device_control_service.py only attached a waitFor block and
    computed `verified` for "on"/"off", so a toggle whose HTTP dispatch
    succeeded but whose physical device never actually changed state was
    reported as success with no way to know it hadn't. Toggle now reads
    the device's current switch state first, computes the expected
    post-toggle value, and gets the exact same waitFor verification on/off
    already had.
    """

    mcp = ToggleControlMCP([TOGGLE_LAMP], initial_switch="off", converged=True)
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Toggle Lamp"],
        "device_kind": "auto",
        "command": "toggle",
    })

    assert result.data["success"] is True
    dispatch_calls = [
        args for name, args in mcp.calls if args.get("tool") == "hub_call_device_command"
    ]
    assert len(dispatch_calls) == 1
    assert dispatch_calls[0]["args"]["waitFor"]["expectedValue"] == "on"


@pytest.mark.asyncio
async def test_toggle_reports_failure_when_the_hub_reports_no_convergence():
    """The other half of the same fix: if the hub's own waitFor reports
    the switch attribute never actually reached the expected post-toggle
    value, that must surface as a failure -- not a silent success -- for
    toggle exactly as it already does for on/off.
    """

    mcp = ToggleControlMCP([TOGGLE_LAMP], initial_switch="off", converged=False)
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Toggle Lamp"],
        "device_kind": "auto",
        "command": "toggle",
    })

    assert result.data["success"] is False
    assert len(result.data["failed"]) == 1


@pytest.mark.asyncio
async def test_toggle_falls_back_to_unverified_when_the_pre_read_is_unavailable():
    """If the pre-toggle state read fails or the attribute isn't reported,
    toggle must fall back to the previous unverified-but-not-crashing
    behaviour rather than guessing a wrong expected value or raising.
    """

    class NoAttributeReadMCP(ToggleControlMCP):
        async def call_tool(self, gateway, arguments):
            if arguments.get("tool") == "hub_get_device_attribute":
                self.calls.append((gateway, arguments))
                return MCPToolResult(
                    "hub_read_devices", arguments, {}, "error",
                    {"success": False, "error": "attribute unavailable"},
                    is_error=True,
                )
            return await super().call_tool(gateway, arguments)

    mcp = NoAttributeReadMCP([TOGGLE_LAMP])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Toggle Lamp"],
        "device_kind": "auto",
        "command": "toggle",
    })

    assert result.data["success"] is True
    dispatch_calls = [
        args for name, args in mcp.calls if args.get("tool") == "hub_call_device_command"
    ]
    assert "waitFor" not in dispatch_calls[0]["args"]


@pytest.mark.asyncio
async def test_exact_cached_target_bypasses_slow_identity_refresh():
    """A known exact target must go straight from local identity to command.

    This guards a live regression where resolving one already-known light paid
    for a ~24 second hub_list_devices manifest refresh before a <1 second
    verified command could run.
    """

    livingroom_light_2 = {
        "id": "7828",
        "label": "Livingroom Light 2",
        "roomName": "Living Room",
        "capabilities": ["Actuator", "Light", "Switch"],
        "attributes": [{"name": "switch", "value": "off"}],
    }

    class CachedIdentityMCP:
        def __init__(self):
            self.calls = []
            self.refresh_attempts = 0

        def peek_device_identities(self):
            return [livingroom_light_2]

        async def get_device_identities(self):
            self.refresh_attempts += 1
            raise AssertionError("slow identity refresh must not run")

        async def get_cached_devices(self):
            self.refresh_attempts += 1
            raise AssertionError("slow manifest refresh must not run")

        async def call_tool(self, gateway, arguments):
            self.calls.append((gateway, arguments))
            assert gateway == "hub_manage_devices"
            assert arguments["tool"] == "hub_call_device_command"
            assert arguments["args"]["deviceId"] == "7828"
            return MCPToolResult(
                gateway,
                arguments,
                {},
                "ok",
                {"success": True, "waitFor": {"converged": True, "value": "on"}},
            )

    receipts = []
    mcp = CachedIdentityMCP()
    service = DeviceControlService(
        mcp, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.execute({
        "device_names": ["livingroom light 2"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.data["success"] is True
    assert result.data["succeeded"][0]["id"] == "7828"
    assert mcp.refresh_attempts == 0
    assert len(mcp.calls) == 1
    identity_receipts = [
        kwargs for _args, kwargs in receipts
        if kwargs.get("evidence_kind") == "control_target_resolution"
    ]
    assert len(identity_receipts) == 1
    assert receipts[0][0][1]["source"] == "local_identity_cache"


@pytest.mark.asyncio
async def test_mcp_client_peek_device_identities_can_use_complete_live_context_without_io():
    """The dashboard's complete live-context snapshot can seed routine control."""

    from mcp_client import HubitatMCPClient

    client = HubitatMCPClient("http://example.invalid/mcp")
    try:
        client._live_context_snapshot = (
            1.0,
            client._live_device_snapshot_generation,
            {
                "devices": [
                    {
                        "id": "7828",
                        "label": "Livingroom Light 2",
                        "roomName": "Living Room",
                        "capabilities": ["Light", "Switch"],
                        "attributes": {"switch": "off"},
                    }
                ]
            },
        )

        identities = client.peek_device_identities()

        assert identities == [
            {
                "id": "7828",
                "label": "Livingroom Light 2",
                "roomName": "Living Room",
                "capabilities": ["Light", "Switch"],
                "attributes": {"switch": "off"},
            }
        ]
        identities[0]["label"] = "mutated"
        assert client._live_context_snapshot[2]["devices"][0]["label"] == "Livingroom Light 2"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cold_identity_lookup_prefers_one_bulk_context_read_over_full_manifest():
    """A cold cache must not immediately pay for paginated hub_list_devices."""

    from mcp_client import HubitatMCPClient

    client = HubitatMCPClient("http://example.invalid/mcp")
    context_reads = 0
    manifest_reads = 0

    async def fake_context(refresh=False):
        nonlocal context_reads
        context_reads += 1
        return {
            "devices": [
                {
                    "id": "7828",
                    "label": "Livingroom Light 2",
                    "roomName": "Living Room",
                    "capabilities": ["Light", "Switch"],
                    "attributes": {"switch": "off"},
                }
            ],
            "totalDevices": 1,
            "idsComplete": True,
            "partial": False,
            "truncated": False,
        }

    async def forbidden_manifest(refresh=False):
        nonlocal manifest_reads
        manifest_reads += 1
        raise AssertionError("full device manifest must not run for complete context")

    client.get_live_context = fake_context
    client.get_cached_devices = forbidden_manifest
    try:
        identities = await client.get_device_identities()
    finally:
        await client.close()

    assert identities[0]["id"] == "7828"
    assert context_reads == 1
    assert manifest_reads == 0


@pytest.mark.asyncio
async def test_room_set_level_uses_verified_setlevel_parameter_array():
    lights = [
        {
            **HALLWAY_LIGHT_1,
            "attributes": [
                {"name": "switch", "value": "on"},
                {"name": "level", "value": 50},
            ],
        },
        {
            **HALLWAY_LIGHT_2,
            "attributes": [
                {"name": "switch", "value": "on"},
                {"name": "level", "value": 20},
            ],
        },
    ]
    mcp = ControlMCP(lights)
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Hallway lights"],
        "device_kind": "light",
        "command": "set_level",
        "level": 100,
    })

    assert result.data["success"] is True
    command_calls = [
        arguments for _gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    ]
    assert len(command_calls) == 2
    for arguments in command_calls:
        assert arguments["args"]["command"] == "setLevel"
        assert arguments["args"]["parameters"] == ["100"]
        assert arguments["args"]["waitFor"] == {
            "attribute": "level",
            "expectedValue": "100",
            "timeoutMs": 5000,
        }



class RelativeLevelMCP:
    def __init__(self) -> None:
        self.devices = [
            {
                "id": "7805",
                "label": "Livingroom Light 1",
                "roomName": "Living Room",
                "capabilities": ["Light", "Switch", "SwitchLevel"],
                "attributes": [
                    {"name": "switch", "value": "on"},
                    {"name": "level", "value": 5},
                ],
            },
            {
                "id": "7828",
                "label": "Livingroom Light 2",
                "roomName": "Living Room",
                "capabilities": ["Light", "Switch", "SwitchLevel"],
                "attributes": [
                    {"name": "switch", "value": "on"},
                    {"name": "level", "value": 5},
                ],
            },
            {
                "id": "9999",
                "label": "Livingroom TRV",
                "roomName": "Living Room",
                "capabilities": ["Switch", "Thermostat"],
                "attributes": [{"name": "switch", "value": "on"}],
            },
        ]
        self.live_levels = {"7805": 80, "7828": 60}
        self.calls: list[tuple[str, dict]] = []

    def peek_device_identities(self):
        return list(self.devices)

    async def get_device_identities(self):
        raise AssertionError("warm identity cache should avoid refresh")

    async def get_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_get_device_attribute":
            device_id = str(arguments["args"]["deviceId"])
            return MCPToolResult(
                "hub_read_devices",
                arguments,
                {},
                "ok",
                {"success": True, "value": self.live_levels[device_id]},
            )
        if arguments.get("tool") == "hub_call_device_command":
            expected = arguments["args"]["waitFor"]["expectedValue"]
            return MCPToolResult(
                "hub_manage_devices",
                arguments,
                {},
                "ok",
                {
                    "success": True,
                    "waitFor": {
                        "converged": True,
                        "value": expected,
                    },
                },
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))


@pytest.mark.asyncio
async def test_adjust_level_reads_live_state_then_compiles_per_device_absolute_levels():
    mcp = RelativeLevelMCP()
    receipts: list[tuple[tuple, dict]] = []

    def capture(*args, **kwargs):
        receipts.append((args, kwargs))

    service = DeviceControlService(mcp, capture)
    result = await service.execute({
        "room": "Living Room",
        "device_kind": "light",
        "command": "adjust_level",
        "delta": 20,
    })

    assert result.data["success"] is True
    assert result.data["matched"] == 2
    assert result.data["delta"] == 20

    succeeded = {item["id"]: item for item in result.data["succeeded"]}
    assert succeeded["7805"]["previous_level"] == 80
    assert succeeded["7805"]["target_level"] == 100
    assert succeeded["7805"]["delta_applied"] == 20
    assert succeeded["7828"]["previous_level"] == 60
    assert succeeded["7828"]["target_level"] == 80
    assert succeeded["7828"]["delta_applied"] == 20

    state_reads = [
        args for gateway, args in mcp.calls
        if gateway == "hub_read_devices"
        and args.get("tool") == "hub_get_device_attribute"
    ]
    assert {item["args"]["deviceId"] for item in state_reads} == {"7805", "7828"}

    commands = [
        args for gateway, args in mcp.calls
        if gateway == "hub_manage_devices"
        and args.get("tool") == "hub_call_device_command"
    ]
    by_id = {item["args"]["deviceId"]: item["args"] for item in commands}
    assert by_id["7805"]["command"] == "setLevel"
    assert by_id["7805"]["parameters"] == ["100"]
    assert by_id["7805"]["waitFor"] == {
        "attribute": "level",
        "expectedValue": "100",
        "timeoutMs": 5000,
    }
    assert by_id["7828"]["parameters"] == ["80"]
    assert by_id["7828"]["waitFor"]["expectedValue"] == "80"

    precondition_receipts = [
        kwargs for _args, kwargs in receipts
        if kwargs.get("evidence_kind") == "control_precondition_state"
    ]
    assert len(precondition_receipts) == 2


@pytest.mark.asyncio
async def test_adjust_level_clamps_at_device_bounds():
    mcp = RelativeLevelMCP()
    mcp.live_levels = {"7805": 95, "7828": 5}
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "Living Room",
        "device_kind": "light",
        "command": "adjust_level",
        "delta": 20,
    })

    succeeded = {item["id"]: item for item in result.data["succeeded"]}
    assert succeeded["7805"]["target_level"] == 100
    assert succeeded["7805"]["delta_applied"] == 5
    assert succeeded["7828"]["target_level"] == 25


@pytest.mark.asyncio
async def test_adjust_level_fails_closed_when_live_level_is_unavailable():
    mcp = RelativeLevelMCP()
    del mcp.live_levels["7828"]
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "Living Room",
        "device_kind": "light",
        "command": "adjust_level",
        "delta": 20,
    })

    assert result.data["success"] is False
    failed = {item["id"]: item for item in result.data["failed"]}
    assert failed["7828"]["command_sent"] is False
    assert "brightness" in failed["7828"]["message"].lower()



class ThermostatMCP:
    def __init__(self) -> None:
        self.devices = [
            {
                "id": "7331",
                "label": "Bedroom 1 TRV",
                "roomName": "Bedroom 1",
                "capabilities": [
                    "Thermostat",
                    "ThermostatHeatingSetpoint",
                    "TemperatureMeasurement",
                    "Switch",
                ],
                "commands": ["setHeatingSetpoint", "on", "off"],
                "attributes": [
                    {"name": "heatingSetpoint", "value": 20.0, "unit": "°C"},
                    {"name": "temperature", "value": 19.4, "unit": "°C"},
                    {"name": "switch", "value": "on"},
                ],
            },
            {
                "id": "7057",
                "label": "Bedroom 1 Light",
                "roomName": "Bedroom 1",
                "capabilities": ["Light", "Switch", "SwitchLevel"],
                "commands": ["setLevel", "on", "off"],
                "attributes": [
                    {"name": "level", "value": 50},
                    {"name": "switch", "value": "on"},
                ],
            },
        ]
        self.live_setpoints = {"7331": 20.0}
        self.calls: list[tuple[str, dict]] = []

    def peek_device_identities(self):
        return list(self.devices)

    async def get_device_identities(self):
        raise AssertionError("warm thermostat identity cache should avoid refresh")

    async def get_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_get_device_attribute":
            device_id = str(arguments["args"]["deviceId"])
            if device_id not in self.live_setpoints:
                return MCPToolResult(
                    "hub_read_devices",
                    arguments,
                    {},
                    "missing",
                    {"success": False},
                    is_error=True,
                )
            return MCPToolResult(
                "hub_read_devices",
                arguments,
                {},
                "ok",
                {"success": True, "value": self.live_setpoints[device_id]},
            )
        if arguments.get("tool") == "hub_call_device_command":
            expected = arguments["args"]["waitFor"]["expectedValue"]
            return MCPToolResult(
                "hub_manage_devices",
                arguments,
                {},
                "ok",
                {
                    "success": True,
                    "waitFor": {
                        "converged": True,
                        "value": expected,
                    },
                },
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))


@pytest.mark.asyncio
async def test_adjust_temperature_reads_live_setpoint_then_compiles_verified_command():
    mcp = ThermostatMCP()
    receipts: list[tuple[tuple, dict]] = []

    def capture(*args, **kwargs):
        receipts.append((args, kwargs))

    service = DeviceControlService(mcp, capture)
    result = await service.execute({
        "room": "Bedroom 1",
        "device_kind": "thermostat",
        "command": "adjust_temperature",
        "delta": 1.0,
    })

    assert result.data["success"] is True
    assert result.data["matched"] == 1
    assert result.data["delta"] == 1.0
    item = result.data["succeeded"][0]
    assert item["id"] == "7331"
    assert item["previous_setpoint"] == 20.0
    assert item["target_setpoint"] == 21.0
    assert item["delta_applied"] == 1.0
    assert item["temperature_unit"] == "°C"

    reads = [
        args for gateway, args in mcp.calls
        if gateway == "hub_read_devices"
        and args.get("tool") == "hub_get_device_attribute"
    ]
    assert reads == [{
        "tool": "hub_get_device_attribute",
        "args": {"deviceId": "7331", "attribute": "heatingSetpoint"},
    }]

    commands = [
        args for gateway, args in mcp.calls
        if gateway == "hub_manage_devices"
        and args.get("tool") == "hub_call_device_command"
    ]
    assert commands == [{
        "tool": "hub_call_device_command",
        "args": {
            "deviceId": "7331",
            "command": "setHeatingSetpoint",
            "parameters": ["21"],
            "waitFor": {
                "attribute": "heatingSetpoint",
                "expectedValue": "21",
                "timeoutMs": 5000,
            },
        },
    }]

    precondition_receipts = [
        kwargs for _args, kwargs in receipts
        if kwargs.get("evidence_kind") == "control_precondition_state"
    ]
    assert len(precondition_receipts) == 1


@pytest.mark.asyncio
async def test_set_temperature_filters_room_to_heating_setpoint_capable_devices_only():
    mcp = ThermostatMCP()
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "Bedroom 1",
        "device_kind": "thermostat",
        "command": "set_temperature",
        "setpoint": 20.5,
    })

    assert result.data["success"] is True
    assert result.data["matched"] == 1
    assert result.data["succeeded"][0]["label"] == "Bedroom 1 TRV"
    command = next(
        args for gateway, args in mcp.calls
        if gateway == "hub_manage_devices"
    )
    assert command["args"]["command"] == "setHeatingSetpoint"
    assert command["args"]["parameters"] == ["20.5"]
    assert command["args"]["waitFor"]["expectedValue"] == "20.5"


@pytest.mark.asyncio
async def test_adjust_temperature_clamps_to_safe_setpoint_range():
    mcp = ThermostatMCP()
    mcp.live_setpoints["7331"] = 34.5
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "Bedroom 1",
        "device_kind": "thermostat",
        "command": "adjust_temperature",
        "delta": 2.0,
    })

    item = result.data["succeeded"][0]
    assert item["target_setpoint"] == 35.0
    assert item["delta_applied"] == 0.5


@pytest.mark.asyncio
async def test_adjust_temperature_fails_closed_without_live_setpoint():
    mcp = ThermostatMCP()
    mcp.live_setpoints.clear()
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "Bedroom 1",
        "device_kind": "thermostat",
        "command": "adjust_temperature",
        "delta": 1.0,
    })

    assert result.data["success"] is False
    failed = result.data["failed"][0]
    assert failed["command_sent"] is False
    assert "setpoint" in failed["message"].lower()
    assert not any(
        gateway == "hub_manage_devices"
        for gateway, _args in mcp.calls
    )


@pytest.mark.asyncio
async def test_temperature_control_rejects_device_without_explicit_heating_setpoint_ability():
    generic_thermostat = {
        "id": "t1",
        "label": "Generic Thermostat",
        "roomName": "Office",
        "capabilities": ["Thermostat", "Switch"],
        "attributes": [{"name": "switch", "value": "on"}],
    }

    class GenericMCP(ThermostatMCP):
        def __init__(self):
            super().__init__()
            self.devices = [generic_thermostat]

    mcp = GenericMCP()
    service = DeviceControlService(mcp, recorder)
    result = await service.execute({
        "device_names": ["Generic Thermostat"],
        "device_kind": "thermostat",
        "command": "set_temperature",
        "setpoint": 20,
    })

    assert result.data["success"] is False
    assert result.data["executed"] == 0
    assert mcp.calls == []



@pytest.mark.asyncio
async def test_adjust_level_matches_unlabelled_switchlevel_dimmers_in_room():
    mcp = RelativeLevelMCP()
    mcp.devices = [
        {
            "id": "7805",
            "label": "Hallway Main",
            "roomName": "Hallway",
            "capabilities": ["Switch", "SwitchLevel"],
            "commands": ["on", "off", "setLevel"],
            "attributes": [
                {"name": "switch", "value": "on"},
                {"name": "level", "value": 5},
            ],
        },
        {
            "id": "7828",
            "label": "Hallway Secondary",
            "roomName": "Hallway",
            "capabilities": ["Switch", "SwitchLevel"],
            "commands": ["on", "off", "setLevel"],
            "attributes": [
                {"name": "switch", "value": "on"},
                {"name": "level", "value": 5},
            ],
        },
        {
            "id": "fan1",
            "label": "Hallway Fan",
            "roomName": "Hallway",
            "capabilities": ["Switch", "SwitchLevel", "FanControl"],
            "commands": ["on", "off", "setLevel", "setSpeed"],
            "attributes": [
                {"name": "switch", "value": "on"},
                {"name": "level", "value": 50},
                {"name": "speed", "value": "medium"},
            ],
        },
    ]
    mcp.live_levels = {"7805": 40, "7828": 20}
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "Hallway",
        "device_kind": "light",
        "command": "adjust_level",
        "delta": 20,
    })

    assert result.data["success"] is True
    assert result.data["matched"] == 2
    assert {item["label"] for item in result.data["succeeded"]} == {
        "Hallway Main",
        "Hallway Secondary",
    }
    assert not any(
        args.get("args", {}).get("deviceId") == "fan1"
        for _gateway, args in mcp.calls
    )



@pytest.mark.asyncio
async def test_adjust_level_falls_back_to_fresh_live_context_when_native_attribute_never_reported():
    class HallwayMCP(RelativeLevelMCP):
        def __init__(self):
            super().__init__()
            self.devices = [{
                "id": "3927",
                "label": "Hallway dimmer",
                "roomName": "Hallway",
                "capabilities": ["Switch", "SwitchLevel"],
                "commands": ["on", "off", "setLevel"],
                "attributes": [{"name": "switch", "value": "on"}],
            }]
            self.live_levels = {}
            self.context_refreshes = 0

        async def call_tool(self, gateway, arguments):
            self.calls.append((gateway, arguments))
            if arguments.get("tool") == "hub_get_device_attribute":
                return MCPToolResult(
                    "hub_read_devices",
                    arguments,
                    {},
                    "never reported",
                    {
                        "success": True,
                        "attribute": "level",
                        "value": None,
                        "neverReported": True,
                    },
                )
            if arguments.get("tool") == "hub_call_device_command":
                expected = arguments["args"]["waitFor"]["expectedValue"]
                return MCPToolResult(
                    "hub_manage_devices",
                    arguments,
                    {},
                    "ok",
                    {
                        "success": True,
                        "waitFor": {"converged": True, "value": expected},
                    },
                )
            raise AssertionError((gateway, arguments))

        async def get_live_context(self, refresh=False):
            assert refresh is True
            self.context_refreshes += 1
            return {
                "devices": [{
                    "id": "3927",
                    "label": "Hallway dimmer",
                    "roomName": "Hallway",
                    "attributes": [
                        {"name": "level", "value": 40},
                        {"name": "switch", "value": "on"},
                    ],
                }]
            }

    mcp = HallwayMCP()
    receipts = []

    def capture(*args, **kwargs):
        receipts.append((args, kwargs))

    service = DeviceControlService(mcp, capture)
    result = await service.execute({
        "device_names": ["Hallway dimmer"],
        "device_kind": "light",
        "command": "adjust_level",
        "delta": 20,
    })

    assert result.data["success"] is True
    item = result.data["succeeded"][0]
    assert item["previous_level"] == 40
    assert item["target_level"] == 60
    assert mcp.context_refreshes == 1

    command = next(
        args for gateway, args in mcp.calls
        if gateway == "hub_manage_devices"
    )
    assert command["args"]["parameters"] == ["60"]
    assert command["args"]["waitFor"]["expectedValue"] == "60"

    summaries = [
        kwargs.get("summary", "")
        for _args, kwargs in receipts
        if kwargs.get("evidence_kind") == "control_precondition_state"
    ]
    assert any("never reported" in summary for summary in summaries)
    assert any("fresh live-context fallback" in summary for summary in summaries)


@pytest.mark.asyncio
async def test_adjust_level_missing_from_both_live_sources_requests_absolute_input():
    class HallwayMCP(RelativeLevelMCP):
        def __init__(self):
            super().__init__()
            self.devices = [{
                "id": "3927",
                "label": "Hallway dimmer",
                "roomName": "Hallway",
                "capabilities": ["Switch", "SwitchLevel"],
                "commands": ["on", "off", "setLevel"],
                "attributes": [{"name": "switch", "value": "on"}],
            }]
            self.calls = []

        async def call_tool(self, gateway, arguments):
            self.calls.append((gateway, arguments))
            if arguments.get("tool") == "hub_get_device_attribute":
                return MCPToolResult(
                    "hub_read_devices",
                    arguments,
                    {},
                    "never reported",
                    {
                        "success": True,
                        "attribute": "level",
                        "value": None,
                        "neverReported": True,
                    },
                )
            raise AssertionError("No mutation should be sent without a live baseline")

        async def get_live_context(self, refresh=False):
            assert refresh is True
            return {
                "devices": [{
                    "id": "3927",
                    "label": "Hallway dimmer",
                    "roomName": "Hallway",
                    "attributes": [{"name": "switch", "value": "on"}],
                }]
            }

    mcp = HallwayMCP()
    service = DeviceControlService(mcp, recorder)
    result = await service.execute({
        "device_names": ["Hallway dimmer"],
        "device_kind": "light",
        "command": "adjust_level",
        "delta": 20,
    })

    assert result.data["success"] is False
    assert result.data["needs_input"] is True
    assert "absolute brightness level" in result.data["clarification"]
    assert result.data["failed"][0]["needs_input"] is True
    assert result.data["failed"][0]["command_sent"] is False
    assert not any(
        gateway == "hub_manage_devices"
        for gateway, _arguments in mcp.calls
    )



@pytest.mark.asyncio
async def test_hallway_room_brightness_ignores_remote_parent_and_controls_real_lights():
    mcp = RelativeLevelMCP()
    mcp.devices = [
        {
            "id": "3927",
            "label": "Hallway dimmer",
            "roomName": "",
            "capabilities": ["Battery", "PushableButton", "SwitchLevel"],
            "commands": ["setLevel"],
            "attributes": [
                {"name": "battery", "value": 82},
                {"name": "level", "value": None},
            ],
        },
        {
            "id": "7829",
            "label": "Hallway Light 1",
            "roomName": "Hallway",
            "capabilities": [
                "Actuator", "ChangeLevel", "Light", "Refresh", "Switch", "SwitchLevel"
            ],
            "commands": ["on", "off", "setLevel"],
            "attributes": [
                {"name": "switch", "value": "on"},
                {"name": "level", "value": 50},
            ],
        },
        {
            "id": "7830",
            "label": "Hallway Light 2",
            "roomName": "Hallway",
            "capabilities": [
                "Actuator", "ChangeLevel", "Light", "Refresh", "Switch", "SwitchLevel"
            ],
            "commands": ["on", "off", "setLevel"],
            "attributes": [
                {"name": "switch", "value": "on"},
                {"name": "level", "value": 30},
            ],
        },
    ]
    mcp.live_levels = {"7829": 50, "7830": 30}
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "Hallway",
        "device_kind": "light",
        "command": "adjust_level",
        "delta": 20,
    })

    assert result.data["success"] is True
    assert result.data["matched"] == 2
    assert {item["label"] for item in result.data["succeeded"]} == {
        "Hallway Light 1",
        "Hallway Light 2",
    }
    assert not any(
        args.get("args", {}).get("deviceId") == "3927"
        for _gateway, args in mcp.calls
    )

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

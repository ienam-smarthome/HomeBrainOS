from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult  # noqa: E402
from rule_authoring_service import (  # noqa: E402
    RULE_MACHINE_GATEWAY,
    RuleAuthoringService,
)


class RuleMCP:
    def __init__(self, devices, rules=None):
        self.devices = devices
        self.rules = rules or []
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_read_devices":
            # The production resolver now reads the complete inventory once and
            # performs deterministic name matching locally. Preserve optional
            # status-filter behaviour for unrelated callers, but an empty args
            # object must return every device.
            wanted = str(arguments.get("args", {}).get("filter") or "").casefold()
            matches = (
                [
                    device
                    for device in self.devices
                    if wanted in str(device.get("label") or "").casefold()
                ]
                if wanted
                else list(self.devices)
            )
            return MCPToolResult(name, arguments, {}, "", {"devices": matches})
        if name == "hub_read_rules":
            return MCPToolResult(name, arguments, {}, "", {"rules": self.rules})
        raise AssertionError((name, arguments))

    async def get_cached_devices(self):
        return list(self.devices)


def recorder(*_args, **_kwargs):
    return None


def tab_device(label="Block Tab-S9-FE"):
    return {
        "id": "6916",
        "label": label,
        "commands": ["blockInternet", "allowInternet", "addTime"],
        "capabilities": ["Switch"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "write a rule to block tab s9 from 9am to 7pm everyday",
        "Create an automation to block Tab-S9-FE from 09:00 to 19:00 every day",
        "set up a schedule to disable internet for the tab s9 from 9 a.m. until 7 p.m. daily",
    ],
)
async def test_compiles_daily_block_window_into_two_atomic_rules(prompt):
    mcp = RuleMCP([tab_device()])
    service = RuleAuthoringService(mcp, recorder)

    decision = await service.propose(
        prompt,
        available_gateways={RULE_MACHINE_GATEWAY, "hub_read_rules"},
        can_read_rules=True,
    )

    assert decision.handled is True
    assert decision.message is None
    assert decision.rule_names == (
        "Block Tab S9 FE (Start)",
        "Block Tab S9 FE (End)",
    )
    assert len(decision.actions) == 2
    first, second = decision.actions
    assert first["tool"] == second["tool"] == "hub_set_rule"
    assert first["args"]["addTrigger"]["atTime"] == "09:00"
    assert second["args"]["addTrigger"]["atTime"] == "19:00"
    assert first["args"]["addAction"] == {
        "capability": "runCommand",
        "deviceIds": ["6916"],
        "capabilityFilter": "Switch",
        "command": "blockInternet",
    }
    assert second["args"]["addAction"]["command"] == "allowInternet"
    inventory_calls = [
        arguments
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
    ]
    assert inventory_calls == [{"tool": "hub_list_devices", "args": {}}]


@pytest.mark.asyncio
async def test_compiles_switch_off_window_using_verified_commands():
    lamp = {
        "id": "42",
        "label": "Bedroom 1 Lamp",
        "commands": ["on", "off", "refresh"],
        "capabilities": ["Switch", "Light"],
    }
    service = RuleAuthoringService(RuleMCP([lamp]), recorder)

    decision = await service.propose(
        "create a rule to turn bedroom 1 lamp off from 10pm to 6am every day",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert [
        action["args"]["addAction"]["command"] for action in decision.actions
    ] == ["off", "on"]
    assert [
        action["args"]["addTrigger"]["atTime"] for action in decision.actions
    ] == ["22:00", "06:00"]


@pytest.mark.asyncio
async def test_rejects_unverified_commands_instead_of_guessing():
    device = tab_device()
    device["commands"] = ["on", "off"]
    service = RuleAuthoringService(RuleMCP([device]), recorder)

    decision = await service.propose(
        "write a rule to block tab s9 from 9am to 7pm everyday",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.actions == ()
    assert "does not advertise" in str(decision.message)
    assert "allowinternet" in str(decision.message)
    assert "blockinternet" in str(decision.message)


@pytest.mark.asyncio
async def test_existing_rules_prevent_duplicate_creation():
    rules = [
        {"id": "4165", "name": "Block Tab S9 FE (Start)"},
        {"id": "4166", "name": "Block Tab S9 FE (End)"},
    ]
    service = RuleAuthoringService(RuleMCP([tab_device()], rules), recorder)

    decision = await service.propose(
        "write a rule to block tab s9 from 9am to 7pm everyday",
        available_gateways={RULE_MACHINE_GATEWAY, "hub_read_rules"},
        can_read_rules=True,
    )

    assert decision.handled is True
    assert decision.actions == ()
    assert "No duplicate rules were queued" in str(decision.message)


@pytest.mark.asyncio
async def test_unmatched_or_unsupported_schedule_stays_in_general_agent_path():
    service = RuleAuthoringService(RuleMCP([tab_device()]), recorder)

    read = await service.propose(
        "which switches are on?",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    weekly = await service.propose(
        "create a rule to block tab s9 on weekdays",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert read.handled is False
    assert weekly.handled is False
    assert service.mcp.calls == []


# --- Single daily trigger (no auto-revert window) -------------------------
#
# Found via live testing against a real 84-device house: the compiler had
# no path at all for "turn on X every day at 7am" -- only auto-reverting
# window schedules ("turn X off from A to B") were recognised. Real device
# shapes below are pulled from hub_get_device against the live hub.

def real_bedroom_light():
    return {
        "id": "7057",
        "label": "Bedroom 1 Light",
        "roomName": "Bedroom 1",
        "commands": ["off", "on", "refresh", "setLevel"],
        "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    }


def real_front_door():
    # A genuine contact sensor with no lock/unlock commands at all --
    # used to prove command verification rejects a mismatched device
    # rather than guessing.
    return {
        "id": "7399",
        "label": "Front Door",
        "roomName": "Hallway",
        "commands": [],
        "capabilities": ["ContactSensor", "Sensor", "Battery"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt,expected_command,expected_time",
    [
        ("create a rule to turn on Bedroom 1 Light every day at 7am", "on", "07:00"),
        ("create a rule to turn on Bedroom 1 Light at 7am every day", "on", "07:00"),
        ("set up an automation to turn off Bedroom 1 Light every day at 11pm", "off", "23:00"),
    ],
)
async def test_compiles_single_daily_trigger_into_one_atomic_rule(
    prompt, expected_command, expected_time
):
    service = RuleAuthoringService(RuleMCP([real_bedroom_light()]), recorder)

    decision = await service.propose(
        prompt,
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.message is None
    assert len(decision.actions) == 1
    assert len(decision.rule_names) == 1
    action = decision.actions[0]
    assert action["tool"] == "hub_set_rule"
    assert action["args"]["addTrigger"]["atTime"] == expected_time
    assert action["args"]["addAction"] == {
        "capability": "runCommand",
        "deviceIds": ["7057"],
        "capabilityFilter": "Switch",
        "command": expected_command,
    }


@pytest.mark.asyncio
async def test_single_trigger_rejects_device_missing_the_command():
    service = RuleAuthoringService(RuleMCP([real_front_door()]), recorder)

    decision = await service.propose(
        "make a rule to lock Front Door every day at 10pm",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.actions == ()
    assert "does not advertise" in str(decision.message)
    assert "lock" in str(decision.message)


@pytest.mark.asyncio
async def test_single_trigger_duplicate_rule_is_not_requeued():
    rules = [{"id": "1", "name": "Turn on Bedroom 1 Light (Daily)"}]
    service = RuleAuthoringService(RuleMCP([real_bedroom_light()], rules), recorder)

    decision = await service.propose(
        "create a rule to turn on Bedroom 1 Light every day at 7am",
        available_gateways={RULE_MACHINE_GATEWAY, "hub_read_rules"},
        can_read_rules=True,
    )

    assert decision.handled is True
    assert decision.actions == ()
    assert "already exists" in str(decision.message)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        # daily marker AFTER the window (already worked before this fix)
        "create a rule to turn Bedroom 1 Light off from 11pm to 6am every day",
        # daily marker BEFORE the window -- equally natural phrasing that
        # silently failed before this fix, since the goal slice included
        # the trailing "every day" and broke the verb-pattern fullmatch
        "create a rule to turn Bedroom 1 Light off every day from 11pm to 6am",
    ],
)
async def test_window_schedule_is_order_independent_for_the_daily_marker(prompt):
    service = RuleAuthoringService(RuleMCP([real_bedroom_light()]), recorder)

    decision = await service.propose(
        prompt,
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.message is None
    assert len(decision.actions) == 2
    assert [
        action["args"]["addTrigger"]["atTime"] for action in decision.actions
    ] == ["23:00", "06:00"]

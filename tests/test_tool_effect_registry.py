from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402
from tool_registry import (  # noqa: E402
    ToolEffect,
    classify_tool_effect,
    control_devices_tool,
    home_snapshot_tool,
    rule_machine_proposal_error,
)


def test_rule_machine_schema_and_capability_probes_are_read_but_apply_is_sensitive():
    tool = MCPTool("hub_manage_rule_machine", "Manage rules", {"type": "object"})
    trigger_probe = {
        "tool": "hub_set_rule",
        "args": {"addTrigger": {"discover": True}},
    }
    apply = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Daily block",
            "addAction": {"capability": "switch", "action": "off"},
        },
    }

    assert classify_tool_effect(tool, {}) is ToolEffect.READ
    assert classify_tool_effect(tool, trigger_probe) is ToolEffect.READ
    assert classify_tool_effect(tool, apply) is ToolEffect.SENSITIVE_WRITE


def test_incomplete_rule_machine_proposals_fail_before_confirmation():
    observed_payload = {
        "tool": "hub_set_rule",
        "args": {"tool": "hub_set_rule"},
    }
    invented_envelope = {
        "tool": "hub_set_rule",
        "args": {
            "operation": "create",
            "args": {"name": "Daily block"},
        },
    }
    valid = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Daily block",
            "addActions": [{
                "capability": "switch",
                "action": "off",
                "deviceIds": ["1"],
            }],
        },
    }

    observed_error = rule_machine_proposal_error(
        "hub_manage_rule_machine", observed_payload
    )
    envelope_error = rule_machine_proposal_error(
        "hub_manage_rule_machine", invented_envelope
    )

    assert observed_error is not None
    assert "non-empty name" in observed_error
    assert "No action was queued or executed" in observed_error
    assert envelope_error is not None
    assert "does not use an operation/create/args envelope" in envelope_error
    assert rule_machine_proposal_error(
        "hub_manage_rule_machine", valid
    ) is None


def test_observed_multi_time_rule_is_rejected_before_confirmation():
    observed = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Block Tab S9 FE (9am-7pm)",
            "bestPracticeKey": "time_based_block",
            "addTriggers": [
                {"capability": "time", "command": "09:00", "type": "time"},
                {"capability": "time", "command": "19:00", "type": "time"},
            ],
            "addActions": [
                {"capability": "switch", "command": "off", "deviceIds": ["6916"]},
                {"capability": "switch", "command": "on", "deviceIds": ["6916"]},
            ],
        },
    }

    error = rule_machine_proposal_error("hub_manage_rule_machine", observed)

    assert error is not None
    assert "trigger 1" in error
    assert "No action was queued or executed" in error


def test_rule_time_window_requires_two_atomic_valid_rules():
    def proposal(name: str, at_time: str, command: str):
        return {
            "tool": "hub_set_rule",
            "args": {
                "name": name,
                "bestPracticeKey": "live-key",
                "addTrigger": {
                    "capability": "Certain Time (and optional date)",
                    "time": "A specific time",
                    "atTime": at_time,
                },
                "addAction": {
                    "capability": "runCommand",
                    "command": command,
                    "deviceIds": ["6916"],
                    "capabilityFilter": "Switch",
                },
            },
        }

    assert rule_machine_proposal_error(
        "hub_manage_rule_machine",
        proposal("Tab S9 FE - Block (9am)", "09:00", "blockInternet"),
    ) is None
    assert rule_machine_proposal_error(
        "hub_manage_rule_machine",
        proposal("Tab S9 FE - Unblock (7pm)", "19:00", "allowInternet"),
    ) is None


def test_rule_one_time_iso_datetime_atTime_is_accepted():
    """A full calendar-date ISO datetime is the one-time-trigger form (as
    opposed to bare 'HH:mm', which Hubitat treats as recurring daily) --
    rule_authoring_service.py emits this shape for "turn on X at 7am"
    requests with no daily/recurring marker."""

    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Bedroom 1 Lamp (One-time 2026-08-08)",
            "addTrigger": {
                "capability": "Certain Time (and optional date)",
                "time": "A specific time",
                "atTime": "2026-08-08T07:00:00",
            },
            "addAction": {
                "capability": "runCommand",
                "command": "on",
                "deviceIds": ["42"],
                "capabilityFilter": "Switch",
            },
        },
    }

    assert rule_machine_proposal_error("hub_manage_rule_machine", proposal) is None


def test_rule_atTime_rejects_malformed_forms():
    def proposal(at_time: str) -> dict[str, object]:
        return {
            "tool": "hub_set_rule",
            "args": {
                "name": "Bedroom 1 Lamp (One-time)",
                "addTrigger": {
                    "capability": "Certain Time (and optional date)",
                    "time": "A specific time",
                    "atTime": at_time,
                },
                "addAction": {
                    "capability": "runCommand",
                    "command": "on",
                    "deviceIds": ["42"],
                    "capabilityFilter": "Switch",
                },
            },
        }

    for bad in ("7am", "2026-08-08", "2026-08-08 07:00:00", "07:00:00", ""):
        error = rule_machine_proposal_error("hub_manage_rule_machine", proposal(bad))
        assert error is not None, f"expected {bad!r} to be rejected"
        assert "atTime" in error


def test_multiple_times_and_actions_in_one_rule_are_rejected():
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Ambiguous time window",
            "addTriggers": [
                {
                    "capability": "Certain Time (and optional date)",
                    "time": "A specific time",
                    "atTime": "09:00",
                },
                {
                    "capability": "Certain Time (and optional date)",
                    "time": "A specific time",
                    "atTime": "19:00",
                },
            ],
            "addActions": [
                {
                    "capability": "runCommand",
                    "command": "blockInternet",
                    "deviceIds": ["6916"],
                    "capabilityFilter": "Switch",
                },
                {
                    "capability": "runCommand",
                    "command": "allowInternet",
                    "deviceIds": ["6916"],
                    "capabilityFilter": "Switch",
                },
            ],
        },
    }

    error = rule_machine_proposal_error("hub_manage_rule_machine", proposal)

    assert error is not None
    assert "one rule cannot safely pair multiple daily times" in error


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ({"capability": "switch", "command": "off", "deviceIds": ["1"]},
         "maps capability='switch' with action="),
        ({"capability": "runCommand", "command": "off", "deviceIds": ["1"]},
         "requires capabilityFilter"),
    ],
)
def test_invalid_action_shortcuts_are_rejected(action, expected):
    error = rule_machine_proposal_error(
        "hub_manage_rule_machine",
        {"tool": "hub_set_rule", "args": {"name": "Bad action", "addAction": action}},
    )

    assert error is not None
    assert expected in error


def gateway(name: str, **annotations: object) -> MCPTool:
    return MCPTool(name, name, {"type": "object"}, annotations=annotations)


class GatewayMCP:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self):
        return [
            gateway("hub_search_tools", readOnlyHint=True),
            gateway("hub_manage_devices", destructiveHint=True),
        ]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {"matches": [{"gateway": "hub_manage_devices"}]},
            )
        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"success": True, "devices": []},
        )


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (
            gateway("hub_read_devices"),
            {"tool": "hub_list_device_events", "args": {"attribute": "switch"}},
            ToolEffect.READ,
        ),
        (
            gateway("hub_manage_devices", destructiveHint=True),
            {"tool": "hub_list_devices", "args": {}},
            ToolEffect.READ,
        ),
        (
            gateway("hub_manage_devices", destructiveHint=True),
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "off"},
            },
            ToolEffect.ROUTINE_WRITE,
        ),
        (
            gateway("hub_manage_devices", destructiveHint=True),
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "lock"},
            },
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("hub_manage_future", readOnlyHint=True),
            {"tool": "hub_do_something_new", "args": {}},
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("hub_manage_destructive_ops"),
            {"tool": "hub_remove_device", "args": {"deviceId": "42"}},
            ToolEffect.DESTRUCTIVE_WRITE,
        ),
        (
            gateway("hub_manage_native_rules_and_apps"),
            {"tool": "hub_set_rule_paused", "args": {"paused": True}},
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("hub_update_firmware", readOnlyHint=True),
            {"confirm": True},
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("future_unknown_tool"),
            {},
            ToolEffect.SENSITIVE_WRITE,
        ),
    ],
)
def test_structured_tool_effect_classification(tool, arguments, expected):
    assert classify_tool_effect(tool, arguments) is expected


def test_local_tools_declare_their_effects():
    assert classify_tool_effect(home_snapshot_tool(), {}) is ToolEffect.READ
    assert (
        classify_tool_effect(control_devices_tool(), {"command": "off"})
        is ToolEffect.ROUTINE_WRITE
    )


def test_effect_properties_define_write_and_confirmation_policy():
    assert ToolEffect.READ.mutates is False
    assert ToolEffect.ROUTINE_WRITE.mutates is True
    assert ToolEffect.ROUTINE_WRITE.requires_confirmation is False
    assert ToolEffect.SENSITIVE_WRITE.requires_confirmation is True
    assert ToolEffect.DESTRUCTIVE_WRITE.requires_confirmation is True


def test_effect_registry_is_authoritative_for_manage_read_calls():
    tool = gateway("hub_manage_devices", destructiveHint=True)
    arguments = {"tool": "hub_list_devices", "args": {}}

    assert classify_tool_effect(tool, arguments) is ToolEffect.READ
    assert classify_tool_effect(tool, arguments).mutates is False
    assert classify_tool_effect(tool, arguments).requires_confirmation is False


@pytest.mark.asyncio
async def test_manage_read_executes_without_confirmation_or_write_classification():
    mcp = GatewayMCP()
    arguments = {"tool": "hub_list_devices", "args": {}}
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "manage devices"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_devices", "arguments": arguments}
        }]}},
        {"message": {"role": "assistant", "content": "Inventory checked."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Inspect the device inventory", session_id="read"
    )

    assert outcome.message == "Inventory checked."
    assert outcome.request_class == "live-read"
    assert mcp.calls[-1] == ("hub_manage_devices", arguments)
    receipt = next(
        item for item in outcome.evidence if item["tool"] == "hub_manage_devices"
    )
    assert receipt["effect"] == ToolEffect.READ.value
    assert receipt["mutates"] is False


@pytest.mark.asyncio
async def test_routine_manage_write_executes_without_confirmation():
    mcp = GatewayMCP()
    arguments = {
        "tool": "hub_call_device_command",
        "args": {"deviceId": "42", "command": "off"},
    }
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "manage devices"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_devices", "arguments": arguments}
        }]}},
        {"message": {"role": "assistant", "content": "Switch turned off."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Run the routine device command", session_id="routine"
    )

    assert outcome.message == "Switch turned off."
    assert outcome.request_class == "write"
    assert mcp.calls[-1] == ("hub_manage_devices", arguments)
    receipt = next(
        item for item in outcome.evidence if item["tool"] == "hub_manage_devices"
    )
    assert receipt["effect"] == ToolEffect.ROUTINE_WRITE.value


@pytest.mark.asyncio
async def test_sensitive_manage_write_still_waits_for_confirmation():
    mcp = GatewayMCP()
    arguments = {
        "tool": "hub_call_device_command",
        "args": {"deviceId": "42", "command": "unlock"},
    }
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "manage devices"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_devices", "arguments": arguments}
        }]}},
        {"message": {"role": "assistant", "content": "Lock opened."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request(
        "Run the sensitive device command", session_id="sensitive"
    )

    assert "Please confirm" in prompt
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
    ]

    answer = await agent.process_user_request("confirm", session_id="sensitive")

    assert answer == "Lock opened."
    assert mcp.calls[-1] == ("hub_manage_devices", arguments)


def test_evidence_receipt_records_structured_effect():
    agent = UnifiedMCPAgent(object(), "key", ai_client=object())
    token = agent._evidence.set([])
    try:
        agent._record_evidence(
            "hub_manage_devices",
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "on"},
            },
            success=True,
            elapsed_ms=3,
            summary="command sent",
        )
        receipt = (agent._evidence.get() or [])[0]
    finally:
        agent._evidence.reset(token)

    assert receipt["effect"] == ToolEffect.ROUTINE_WRITE.value
    assert receipt["mutates"] is True

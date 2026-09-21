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
    normalize_rule_machine_proposal,
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


@pytest.mark.parametrize(
    "invalid_field",
    [
        "requiredExpression",
        "requiredExpressions",
        "required_expression",
        "addRequiredExpressions",
        "replaceRequiredExpressions",
    ],
)
def test_required_expression_alias_is_rejected_before_confirmation(invalid_field):
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off After 2AM",
            invalid_field: {
                "conditions": [{
                    "capability": "Between two times",
                    "startTime": "02:00",
                    "stopTime": "05:59",
                }],
                "operator": "AND",
            },
            "addTrigger": {
                "capability": "Switch",
                "deviceIds": ["7827"],
                "state": "on",
            },
            "addAction": {
                "capability": "switch",
                "action": "off",
                "deviceIds": ["7827"],
            },
        },
    }

    error = rule_machine_proposal_error("hub_manage_rule_machine", proposal)

    assert error is not None
    assert f"{invalid_field} is not a supported" in error
    assert "addRequiredExpression" in error
    assert "No action was queued or executed" in error


@pytest.mark.parametrize(
    "valid_field", ["addRequiredExpression", "replaceRequiredExpression"]
)
def test_documented_required_expression_fields_are_not_rejected(valid_field):
    identity = (
        {"appId": "4202"}
        if valid_field == "replaceRequiredExpression"
        else {"name": "Big Lamp Auto-Off After 2AM"}
    )
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            **identity,
            valid_field: {"discover": True},
        },
    }

    assert rule_machine_proposal_error(
        "hub_manage_rule_machine", proposal
    ) is None


def test_between_times_required_expression_rejects_flat_time_fields():
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off (2:30am-6:30am)",
            "addRequiredExpression": {
                "conditions": [{
                    "capability": "Between two times",
                    "startTime": "02:30",
                    "stopTime": "06:30",
                }],
                "operator": "AND",
            },
            "addTrigger": {
                "capability": "Switch",
                "deviceIds": ["7827"],
                "state": "on",
            },
            "addActions": [
                {"capability": "delay", "minutes": 30},
                {"capability": "switch", "action": "off", "deviceIds": ["7827"]},
            ],
        },
    }

    error = rule_machine_proposal_error("hub_manage_rule_machine", proposal)

    assert error is not None
    assert "contains unsupported fields" in error
    assert "start and end objects" in error
    assert "No action was queued or executed" in error


def test_between_times_required_expression_accepts_endpoint_maps():
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off (2:30am-6:30am)",
            "addRequiredExpression": {
                "conditions": [{
                    "capability": "Between two times",
                    "start": {"type": "clock", "time": "02:30"},
                    "end": {"type": "clock", "time": "06:30"},
                }],
                "operator": "AND",
            },
        },
    }

    assert rule_machine_proposal_error(
        "hub_manage_rule_machine", proposal
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


def test_time_window_rejects_trigger_capability_before_confirmation():
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off (Night)",
            "addRequiredExpression": {
                "conditions": [{
                    "capability": "Certain Time (and optional date)",
                    "comparator": "between",
                    "start": {"type": "clock", "time": "02:30"},
                    "end": {"type": "clock", "time": "06:30"},
                }],
                "operator": "AND",
            },
            "addTrigger": {
                "capability": "switch", "deviceIds": ["7827"], "state": "on",
            },
            "addAction": {
                "capability": "switch", "action": "off", "deviceIds": ["7827"],
            },
        },
    }

    error = rule_machine_proposal_error("hub_manage_rule_machine", proposal)

    assert error is not None
    assert "use capability='Between two times'" in error


def test_explicit_relative_delay_must_be_preserved_in_action_sequence():
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off (Night)",
            "addTrigger": {
                "capability": "switch", "deviceIds": ["7827"], "state": "on",
            },
            "addAction": {
                "capability": "switch", "action": "off", "deviceIds": ["7827"],
            },
        },
    }

    error = rule_machine_proposal_error(
        "hub_manage_rule_machine",
        proposal,
        user_prompt="Turn Big lamp off 30 minutes later",
    )

    assert error is not None
    assert "requires a 30-minute delay" in error


def test_matching_relative_delay_and_following_action_are_accepted():
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off (Night)",
            "addTrigger": {
                "capability": "switch", "deviceIds": ["7827"], "state": "on",
            },
            "addActions": [
                {"capability": "delay", "minutes": 30},
                {
                    "capability": "switch",
                    "action": "off",
                    "deviceIds": ["7827"],
                },
            ],
        },
    }

    assert rule_machine_proposal_error(
        "hub_manage_rule_machine",
        proposal,
        user_prompt="Turn Big lamp off 30 minutes later",
    ) is None


def test_singular_action_array_is_normalized_before_validation():
    observed = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off (Night)",
            "addTrigger": {
                "capability": "Switch", "deviceIds": ["7827"], "state": "on",
            },
            "addAction": [
                {"capability": "delay", "minutes": 30},
                {
                    "capability": "switch",
                    "action": "off",
                    "deviceIds": ["7827"],
                },
            ],
        },
    }

    normalized = normalize_rule_machine_proposal(
        "hub_manage_rule_machine", observed
    )

    assert "addAction" in observed["args"]
    assert "addAction" not in normalized["args"]
    assert normalized["args"]["addActions"] == observed["args"]["addAction"]
    assert rule_machine_proposal_error(
        "hub_manage_rule_machine",
        normalized,
        user_prompt="Turn Big lamp off 30 minutes later",
    ) is None


def test_plural_single_object_is_normalized_to_singular_container():
    observed = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Off",
            "addActions": {
                "capability": "switch",
                "action": "off",
                "deviceIds": ["7827"],
            },
        },
    }

    normalized = normalize_rule_machine_proposal(
        "hub_manage_rule_machine", observed
    )

    assert "addActions" not in normalized["args"]
    assert normalized["args"]["addAction"] == observed["args"]["addActions"]
    assert rule_machine_proposal_error(
        "hub_manage_rule_machine", normalized
    ) is None


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
            # Regression test: `_DESTRUCTIVE_ACTIONS` stores "factory_reset"
            # as one multi-word entry, but `_operation_effect` used to only
            # ever check single-word tokens split on "_" -- so
            # {"factory", "reset"} & _DESTRUCTIVE_ACTIONS was always empty
            # and this operation could never match, despite being a member
            # of the set itself.
            gateway("hub_manage_destructive_ops"),
            {"tool": "hub_factory_reset", "args": {}},
            ToolEffect.DESTRUCTIVE_WRITE,
        ),
        (
            gateway("hub_manage_destructive_ops"),
            {"tool": "hub_reset_database", "args": {}},
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
        (
            gateway("hub_manage_virtual_device"),
            {},
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("hub_manage_mode"),
            {},
            ToolEffect.SENSITIVE_WRITE,
        ),
    ],
)
def test_structured_tool_effect_classification(tool, arguments, expected):
    assert classify_tool_effect(tool, arguments) is expected


def test_direct_manage_tools_are_never_treated_as_a_gateway_schema_probe():
    """hub_manage_virtual_device/hub_manage_mode are direct tools, not
    gateways -- an empty-args call must fail closed to SENSITIVE_WRITE
    (requiring confirmation) instead of being waved through as the
    harmless no-argument gateway schema-discovery convention.
    """

    for name in ("hub_manage_virtual_device", "hub_manage_mode"):
        effect = classify_tool_effect(gateway(name), {})
        assert effect is ToolEffect.SENSITIVE_WRITE
        assert effect.requires_confirmation is True

    # Control case: an ordinary hub_manage_* gateway called empty is still
    # treated as a safe schema-discovery probe.
    assert (
        classify_tool_effect(gateway("hub_manage_devices", destructiveHint=True), {})
        is ToolEffect.READ
    )


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


def test_batched_setlevel_device_commands_are_routine_not_destructive():
    tool = gateway("hub_manage_devices", destructiveHint=True)
    arguments = {
        "tool": "hub_call_device_command",
        "args": {
            "commands": [
                {"deviceId": "7805", "command": "setLevel", "parameters": {"level": 100}},
                {"deviceId": "7828", "command": "setLevel", "parameters": {"level": 100}},
            ]
        },
    }

    assert classify_tool_effect(tool, arguments) is ToolEffect.ROUTINE_WRITE


def test_batched_device_commands_fail_closed_when_any_command_is_sensitive():
    tool = gateway("hub_manage_devices", destructiveHint=True)
    arguments = {
        "tool": "hub_call_device_command",
        "args": {
            "commands": [
                {"deviceId": "7805", "command": "setLevel", "parameters": {"level": 50}},
                {"deviceId": "99", "command": "unlock"},
            ]
        },
    }

    assert classify_tool_effect(tool, arguments) is ToolEffect.SENSITIVE_WRITE

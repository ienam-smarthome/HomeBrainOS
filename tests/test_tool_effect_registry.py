from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool  # noqa: E402
from tool_registry import (  # noqa: E402
    ToolEffect,
    classify_tool_effect,
    control_devices_tool,
    home_snapshot_tool,
)


def gateway(name: str, **annotations: object) -> MCPTool:
    return MCPTool(name, name, {"type": "object"}, annotations=annotations)


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (
            gateway("hub_read_devices"),
            {"tool": "hub_get_device_events", "args": {"command": "off"}},
            ToolEffect.READ,
        ),
        (
            gateway("hub_manage_devices"),
            {"tool": "hub_list_devices", "args": {}},
            ToolEffect.READ,
        ),
        (
            gateway("hub_manage_devices"),
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "off"},
            },
            ToolEffect.ROUTINE_WRITE,
        ),
        (
            gateway("hub_manage_devices"),
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "lock"},
            },
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


def test_shadow_comparison_reports_legacy_manage_read_mismatch(caplog):
    tool = gateway("hub_manage_devices")
    arguments = {"tool": "hub_list_devices", "args": {}}

    with caplog.at_level(logging.WARNING, logger="HomeBrainOS.Orchestrator"):
        effect = UnifiedMCPAgent._shadow_tool_effect(tool, arguments)

    assert effect is ToolEffect.READ
    assert UnifiedMCPAgent._call_is_mutation(tool, arguments) is True
    assert "Tool-effect shadow mismatch" in caplog.text


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

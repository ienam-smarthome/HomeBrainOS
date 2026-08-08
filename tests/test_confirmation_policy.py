from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from confirmation_policy import (  # noqa: E402
    ConfirmationAction,
    ConfirmationPolicy,
    SESSION_REQUIRED,
)
from tool_registry import ToolEffect  # noqa: E402


def action(name: str = "hub_restart") -> tuple[str, dict]:
    return name, {}


def test_requires_confirmation_uses_structured_effect_and_declared_state():
    policy = ConfirmationPolicy()

    assert policy.requires_confirmation(ToolEffect.SENSITIVE_WRITE)
    assert policy.requires_confirmation(ToolEffect.DESTRUCTIVE_WRITE)
    assert not policy.requires_confirmation(ToolEffect.ROUTINE_WRITE)
    assert not policy.requires_confirmation(ToolEffect.READ)
    assert not policy.requires_confirmation(
        ToolEffect.SENSITIVE_WRITE,
        declared=False,
    )


def test_disabled_policy_bypasses_confirmation():
    policy = ConfirmationPolicy(enabled=False)

    assert not policy.requires_confirmation(ToolEffect.DESTRUCTIVE_WRITE)
    assert policy.decide("session", [action()]).action is ConfirmationAction.BYPASS


def test_empty_action_group_bypasses_confirmation():
    decision = ConfirmationPolicy().decide("session", [])

    assert decision.action is ConfirmationAction.BYPASS
    assert decision.message is None


def test_empty_and_default_sessions_fail_closed():
    policy = ConfirmationPolicy()

    for session_id in ("", "  ", "default"):
        decision = policy.decide(session_id, [action()])
        assert decision.action is ConfirmationAction.REJECT
        assert decision.message == SESSION_REQUIRED


def test_action_group_limit_is_bounded_and_exact_limit_is_allowed():
    policy = ConfirmationPolicy(max_actions=12)

    allowed = policy.decide("session", [action() for _ in range(12)])
    rejected = policy.decide("session", [action() for _ in range(13)])

    assert allowed.action is ConfirmationAction.QUEUE
    assert rejected.action is ConfirmationAction.REJECT
    assert "more than 12 sensitive actions" in str(rejected.message)


def test_single_sensitive_action_names_the_gateway():
    decision = ConfirmationPolicy().decide("session", [action("hub_restart")])

    assert decision.action is ConfirmationAction.QUEUE
    assert decision.message == (
        "Please confirm before I run the sensitive Hubitat action `hub_restart`."
    )


def test_firmware_action_uses_explicit_restart_warning():
    decision = ConfirmationPolicy().decide(
        "session",
        [action("hub_update_firmware")],
    )

    assert decision.action is ConfirmationAction.QUEUE
    assert "install the available Hubitat firmware update" in str(decision.message)
    assert "may restart" in str(decision.message)


def test_multiple_actions_use_count_and_sorted_unique_gateway_names():
    decision = ConfirmationPolicy().decide(
        "session",
        [action("hub_shutdown"), action("hub_restart"), action("hub_restart")],
    )

    assert decision.message == (
        "Please confirm before I run 3 sensitive Hubitat actions through "
        "`hub_restart, hub_shutdown`."
    )


def test_unavailable_tool_message_is_sorted_and_deduplicated():
    message = ConfirmationPolicy.unavailable_tools_message(
        ["hub_shutdown", "hub_restart", "hub_shutdown"]
    )

    assert message == (
        "The queued Hubitat action was cancelled because its tool is no longer "
        "available: hub_restart, hub_shutdown."
    )


def test_rule_machine_approval_preserves_direct_payload_and_adds_confirm():
    proposed = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Tab S9 FE - Block (9am)",
            "bestPracticeKey": "live-key",
            "addTriggers": [{"atTime": "09:00"}],
            "addActions": [{"command": "blockInternet"}],
        },
    }

    approved = ConfirmationPolicy.approved_arguments(
        "hub_manage_rule_machine", proposed
    )

    assert approved["args"] == {
        **proposed["args"],
        "confirm": True,
    }
    assert "confirm" not in proposed["args"]


def test_confirm_bearing_gateway_operations_beyond_rule_machine_get_it_injected():
    """Regression test for a real bug found auditing the sensitive-write
    gateways beyond Rule Machine: approved_arguments() used to special-case
    only "hub_manage_rule_machine" for injecting confirm:true into the
    nested args object. Every other gateway operation confirmed (by
    inspecting its live MCP schema) to declare its own confirm parameter --
    a backup restore/delete, a Zwave/Zigbee radio change, a hub variable
    create/delete, an app/driver code edit, a destructive op, a room or
    dashboard delete, an MCP self-settings update, a device swap/replace/
    create -- never received the flag, so a user's explicit confirmation
    approval never actually reached Hubitat's own confirm gate for these.
    """

    gateway_calls = [
        ("hub_manage_backup", {"tool": "hub_restore_backup", "args": {"fileName": "x.zip"}}),
        ("hub_manage_backup", {"tool": "hub_delete_backup", "args": {"location": "local"}}),
        ("hub_manage_radio", {"tool": "hub_set_zwave", "args": {"enabled": False}}),
        ("hub_manage_radio", {"tool": "hub_call_zwave", "args": {"action": "node_remove"}}),
        ("hub_manage_variables", {"tool": "hub_delete_variable", "args": {"name": "AwayMode"}}),
        ("hub_manage_variables", {"tool": "hub_create_variable", "args": {"name": "X", "type": "String", "value": "y"}}),
        ("hub_manage_code", {"tool": "hub_update_app", "args": {"appId": "42", "source": "..."}}),
        ("hub_manage_code", {"tool": "hub_delete_item", "args": {"type": "driver", "item_id": "9"}}),
        (
            "hub_manage_native_rules_and_apps",
            {"tool": "hub_set_native_app", "args": {"appType": "Notifier", "name": "Alert"}},
        ),
        (
            "hub_manage_native_rules_and_apps",
            {"tool": "hub_delete_native_app", "args": {"appId": "17"}},
        ),
        ("hub_manage_destructive_ops", {"tool": "hub_reboot", "args": {}}),
        ("hub_manage_dashboards", {"tool": "hub_delete_dashboard", "args": {"dashboardId": "3"}}),
        ("hub_manage_rooms", {"tool": "hub_delete_room", "args": {"room": "Kitchen"}}),
        ("hub_manage_mcp", {"tool": "hub_update_mcp_settings", "args": {"settings": {}}}),
        ("hub_manage_devices", {"tool": "hub_create_device", "args": {"deviceTypeId": "5"}}),
    ]
    for tool_name, proposed in gateway_calls:
        approved = ConfirmationPolicy.approved_arguments(tool_name, proposed)

        assert approved["args"].get("confirm") is True, tool_name
        assert "confirm" not in proposed["args"], tool_name


def test_nested_operations_without_a_confirm_field_are_left_untouched():
    """Not every operation on a confirm-bearing gateway has a confirm field
    of its own -- hub_call_device_command verifies success via waitFor
    instead, RM runtime control (pause/resume/trigger) is routine rather
    than destructive, and the legacy custom-rule engine's update schema has
    no confirm field at all. Injecting an unrequested confirm key into one
    of these risks sending an unexpected parameter with unverifiable
    upstream behaviour, so these must be left exactly as proposed -- this
    is the real live regression: a prior blanket "inject into any nested
    args" fix broke exactly this case for device command dispatch (e.g. an
    unlock), which is why this stays a precise allowlist instead.
    """

    device_command = {
        "tool": "hub_call_device_command",
        "args": {"deviceId": "42", "command": "unlock"},
    }
    approved = ConfirmationPolicy.approved_arguments("hub_manage_devices", device_command)
    assert approved == device_command
    assert "confirm" not in approved["args"]

    rule_pause = {"tool": "hub_set_rule_paused", "args": {"ruleId": "10", "paused": True}}
    approved = ConfirmationPolicy.approved_arguments(
        "hub_manage_native_rules_and_apps", rule_pause
    )
    assert "confirm" not in approved["args"]

    custom_rule_update = {"tool": "hub_update_custom_rule", "args": {"ruleId": "3", "enabled": False}}
    approved = ConfirmationPolicy.approved_arguments(
        "hub_manage_custom_rules", custom_rule_update
    )
    assert "confirm" not in approved["args"]


def test_direct_tool_without_nested_args_still_uses_its_own_schema():
    """A genuinely direct (non-gateway) tool call -- no nested "args" object
    at all -- must keep falling back to the schema-declared behaviour;
    the nested-args generalisation must not affect this path.
    """

    schema_with_confirm = {"properties": {"confirm": {"type": "boolean"}}}
    approved = ConfirmationPolicy.approved_arguments(
        "hub_reboot", {"delaySeconds": 5}, tool_schema=schema_with_confirm
    )
    assert approved == {"delaySeconds": 5, "confirm": True}

    schema_without_confirm = {"properties": {"delaySeconds": {"type": "integer"}}}
    approved = ConfirmationPolicy.approved_arguments(
        "hub_reboot", {"delaySeconds": 5}, tool_schema=schema_without_confirm
    )
    assert approved == {"delaySeconds": 5}

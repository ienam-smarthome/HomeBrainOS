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

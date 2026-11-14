"""Command-first UI safety and fixture contracts; zero real Hubitat operations."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from action_card_projection import queued_action_card
from confirmation_policy import ConfirmationPolicy
from tool_registry import ToolEffect
from webui import render_page


def test_only_structured_pending_write_receives_action_card() -> None:
    assert queued_action_card([("hub_read_devices", {"tool": "hub_list_devices"})]) is None
    assert queued_action_card([]) is None
    assert queued_action_card([("hub_manage_devices", {"tool": "hub_get_device",
                                                        "args": {"deviceId": "DEMO-1"}})]) is None
    routine = queued_action_card([
        ("hub_manage_devices", {"tool": "hub_call_device_command",
                                "args": {"deviceId": "DEMO-1", "command": "off"}})
    ])
    assert routine and routine["effect_class"] == "routine_write"
    assert routine["status"] == "pending_confirmation"
    assert routine["actions"][0]["command"] == "off"
    assert routine["actions"][0]["fields"] == [{"kind": "device", "value": "DEMO-1"}]
    assert routine["dry_run_available"] is False
    assert routine["undo_available"] is False
    assert routine["edits_require_new_proposal"] is True


def test_sensitive_destructive_variants_and_privacy_projection() -> None:
    sensitive = queued_action_card([
        ("hub_manage_rule_machine", {"tool": "hub_set_rule",
                                     "args": {"operation": "create", "deviceId": "DEMO-2",
                                              "atTime": "01:00", "days": ["Monday", "Tuesday"],
                                              "apiKey": "PRIVATE-KEY", "macAddress": "SECRET-MAC"}})
    ])
    assert sensitive and sensitive["effect_class"] == "sensitive_write"
    assert sensitive["actions"][0]["fields"] == [
        {"kind": "device", "value": "DEMO-2"},
        {"kind": "time", "value": "01:00"},
        {"kind": "days", "value": "Monday, Tuesday"},
    ]
    assert "PRIVATE-KEY" not in str(sensitive)
    assert "SECRET-MAC" not in str(sensitive)

    destructive = queued_action_card([
        ("hub_manage_destructive_ops", {"tool": "hub_delete_device",
                                        "args": {"deviceId": "DEMO-3"}})
    ])
    assert destructive and destructive["effect_class"] == "destructive_write"


def test_read_and_pending_write_remain_distinct() -> None:
    combined = queued_action_card([
        ("hub_get_info", {}),
        ("hub_manage_destructive_ops", {"tool": "hub_reboot", "args": {}}),
    ])
    assert combined
    assert combined["action_count"] == 2
    assert combined["effect_class"] == "destructive_write"
    assert combined["actions"][0]["effect"] == "read"
    assert combined["actions"][1]["effect"] == "destructive_write"


def test_routine_write_queues_via_existing_policy() -> None:
    policy = ConfirmationPolicy()
    assert policy.requires_confirmation(ToolEffect.ROUTINE_WRITE)
    assert policy.requires_confirmation(ToolEffect.SENSITIVE_WRITE)
    assert policy.requires_confirmation(ToolEffect.DESTRUCTIVE_WRITE)
    assert not policy.requires_confirmation(ToolEffect.READ)
    assert not policy.requires_confirmation(ToolEffect.ROUTINE_WRITE, declared=False)


def test_ui_sticky_command_feed_and_keyboard_grammar() -> None:
    page = render_page("HomeBrain", "0.18.460")
    for contract in (
        'id="commandForm"', 'id="query"', 'id="speak"',
        'id="ask" type="submit"', 'id="exchangeFeed"',
        'id="summaryTiles"', 'id="connectionPill"',
        'id="monitoringPanels"', 'id="voiceStatus"',
        'id="dashDevices"', 'id="overviewNote"',
        'role="status"', 'aria-label="Ask HomeBrain"',
        "event.key==='Enter'&&!event.shiftKey",
        "event.key==='Escape'",
        "event.key==='/'",
        "void submit(query.value)",
        "finishVoice(true)",
        "recognition.lang='en-GB'",
        "Voice input may use a browser speech service.",
    ):
        assert contract in page, contract
    assert "fonts.googleapis.com" not in page
    assert "query.match(/block" not in page
    assert "function beginExchange(question)" in page
    assert "answer.classList.add('older')" in page


def test_evidence_and_stage_renderers_use_only_received_data() -> None:
    page = render_page("HomeBrain", "0.18.460")
    for contract in (
        "function renderEvidence(data,host)",
        "row.supports_live_claim===true",
        "const rows=Array.isArray(data.evidence)?data.evidence:[]",
        "Evidence · ",
        "Download PRIVATE JSON",
        "Inspect it before sharing",
        "metrics.model_round_details",
        "row.elapsed_ms??row.duration_ms",
        "recordTrace(progress.stage,Number(progress.elapsed_seconds))",
        "renderPendingAction(data,body)",
        "if(data.confirmation_required===true)",
        "function actionCardVariant(data)",
        "api/confirmation/dismiss",
        "window.confirm(",
        "void submit('confirm')",
        "edits require",
    ):
        assert contract.lower() in page.lower(), contract
    assert "Math.random()*500" not in page
    assert "Dry-run: this would have" not in page
    assert 'data-q="Block Google TV' not in page


def test_generated_inline_javascript_parses_if_node_installed() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed locally")
    page = render_page("HomeBrain", "0.18.460")
    script = page.split("<script>", 1)[-1].split("</script>", 1)[0]
    assert script and "function showAnswer" in script
    result = subprocess.run([node, "--check", "--input-type=commonjs"],
                            input=script, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr

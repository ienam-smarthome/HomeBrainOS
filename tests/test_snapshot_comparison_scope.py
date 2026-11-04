"""Q1 state-comparison vs historical scope regression (synthetic only).

Ordinary multi-device status must not activate one-sided event-history
checkpoints or turn history absence into a failed current-state question.
Explicit historical and causal comparisons retain their original scope.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai/rootfs/app"))

from investigation_policy import (  # noqa: E402
    is_history_investigation, is_snapshot_comparison,
    uses_known_history_evidence_path,
)
from investigation_checkpoint import is_investigative_question  # noqa: E402
from target_history_scope import (  # noqa: E402
    inspect_target_history_scope,
    render_target_scope_followup,
    guard_unscoped_target_history_denial,
)
from skills_framework import select_skills  # noqa: E402
from agent_prompt_policy import build_system_prompt  # noqa: E402


@pytest.mark.parametrize("question", [
    "Compare the states of Hallway Light 1 and Livingroom Light 2.",
    "Compare current switch states of two bedroom lights.",
    "Compare the brightness levels of these two dimmers.",
    "Compare the present status of Device A and Device B.",
    "Contrast the reported levels of Lamp A and Lamp B.",
])
def test_current_state_comparison_is_not_event_history(question):
    assert is_snapshot_comparison(question)
    assert not is_history_investigation(question)
    assert not uses_known_history_evidence_path(question)
    assert not is_investigative_question(question)
    assert "hubitat-investigator" not in select_skills(question)


@pytest.mark.parametrize("question", [
    "Compare the states of Lamp A and Lamp B yesterday.",
    "Compare the states of Hallway Light 1 and Livingroom Light 2 over time.",
    "Compare the switch states of both lights and their event history.",
    "Compare the recent changes in switch states of both lights.",
    "Compare the states of both lights and explain why one turned off.",
    "Compare the states of both lights after the last automation command.",
    "Compare the normal and abnormal activity of two lights.",
    "Compare their event histories, including ON/OFF transitions.",
    "Why did Hallway Light 1 turn off?",
    "Are the Hallway Light 1 and Livingroom Light 2 cycles unusual?",
])
def test_historical_or_causal_comparisons_keep_investigation(question):
    assert not is_snapshot_comparison(question)
    assert is_history_investigation(question)
    assert is_investigative_question(question)


@pytest.fixture
def two_device_receipts():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "effect": "read", "mutates": False,
            "evidence_kind": "targeted_device_lookup",
            "arguments": {"tool": "hub_list_devices", "args": {
                "labelFilter": label,
            }},
            "details": {"reportedDeviceState": {
                "deviceId": ident, "label": label,
                "reportedAttributes": {"switch": "off", "level": level},
            }},
        }
        for ident, label, level in [
            ("701", "Test Hall Light", 50),
            ("702", "Test Lounge Light", 60),
        ]
    ] + [{
        # Only one of two targets had a 24-hour event read, precisely the
        # unnecessary one-sided exploration seen in the live Q1 capture.
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": "authoritative_device_event_history",
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "701", "hoursBack": 24,
        }},
    }]


def test_unrequested_one_sided_history_does_not_mark_state_comparison_unresolved(two_device_receipts):
    question = "Compare the states of Test Hall Light and Test Lounge Light."
    assert inspect_target_history_scope(question, two_device_receipts) is None
    assert render_target_scope_followup(question, two_device_receipts) is None
    original = "The two devices reported switch off and retained levels 50% and 60%."
    guarded, changed = guard_unscoped_target_history_denial(
        original, question, two_device_receipts,
    )
    assert guarded == original
    assert not changed


def test_history_comparison_still_requires_both_target_reads(two_device_receipts):
    question = "Compare the states of Test Hall Light and Test Lounge Light over time."
    coverage = inspect_target_history_scope(question, two_device_receipts)
    assert coverage is not None
    assert coverage["target_scoped_read_ids"] == ["701"]
    assert coverage["missing_target_read_ids"] == ["702"]
    assert render_target_scope_followup(question, two_device_receipts)
    assert coverage["history_completeness_proven"] is False


def test_status_prompt_explicitly_limits_unrequested_history_and_causal_claims():
    prompt = build_system_prompt("", "")
    assert "do not broaden a current snapshot into event history" in prompt
    assert "retained dimmer level while switch=off" in prompt
    assert "neither an event listener nor temporal proximity" in prompt


def test_routine_noncomparison_status_and_commands_are_unaffected():
    for prompt in (
        "What is the current state of Test Lamp?",
        "Turn on Test Lamp.",
        "Set a bedroom light to 30%.",
    ):
        assert not is_snapshot_comparison(prompt)
        assert not is_history_investigation(prompt)

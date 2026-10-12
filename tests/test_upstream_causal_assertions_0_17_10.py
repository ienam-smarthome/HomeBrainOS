"""Causal attribution must distinguish who sent a command from what triggered it.

The model may correctly label upstream alternatives "not established" in a
table yet contradict itself in a causal explanation. Test the independent
claims rather than relying on one fixed wording of "Manual Control: Ruled out".
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from causal_attribution_guard import guard_unproven_upstream_manual_exclusion  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402


def app_command_evidence() -> list[dict]:
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Example Light",
            "attribute": "switch",
            "temporalAnalysis": {
                "intervalCount": 1,
                "observedIntervals": [{
                    "start": "2026-10-12T07:53:36.721+0100",
                    "end": "2026-10-12T08:10:58.185+0100",
                    "durationSeconds": 1041,
                }],
            },
            "commandEvents": [{
                "name": "command-setLevel",
                "date": "2026-10-12T07:53:36.621+0100",
                "description": "Command called: setLevel(50)",
                "producedBy": {
                    "type": "app", "id": "1234",
                    "label": "Example Lighting Automation",
                },
            }],
        },
    }]


def _sample_message() -> str:
    return (
        "### Investigation: Example Light\n"
        "* **The Producer:** The automation issued setLevel(50). This "
        "deterministically identifies the automation as the source, "
        "ruling out a manual physical switch press.\n"
        "* **The Trigger:** Configured occupancy motion was active "
        "immediately before the command.\n"
        "* **Manual Control:** The automation issued the device command; "
        "manual input upstream of that automation was not independently excluded.\n"
        "| Element | Status | Evidence |\n"
        "| :--- | :--- | :--- |\n"
        "| **Manual/Mode Cause** | **Not established** | "
        "Upstream causes remain unresolved. |\n"
    )


def test_model_contradiction_corrected_without_erasing_confirmed_source():
    fixed, changed = guard_unproven_upstream_manual_exclusion(
        _sample_message(), app_command_evidence()
    )
    assert changed
    assert "ruling out a manual physical switch press" not in fixed
    assert "without independently excluding an upstream manual action" in fixed
    assert "The automation issued setLevel(50)" in fixed
    assert "| **Manual/Mode Cause** | **Not established** |" in fixed
    assert "Configured occupancy motion was active" in fixed


def test_synonyms_and_passive_voice_have_same_causal_boundaries():
    cases = [
        (
            "The final app command rules out any manual input.",
            "without independently excluding an upstream manual action",
        ),
        (
            "The app produced it, excluding physical switch interaction.",
            "without independently excluding an upstream manual action",
        ),
        (
            "Manual physical switch presses were ruled out.",
            "manual input upstream of that automation was not independently excluded",
        ),
        (
            "The app issued the command, ruling out other automations.",
            "without independently excluding upstream automations",
        ),
        (
            "The immediate app source rules out a mode change.",
            "without independently excluding an upstream mode influence",
        ),
    ]
    for draft, supported in cases:
        fixed, changed = guard_unproven_upstream_manual_exclusion(
            draft, app_command_evidence()
        )
        assert changed, draft
        assert supported in fixed, fixed


def test_valid_cautious_negation_and_unrelated_exclusion_are_preserved():
    cases = [
        "App 1234 produced setLevel(50), without ruling out manual input.",
        "The app produced the command, not ruling out a physical switch press.",
        "The recorded event rules out an unrelated power outage.",
        "No direct manual command was identified for this transition.",
    ]
    for line in cases:
        fixed, changed = guard_unproven_upstream_manual_exclusion(
            line, app_command_evidence()
        )
        assert not changed, line
        assert fixed == line


def test_no_app_command_does_not_invent_immediate_app_provenance():
    evidence = [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Example Light",
            "attribute": "switch",
            "temporalAnalysis": {"intervalCount": 0, "observedIntervals": []},
        },
    }]
    fixed, changed = guard_unproven_upstream_manual_exclusion(
        _sample_message(), evidence
    )
    assert not changed
    assert "ruling out a manual physical switch press" in fixed


def test_user_live_answer_failsafe_in_synthesis_and_api_serializer():
    question = (
        "Investigate thoroughly why Example Light turned on at 07:53:36 "
        "on 12 October. Explain what is confirmed and likely. Read-only."
    )
    corrected, issues = validate_synthesis(
        _sample_message(), app_command_evidence(),
        original_user=question, causal=True
    )
    assert "upstream_manual_exclusion" in issues
    assert "ruling out a manual physical switch press" not in corrected

    outcome = SimpleNamespace(
        message=_sample_message(),
        evidence=app_command_evidence(),
        metrics={"outcome": "success", "counters": {"model_rounds": 5}},
        route="unified-mcp-agent",
        request_class="live-read",
    )
    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=43699, version="0.17.10"
    )
    assert response["version"] == "0.17.10"
    assert "ruling out a manual physical switch press" not in response["message"]
    assert "without independently excluding an upstream manual action" in response["message"]
    assert "App 1234" not in response["message"] or "The automation issued setLevel(50)" in response["message"]

"""Framework regressions: progressive skills, facts-first hypotheses and secrecy."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from skills_framework import render_skills_for_request, select_skills, skill_index
from skill_secret_guard import redact_model_messages, redact_secrets
from skill_investigation import build_skill_investigation, render_skill_investigation
from skill_topology import build_topology_plan, render_topology_plan


QUESTION = "Why did Livingroom Light 1 turn ON at 19:55 on 14 October 2026? Read-only."


def _case():
    return [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "arguments": {"name": "Livingroom Light 1", "attribute": "switch"},
            "details": {
                "label": "Livingroom Light 1", "attribute": "switch",
                "temporalAnalysis": {"observedIntervals": [{
                    "start": "2026-10-14T19:55:00.049+0100",
                    "end": "2026-10-14T22:45:40.112+0100",
                    "durationSeconds": 10240,
                }]},
                "correlationEvents": [
                    {"name": "switch", "value": "off", "date": "2026-10-14T19:54:57.946+0100",
                     "producedBy": {"label": "Matter Hue Bridge Pro", "type": "device"}},
                    {"name": "switch", "value": "on", "date": "2026-10-14T19:55:00.049+0100",
                     "producedBy": {"label": "Matter Hue Bridge Pro", "type": "device"}},
                ],
            },
        },
        {
            "success": True, "tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events",
            "arguments": {"args": {"attribute": "command-on", "deviceId": "7805"}},
            "details": {"label": "Livingroom Light 1", "eventName": "command-on", "events": [{
                "name": "command-on", "date": "2026-10-14T19:54:46.691+0100",
                "type": "command", "description": "Command called: on()",
                "producedBy": {"label": "SenseCap D1 Settings", "id": "4129", "type": "app"},
            }]},
        },
    ]


def test_intent_activation_and_bundled_operating_skill():
    assert select_skills("What's the weather tomorrow?") == ()
    assert select_skills("Turn on Bedroom Light 1") == ("hubitat-operations",)
    assert select_skills(QUESTION) == ("hubitat-operations", "hubitat-investigator")
    prompt = render_skills_for_request(QUESTION)
    assert "HOST" not in prompt[:25]  # active skills are labelled, not evidence receipts
    assert "ACTIVE HOMEBRAIN SKILL: hubitat-investigator" in prompt
    assert "hub_search_tools" in prompt
    assert "intervening OFF" in prompt
    assert "never" in prompt.lower()
    assert len(skill_index()) == 2


def test_missing_skill_is_not_substituted_or_executed():
    from skills_framework import _read_skill
    assert _read_skill("../../arbitrary") == ""


def test_live_failure_ranked_with_intervening_off_not_external_proof():
    projection = build_skill_investigation(_case(), QUESTION)
    assert projection is not None
    assert projection["focusTime"] == "2026-10-14T19:55:00.049+0100"
    command = [r for r in projection["facts"] if r["kind"] == "preceding_hubitat_command"]
    assert len(command) == 1
    assert command[0]["delaySeconds"] == 13.358
    assert command[0]["producer"] == "SenseCap D1 Settings"
    assert command[0]["confidence"] == "verified-command-invocation-not-delivery"
    anomalies = [r for r in projection["facts"] if r["kind"] == "intervening_state_changes"]
    assert anomalies[0]["events"][0]["state"] == "off"
    assert projection["hypotheses"][0]["kind"] == "prior_hubitat_command_effect"
    assert "not-established" == projection["hypotheses"][-1]["status"]
    assert "bridge" in render_skill_investigation(_case(), QUESTION).lower()


def test_topology_plan_prioritises_command_producer_app_not_nearby_room_guesses():
    result = build_topology_plan(_case(), QUESTION)
    assert result is not None
    assert result["commandProducer"]["appId"] == "4129"
    assert result["currentSourceCoverage"]["appConfiguration"] == "not-checked"
    assert any(r["source"] == "controlling_app_configuration" for r in result["recommendedReads"])
    assert "4129" in render_topology_plan(_case(), QUESTION)
    assert "historicalConfigurationVerified" in result["currentSourceCoverage"]


def test_secret_values_redacted_without_modifying_source_messages():
    source = [
        {"role": "user", "content": "Check MQTT service password configuration"},
        {"role": "tool", "content": '{"mqttPassword":"test-pass","access_token":"abcdef","deviceId":"7805"}'},
        {"role": "user", "content": "HOST CONFIG\nclientSecret=abc123"},
    ]
    sanitized = redact_model_messages(source)
    assert sanitized[0]["content"] == source[0]["content"]
    assert "test-pass" not in sanitized[1]["content"]
    assert "abcdef" not in sanitized[1]["content"]
    assert '"deviceId":"7805"' in sanitized[1]["content"]
    assert "abc123" not in sanitized[2]["content"]
    assert "test-pass" in source[1]["content"]  # raw receipt left unchanged
    assert "tok123" not in redact_secrets("Authorization: Bearer tok123")

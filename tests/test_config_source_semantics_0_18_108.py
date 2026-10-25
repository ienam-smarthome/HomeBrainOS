"""0.18.108 — live failure replay: raw app config != effective Groovy behavior.

One case uses the observed Livingroom app 4019 raw 'inactiveAction'
conclusion (wrong against the displayed 30s/5m effective UI). Another
tests an unrelated app/field to prove this is not a keyword-specific route.
All fake receipts are READ ONLY; no live Hubitat access.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from source_analysis_completion import (
    configuration_semantics_evidence_gap,
    configuration_semantics_followup,
    guard_unverified_config_behavior,
)
from synthesis_validator import validate_synthesis
from request_metrics import RequestMetrics


def app_config(app_id: str, *, ok: bool = True, **details):
    return {
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": ok,
        "mutates": False,
        "effect": "read",
        "arguments": {
            "tool": "hub_get_app_config", "args": {"appId": app_id},
        },
        "details": details,
    }


def installed_code(app_id: str):
    return {
        "tool": "homebrain_read_groovy_source",
        "sub_tool": None, "success": True,
        "mutates": False, "effect": "read",
        "arguments": {"appId": app_id},
        "details": {"verifiedCandidateMethodBodies": ["inactiveHandler"]},
    }


LIGHT_ANSWER = (
    'The app summary mentions the 30-second timeout, but '
    'the live configuration for \`inactiveAction\` is **\`"none"\`**. '
    'This means the automation is explicitly configured to not issue '
    'an off command when motion stops.\n\n'
    'Sensor Linptech Kitchen is currently active, but this does not '
    'prove it stayed active all night.\n\n'
    'To enable automatic deactivation, change inactiveAction from '
    '"none" to "off".'
)


def test_detect_real_app_config_to_source_evidence_gap():
    receipts = [app_config("4019")]
    assert configuration_semantics_evidence_gap(receipts) == ("4019",)
    hint = configuration_semantics_followup(LIGHT_ANSWER, receipts)
    assert hint is not None
    assert "4019" in hint and "installed" in hint
    assert "read-only" in hint.lower()
    assert "UNKNOWN" in hint
    assert "source code ID" in hint


def test_runtime_claim_is_calibrated_and_setting_change_advice_removed():
    receipts = [app_config("4019")]
    corrected, changed = guard_unverified_config_behavior(LIGHT_ANSWER, receipts)
    assert changed
    assert "not verified" in corrected
    assert "cannot establish effective automatic behaviour" in corrected
    assert "Sensor Linptech Kitchen is currently active" in corrected
    assert 'change inactiveAction from' not in corrected
    assert "A change to that setting is not justified" in corrected
    corrected2, issues = validate_synthesis(LIGHT_ANSWER, receipts)
    assert "unverified_configuration_semantics" in issues
    assert "change inactiveAction from" not in corrected2


def test_source_receipt_covers_exact_installed_app_without_requiring_keywords():
    source_read = [app_config("4019"), installed_code("4019")]
    assert configuration_semantics_evidence_gap(source_read) == ()
    assert configuration_semantics_followup(LIGHT_ANSWER, source_read) is None
    unchanged, changed = guard_unverified_config_behavior(LIGHT_ANSWER, source_read)
    assert not changed and unchanged == LIGHT_ANSWER


def test_unrelated_app_source_does_not_prove_target_app_semantics():
    receipts = [app_config("4019"), installed_code("3000")]
    assert configuration_semantics_evidence_gap(receipts) == ("4019",)
    assert configuration_semantics_followup(LIGHT_ANSWER, receipts) is not None


def test_generic_non_lighting_app_claim_and_read_only_scope():
    receipts = [app_config("3977")]
    draft = (
        "The raw \`retryPolicy\` = \`none\` means this installed app "
        "never retries MQTT messages.\n\n"
        "The app's current enabled status is on."
    )
    hint = configuration_semantics_followup(draft, receipts)
    assert hint is not None and "3977" in hint
    revised, changed = guard_unverified_config_behavior(draft, receipts)
    assert changed and "never retries MQTT" not in revised
    assert "current enabled status is on" in revised


def test_no_retry_for_simple_config_listing_or_missing_source_identity():
    receipts = [app_config("3977")]
    assert configuration_semantics_followup(
        "The installed app has a stored value: retryPolicy=none.", receipts
    ) is None
    assert configuration_semantics_followup(
        "The app appears enabled.", receipts
    ) is None
    assert configuration_semantics_evidence_gap(
        [app_config("3977", ok=False)]
    ) == ()
    assert configuration_semantics_evidence_gap(
        [app_config("3977"), {
            "tool": "hub_manage_apps", "sub_tool": "hub_get_source",
            "arguments": {"args": {"id": "3977"}},
            "success": True, "mutates": True,
            "effect": "write",
        }]
    ) == ("3977",)


def test_hub_source_code_id_must_be_explicitly_mapped_to_app():
    receipts = [app_config("4019", appTypeId=1453), {
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_source",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"args": {"id": "1453"}},
    }]
    assert configuration_semantics_evidence_gap(receipts) == ()
    assert configuration_semantics_evidence_gap(
        [app_config("4019"), receipts[-1]]
    ) == ("4019",)


def test_unverified_paragraph_does_not_corrupt_timeline_or_already_uncertain_claim():
    narrative = (
        "The raw \`inactiveAction\` = \`none\` means automatic-off is disabled."
        "\n\n| Start | End | Duration |\n| --- | --- | --- |\n"
        "| 20:23 | 00:41 | 4h 19m |\n\n"
        "It is unknown whether all three motion sources were inactive."
    )
    revised, changed = guard_unverified_config_behavior(
        narrative, [app_config("4019")],
    )
    assert changed
    assert "| 20:23 | 00:41 | 4h 19m |" in revised
    assert "unknown whether all three motion sources" in revised


def test_model_retry_wiring_is_bounded_and_read_only():
    code = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "configuration_semantics_retry_used = False" in code
    assert "configuration_semantics_followup(" in code
    assert "round_index + 1 < active_round_budget" in code
    assert "not self._mutation_requested_by_user.get()" in code
    assert "_LOCAL_GROOVY_SOURCE_TOOL" in code
    assert "configuration_semantics_source_retry" in RequestMetrics.ALLOWED_COUNTERS

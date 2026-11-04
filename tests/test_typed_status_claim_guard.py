"""Source-typed status-grounding tests: no model, no network, no device writes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai/rootfs/app"
sys.path.insert(0, str(APP))

from typed_status_claim_guard import guard_typed_status_claims  # noqa: E402
from agent_prompt_policy import build_system_prompt  # noqa: E402

REPORTED = {
    "cpu_5_min": 0.78,
    "cpu_percent": 19.5,
    "cpu_15_min": 0.91,
    "cpu_15_percent": 22.83,
    "free_memory": 756.39,
    "free_memory_unit": "MB",
    "database_size": 175,
    "database_size_unit": "MB",
    "installed_firmware": "2.5.3.117",
    "available_firmware": "2.5.3.117",
    "firmware_status_settled": True,
    "zigbee_healthy": "true",
    "zigbee_status": "enabled",
    "zwave_status": "disabled",
    "zwave_healthy": "false",
    "matter_status": "online",
    "uptime": "0d:18h:33m:54s",
    "temperature_unit": "°C",  # unit alone is NOT a measured value
    # No numeric temperature, no hub_alerts.
}


def snapshot(reported=None, *, matched=True, success=True, kind="authoritative_hub_info_snapshot"):
    return [{
        "tool": "homebrain_hub_info_snapshot",
        "success": success,
        "effect": "read",
        "mutates": False,
        "supports_live_claim": True,
        "evidence_kind": kind,
        "details": {
            "sourceType": "hub_information_driver",
            "sourceScopeMatched": matched,
            "reported": REPORTED if reported is None else reported,
            "limitations": "Only driver-reported scalar fields; no physical audit",
        },
    }]


def test_real_hub_health_failure_is_localized_without_erasing_supported_values():
    model = (
        "The hub is healthy with no active alerts. "
        "Hub firmware 2.5.3.117 is up to date. Hub resources:\n\n"
        "- **CPU load (5 min):** 0.78 / 19.5%\n"
        "- **Free memory:** 756.39 MB\n"
        "- **Temperature:** 42.5 °C\n"
        "- **Uptime:** 0d:18h:33m:54s\n"
        "- **Database size:** 175 MB\n"
        "- **Zigbee:** Online\n"
        "- **Z-Wave:** Disabled\n"
        "- **Matter:** online"
    )
    output, issues = guard_typed_status_claims(model, snapshot())
    assert "42.5" not in output
    assert "- **Temperature:** not reported in the checked Hub Info snapshot" in output
    assert "The hub is healthy with no active alerts" not in output
    assert "independent full-health or alert audit" in output
    assert "firmware 2.5.3.117 matches" in output
    assert "external update freshness is unverified" in output
    assert "- **Zigbee:** enabled (driver-reported healthy=true)" in output
    for supported in (
        "0.78 / 19.5%", "756.39 MB", "0d:18h:33m:54s",
        "175 MB", "**Z-Wave:** Disabled", "**Matter:** online"
    ):
        assert supported in output
    assert {"temperature_missing", "hub_health_absence_overclaim",
            "firmware_external_freshness_unverified",
            "zigbee_online_overclaim"}.issubset(set(issues))


def test_complete_matching_snapshot_preserves_supported_model_authored_answer():
    supported = {
        **REPORTED, "temperature": 43.1, "temperature_unit": "°C",
        "zigbee_status": "online", "hub_alerts": "1 warning",
    }
    answer = (
        "Resource states reported by Hub Info:\n"
        "- **Temperature:** 43.1 °C\n"
        "- **Free memory:** 756.39 MB\n"
        "- **Database size:** 175 MB\n"
        "- **CPU load (5 min):** 0.78 / 19.5%\n"
        "- **Zigbee:** online\n"
        "- **Matter:** online"
    )
    result, issues = guard_typed_status_claims(answer, snapshot(supported))
    assert result == answer
    assert issues == []


@pytest.mark.parametrize(("label", "value", "expected_issue", "reported_value"), [
    ("Temperature", "90 °F", "temperature_mismatch", 37.5),
    ("Free memory", "942 MB", "free_memory_mismatch", 756.39),
    ("CPU load (5 min)", "2.5 / 80%", "cpu_mismatch", 0.78),
    ("Database size", "499 MB", "database_mismatch", 175),
])
def test_wrong_precise_scalar_claims_are_replaced_by_actual_typed_values(
    label, value, expected_issue, reported_value
):
    reported = {
        **REPORTED, "temperature": 37.5, "temperature_unit": "°C",
    }
    output, issues = guard_typed_status_claims(
        f"- **{label}:** {value}", snapshot(reported)
    )
    assert expected_issue in issues
    assert value not in output
    assert str(reported_value) in output


def test_source_reported_hub_alerts_is_not_independent_no_alerts_proof():
    report = {**REPORTED, "hub_alerts": "none"}
    output, issues = guard_typed_status_claims(
        "The hub is healthy with no active alerts.", snapshot(report)
    )
    assert "hub is healthy" not in output.casefold()
    assert "not an independent full-health or alert audit" in output
    assert issues


def test_unreported_cpu_memory_and_radio_status_are_not_treated_as_zero_or_online():
    report = {**REPORTED}
    report.update({
        "cpu_5_min": None,
        "cpu_percent": None,
        "free_memory": None,
        "matter_status": None,
        "zigbee_status": None,
    })
    text = (
        "- **CPU load:** 0.2 / 5%\n"
        "- **Free memory:** 1 GB\n"
        "- **Zigbee:** online\n"
        "- **Matter:** online"
    )
    final, issues = guard_typed_status_claims(text, snapshot(report))
    assert "0.2 / 5%" not in final
    assert "1 GB" not in final
    assert "**Zigbee:** status not reported" in final
    assert "**Matter:** status not reported" in final
    assert {"cpu_missing", "free_memory_missing", "zigbee_missing",
            "matter_missing"}.issubset(issues)


def test_firmware_mismatch_reports_both_versions_without_claiming_freshness():
    report = {**REPORTED, "available_firmware": "2.5.3.118"}
    text = "Hub firmware 2.5.3.117 is up to date."
    final, issues = guard_typed_status_claims(text, snapshot(report))
    assert "2.5.3.118" in final
    assert "differs from" in final
    assert "external update freshness is unverified" in final
    assert "firmware_external_freshness_unverified" in issues


def test_unmatched_and_errored_receipts_cannot_trigger_status_rewrites():
    original = "The hub is healthy with no active alerts. Temperature: 54.5 °C"
    for receipts in (
        [],
        snapshot(matched=False),
        snapshot(success=False),
        snapshot(kind="unrelated_device_history"),
        [{**snapshot()[0], "mutates": True}],
        [{**snapshot()[0], "effect": "sensitive_write"}],
        [{**snapshot()[0], "details": {"reported": REPORTED}}],
    ):
        final, issues = guard_typed_status_claims(original, receipts)
        assert final == original
        assert issues == []


def test_correction_has_no_device_id_private_argument_or_new_status_read():
    report = {**REPORTED, "temperature": None, "hub_alerts": None}
    source = snapshot(report)
    source[0]["arguments"] = {"apiKey": "never-export-me", "deviceId": "8801"}
    final, issues = guard_typed_status_claims(
        "- **Temperature:** 99.9 °C\nThe hub is healthy.", source
    )
    assert "99.9" not in final
    assert "never-export-me" not in final
    assert "8801" not in final
    assert len(issues) >= 2


def test_general_prompt_rejects_null_measures_and_global_health_assumptions():
    prompt = build_system_prompt("", "")
    assert "A missing/null measurement remains unverified" in prompt
    assert "missing hubAlerts field cannot establish" in prompt
    assert "driver-reported" in prompt.casefold()

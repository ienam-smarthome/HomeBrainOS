"""Universal typed-source claim attestation: no model, Hubitat, HA or router IO."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai/rootfs/app"
sys.path.insert(0, str(APP))

from typed_status_claim_guard import guard_typed_status_claims  # noqa: E402
from agent_prompt_policy import build_system_prompt  # noqa: E402

HUB = {
    "cpu_5_min": 0.78, "cpu_percent": 19.5,
    "cpu_15_min": 0.91, "cpu_15_percent": 22.83,
    "free_memory": 756.39, "free_memory_unit": "MB",
    "database_size": 175, "database_size_unit": "MB",
    "installed_firmware": "2.5.3.117",
    "available_firmware": "2.5.3.117",
    "firmware_status_settled": True,
    "zigbee_healthy": "true", "zigbee_status": "enabled",
    "zwave_status": "disabled", "zwave_healthy": "false",
    "matter_status": "online",
    "uptime": "0d:18h:33m:54s",
    "temperature_unit": "°C",  # Unit does NOT establish a measurement.
}


def hub(facts=None, *, success=True, matched=True, kind="authoritative_hub_info_snapshot"):
    return [{
        "tool": "homebrain_hub_info_snapshot",
        "success": success, "effect": "read", "mutates": False,
        "supports_live_claim": True,
        "evidence_kind": kind,
        "details": {
            "sourceType": "hub_information_driver",
            "sourceScopeMatched": matched,
            "reported": HUB if facts is None else facts,
        },
    }]


def device(label="Sample Lamp", device_id="701", values=None, *, success=True, source=True):
    return [{
        "tool": "homebrain_resolve_device",
        "success": success, "effect": "read", "mutates": False,
        "supports_live_claim": source,
        "evidence_kind": "deterministic_targeted_device_resolution",
        "details": {"reportedDeviceState": {
            "deviceId": device_id, "label": label,
            "source": "verified-resolved-device-hubitat-state",
            "reportedAttributes": (
                {"switch": "off", "level": 60} if values is None else values
            ),
        }},
    }]


def test_real_hub_health_answer_rejects_missing_measurements_but_preserves_good_facts():
    answer = (
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
    output, issues = guard_typed_status_claims(answer, hub())
    assert "42.5" not in output
    assert "**Temperature**: not reported in the checked source" in output
    assert "healthy with no active alerts" not in output
    assert "do not establish complete system health" in output
    assert "Firmware 2.5.3.117 matches" in output
    assert "external update freshness unverified" in output
    assert "**Zigbee**: enabled (source-reported healthy=true)" in output
    for supported in (
        "0.78 / 19.5%", "756.39 MB", "0d:18h:33m:54s",
        "175 MB", "**Z-Wave**: Disabled", "**Matter**: online",
    ):
        assert supported in output
    assert {"temperature_not_reported", "unverified_global_health",
            "firmware_external_freshness_unverified",
            "radio_enabled_not_online"}.issubset(set(issues))


def test_full_numeric_and_status_values_are_left_in_model_wording():
    facts = {
        **HUB, "temperature": 43.1, "temperature_unit": "°C",
        "zigbee_status": "online",
    }
    natural = (
        "Hub Info reported these values:\n"
        "- **Temperature:** 43.1 °C\n"
        "- **Free memory:** 756.39 MB\n"
        "- **Database size:** 175 MB\n"
        "- **CPU load (5 min):** 0.78 / 19.5%\n"
        "- **Zigbee:** online\n"
        "- **Matter:** online"
    )
    output, issues = guard_typed_status_claims(natural, hub(facts))
    assert output == natural
    assert issues == []


@pytest.mark.parametrize(("label", "claim", "source_value"), [
    ("Temperature", "90 °F", "37.5 °C"),
    ("Free memory", "942 MB", "756.39 MB"),
    ("CPU load (5 min)", "2.5 / 80%", "0.78 / 19.5%"),
    ("Database size", "499 MB", "175 MB"),
    ("Power", "100 W", "25 W"),
    ("Humidity", "80%", "54%"),
    ("Battery", "3%", "89%"),
])
def test_scalar_field_validation_is_source_agnostic(label, claim, source_value):
    facts = {
        **HUB, "temperature": 37.5, "temperature_unit": "°C",
        "power": 25, "power_unit": "W", "humidity": 54,
        "humidity_unit": "%", "battery": 89, "battery_unit": "%",
    }
    output, issues = guard_typed_status_claims(
        f"- **{label}:** {claim}", hub(facts)
    )
    assert claim not in output
    assert source_value in output
    assert issues


def test_missing_temperature_in_non_hub_device_is_corrected_too():
    source = device(values={"temperature": None, "temperature_unit": "°C"})
    out, issues = guard_typed_status_claims(
        "- **Temperature:** 22.2 °C", source
    )
    assert "22.2" not in out
    assert "not reported in the checked source" in out
    assert "temperature_not_reported" in issues


def test_device_resolution_per_entity_does_not_use_another_devices_level():
    a = device("Test Light A", "701", {"switch": "on", "level": 50})
    b = device("Test Light B", "702", {"switch": "off", "level": 60})
    text = "- **Test Light A:** on at 50%\n- **Test Light B:** off at 90%"
    out, issues = guard_typed_status_claims(text, [*a, *b])
    assert "**Test Light A**: on at 50%" in out
    assert "**Test Light B**: switch off, saved level 60%" in out
    assert "90%" not in out
    assert "device_state_source_mismatch" in issues


def test_ambiguous_multiple_sources_cannot_satisfy_unlabelled_metric():
    a = device("Test Sensor A", "701", {"temperature": 12.5})
    b = device("Test Sensor B", "702", {"temperature": 21.5})
    text = "Temperature: 80 °C"
    out, issues = guard_typed_status_claims(text, [*a, *b])
    assert out == text
    assert issues == []


def test_unit_only_does_not_attest_numeric_value_even_with_successful_read():
    out, issues = guard_typed_status_claims(
        "- Temperature: 42.5 °C",
        device(values={"temperature_unit": "°C"}),
    )
    assert "42.5" not in out
    assert issues == ["temperature_not_reported"]


def test_firmware_match_does_not_imply_external_update_freshness():
    out, issues = guard_typed_status_claims(
        "Hub firmware 2.5.3.117 is up to date.", hub()
    )
    assert "matches source-reported available version" in out
    assert "external update freshness unverified" in out
    assert issues == ["firmware_external_freshness_unverified"]


def test_other_source_reports_with_identical_semantics():
    report = {
        **HUB,
        "temperature": 24, "temperature_unit": "°C",
        "installed_firmware": "1.2.3",
        "available_firmware": "1.2.4",
    }
    other = hub(report)
    other[0]["details"]["sourceType"] = "typed_monitoring_snapshot_v1"
    out, issues = guard_typed_status_claims(
        "Firmware 1.2.3 is up to date.\n- Temperature: 88 °C", other
    )
    assert "1.2.4" in out
    assert "24 °C" in out
    assert len(issues) == 2


def test_snapshot_can_not_establish_absence_of_alerts():
    text = "The hub is healthy with no active alerts."
    for source in (hub(), hub({**HUB, "hub_alerts": "none"})):
        out, issues = guard_typed_status_claims(text, source)
        assert "is healthy with no active alerts" not in out
        assert "complete system health" in out
        assert issues


def test_failed_or_unscoped_receipts_cannot_silently_invent_source_checks():
    text = "The hub is healthy. Temperature: 42.5 °C"
    sources = [
        [], hub(success=False), hub(matched=False),
        [{**hub()[0], "mutates": True}],
        [{**hub()[0], "effect": "sensitive_write"}],
        [{**hub()[0], "supports_live_claim": False}],
        [{**hub()[0], "details": {"reported": HUB}}],
        device(success=False), device(source=False),
    ]
    for evidence in sources:
        out, issues = guard_typed_status_claims(text, evidence)
        assert (out, issues) == (text, [])


def test_never_echoes_raw_arguments_or_private_device_identity():
    source = hub()
    source[0]["arguments"] = {
        "token": "private-secret", "deviceId": "123456789"
    }
    out, issues = guard_typed_status_claims(
        "- Temperature: 66.7 °C\nThe hub is healthy.", source
    )
    assert "private-secret" not in out
    assert "123456789" not in out
    assert "66.7" not in out
    assert issues


def test_general_status_prompt_requires_actual_fields():
    prompt = build_system_prompt("", "")
    assert "missing/null measurement remains unverified" in prompt
    assert "missing hubAlerts field cannot establish" in prompt

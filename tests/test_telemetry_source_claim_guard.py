"""Q1 generic telemetry explanation attestation, synthetic sources only.

No Hubitat / HA / router calls. Original model answer remains the author,
but cannot promote uncertain physical or driver-method assertions to facts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai/rootfs/app"))

from telemetry_source_claim_guard import guard_telemetry_source_claims  # noqa: E402
from agent_prompt_policy import build_system_prompt  # noqa: E402


def receipt(name="Test MQTT Plug", device_id="701", *, last_seen="Mon Oct 12 01:30:01 BST 2026",
            data_age=162325, with_events=True):
    states = [
        {
            "tool": "hub_read_devices",
            "success": True, "mutates": False, "effect": "read",
            "supports_live_claim": False, "evidence_kind": "targeted_device_lookup",
            "details": {"reportedDeviceState": {
                "deviceId": device_id, "label": name,
                "observedAt": "2026-11-04T14:36:24+00:00",
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                    "lastSeen": last_seen, "dataAgeSeconds": data_age,
                },
                "source": "targeted-hubitat-device-state",
            }},
        },
        {
            "tool": "homebrain_resolve_device",
            "success": True, "mutates": False, "effect": "read",
            "supports_live_claim": True,
            "evidence_kind": "deterministic_targeted_device_resolution",
            "details": {"reportedDeviceState": {
                "deviceId": device_id, "label": name,
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                    "lastSeen": last_seen, "dataAgeSeconds": data_age,
                },
                "source": "verified-resolved-device-hubitat-state",
            }},
        },
    ]
    if with_events:
        states.append({
            "tool": "homebrain_device_history",
            "success": True, "mutates": False, "effect": "read",
            "supports_live_claim": True,
            "details": {"observedEvents": [
                {"name": "mqttStatus", "value": "disconnected",
                 "producedBy": {"id": device_id, "type": "device"}},
                {"name": "mqttStatus", "value": "connected",
                 "producedBy": {"id": device_id, "type": "device"}},
                {"name": "deviceHealth", "value": "unknown",
                 "producedBy": {"id": device_id, "type": "device"}},
            ]},
        })
    return states


def coverage(device_id="701", *, verified=False, root_cause=False):
    return {
        "domain": "device_telemetry",
        "rootCauseVerified": root_cause,
        "sourceAuthority": {
            "targetDeviceId": device_id,
            "verifiedInstalledDriverBehaviour": verified,
            "physicalCauseEstablished": root_cause,
            "independentBrokerPacketsVerified": root_cause,
        },
        "incidentReasoningDepth": {
            "driverMethodBehaviourVerified": verified,
            "rootCauseEstablishedByThisAssessment": root_cause,
        },
    }


LIVE_DRAFT = """The discrepancy is caused by the difference between a cached state and a live calculation.
**The Best-Supported Explanation**
The device is physically offline or stopped communicating. The mqttStatus of "connected" is a stale attribute; it represents the last known state and only changes if the hub receives a specific disconnect message. Because no such message was received, the hub continues to display the last known status.
In contrast, the healthStatus of "offline" is a live calculation performed by the hub's internal watchdog. This watchdog monitors incoming telemetry and marks the device offline when a timeout threshold is exceeded.
**Evidence Timeline**
- **October 12:** The lastSeen timestamp indicates the last time the device was definitively seen by the system.
- **~45 Hours Ago:** The dataAgeSeconds (162,325) suggests the last piece of actual telemetry was received approximately 45 hours ago.
- **Today:** Hub logs show a watchdog firing every 5 minutes after approximately 20 hours without data.
**Unresolved Limitations**
While the evidence confirms the device is not communicating, the physical root cause remains unproven. It is unknown if the device lost power or WiFi.
**Next Recommended Read-Only Discriminator**
Check the healthStatus and mqttStatus of other MQTT devices before attributing a root cause.
"""


def test_real_likely_telemetry_overclaims_do_not_survive_publication():
    output, issues = guard_telemetry_source_claims(
        LIVE_DRAFT, receipt(), coverage(),
    )
    assert "physically offline" not in output
    assert "definitively seen" not in output
    assert "last piece of actual telemetry" not in output
    assert "watchdog firing every 5 minutes" not in output
    assert "cached state and a live calculation" not in output
    assert "566.1 hours" in output
    assert "45.1 hours" in output
    assert "They disagree" in output
    assert "MQTT disconnect reports" in output
    assert "driver's status-update and watchdog implementation" in output
    assert "**Next Recommended Read-Only Discriminator**" in output
    assert "Check the healthStatus and mqttStatus of other MQTT devices" in output
    assert set(issues).issuperset({
        "telemetry_physical_claim_unverified",
        "telemetry_driver_claim_unverified",
        "telemetry_clock_claim_unverified",
    })


@pytest.mark.parametrize("not_target", [
    {"domain": "device_status"},
    {"domain": "device_telemetry", "sourceAuthority": {"targetDeviceId": "702"}},
    None,
])
def test_unrelated_scope_or_different_target_does_not_rewrite(not_target):
    original = "The device is physically offline."
    assert guard_telemetry_source_claims(
        original, receipt(), not_target
    ) == (original, [])


def test_reported_health_state_and_modest_explanation_remain_model_authored():
    answer = (
        "Hubitat reports healthStatus=offline and mqttStatus=connected. "
        "That difference does not establish the physical fault. "
        "An independent broker read could help."
    )
    assert guard_telemetry_source_claims(answer, receipt(), coverage()) == (
        answer, []
    )


def test_bounded_positive_disconnect_refutes_certain_no_disconnect():
    text = "No disconnect message was received."
    with_event, with_issue = guard_telemetry_source_claims(
        text, receipt(), coverage()
    )
    assert "contains an MQTT disconnect report" in with_event
    assert with_issue == ["telemetry_disconnect_claim_unverified"]
    without_event, without_issue = guard_telemetry_source_claims(
        text, receipt(with_events=False), coverage()
    )
    assert "cannot prove no MQTT disconnect" in without_event
    assert without_issue == ["telemetry_disconnect_claim_unverified"]


def test_conflicting_clock_does_not_certify_last_packet_even_when_other_sources_exist():
    text = "The lastSeen shows the last time the device was definitively seen."
    output, issues = guard_telemetry_source_claims(text, receipt(), coverage())
    assert "They disagree" in output
    assert "telemetry_clock_claim_unverified" in issues


def test_matching_clock_still_cannot_certify_physical_telemetry():
    text = "The lastSeen shows the last time the device was definitively seen."
    # 2026-11-04 14:36 read minus 12 Oct -> approximately 566h.
    seconds = 566 * 3600
    final, issues = guard_telemetry_source_claims(
        text, receipt(data_age=seconds), coverage()
    )
    assert "neither independently verifies the time" in final
    assert "telemetry_clock_claim_unverified" in issues


def test_verified_driver_method_does_not_trigger_driver_only_guard():
    text = "The watchdog marks a device offline after a timeout threshold."
    fixed, issues = guard_telemetry_source_claims(
        text, receipt(), coverage(verified=True),
    )
    assert fixed == text
    assert issues == []


def test_driver_method_unverified_has_no_dependency_on_specific_device_label():
    for name, ident in [
        ("Garage Plug", "701"), ("Thermostat Zone", "901"),
        ("Sensor 2", "881"),
    ]:
        out, issues = guard_telemetry_source_claims(
            "The watchdog triggers after 12 hours without data.",
            receipt(name, ident), coverage(ident),
        )
        assert "driver's status-update and watchdog implementation" in out
        assert issues == ["telemetry_driver_claim_unverified"]


def test_some_other_device_disconnect_event_cannot_be_misattributed():
    events = receipt(with_events=False)
    events.append({
        "tool": "homebrain_device_history",
        "success": True, "mutates": False, "effect": "read",
        "details": {"observedEvents": [{
            "name": "mqttStatus", "value": "disconnected",
            "producedBy": {"id": "702", "type": "device"},
        }]},
    })
    result, _ = guard_telemetry_source_claims(
        "No disconnect event was seen.", events, coverage()
    )
    assert "contains an MQTT disconnect report" not in result
    assert "cannot prove no MQTT disconnect" in result


def test_no_claim_assessment_from_errored_or_mutating_device_reads():
    evidence = receipt()
    for row in evidence:
        row["success"] = False
    original = "The device is physically offline."
    assert guard_telemetry_source_claims(original, evidence, coverage()) == (
        original, []
    )
    source = receipt()
    for row in source:
        row["mutates"] = True
    assert guard_telemetry_source_claims(original, source, coverage()) == (
        original, []
    )


def test_no_raw_logs_or_private_arguments_leak_into_correction():
    events = receipt()
    events[0]["arguments"] = {
        "token": "PRIVATE-HUBITAT-TOKEN", "url": "http://private-host"
    }
    out, issues = guard_telemetry_source_claims(
        "The device is physically offline.", events, coverage()
    )
    assert issues
    assert "PRIVATE-HUBITAT-TOKEN" not in out
    assert "private-host" not in out
    assert "701" not in out


def test_general_system_prompt_prohibits_source_semantic_inflation():
    sys_prompt = build_system_prompt("", "")
    assert "If lastSeen and dataAgeSeconds refer to incompatible clocks" in sys_prompt
    assert "Positive disconnect/reconnect" in sys_prompt
    assert "successfully queried log source" in sys_prompt

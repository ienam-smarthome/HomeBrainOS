"""General source-role + event-value publication regressions, synthetic devices."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from api_response_builder import build_agent_response
from causal_initiator_provenance_guard import guard_unverified_initiator_claims
from causal_sensor_value_guard import guard_focal_sensor_value_precision
from controller_correlation_guard import guard_controller_boundary_claim
from synthesis_validator import validate_synthesis
from test_causal_focal_source_proof_018449 import _evidence, FOCAL


def _source_packet():
    rows = _evidence()
    correlation = next(
        row for row in rows
        if row.get("tool") == "homebrain_causal_secondary_correlation"
    )
    correlation["details"]["sensors"] = [{
        "label": "Example Desk Occupancy", "attribute": "motion",
        "relevantCorrelations": [{
            "subjectTransition": FOCAL,
            "sensorEvent": "2026-11-07T00:29:40.936+00:00",
            "attribute": "motion", "eventValue": "inactive",
            "signedDeltaSeconds": -19.087,
        }],
    }]
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "mutates": False, "effect": "read",
        "supports_live_claim": True,
        "evidence_kind": "authoritative_device_event_history",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "9030", "attribute": "motion"}},
        "details": {
            "label": "Example Desk Occupancy", "deviceId": "9030",
            "attribute": "motion", "windowVerified": True,
            "events": [{
                "name": "motion", "value": "inactive", "type": "physical",
                "date": "2026-11-07T00:29:40.936+00:00",
            }],
        },
    })
    return rows


EXAMPLE_BAD = (
    'The exact initiator of the most recent "off" event for Example Lamp '
    'is unverified, as there is no record of a command being issued by '
    'Hubitat to trigger this transition.\n'
    '* **External Reporting:** Example Bridge reported the state change. '
    "This indicates the action occurred outside of Hubitat's control.\n"
    '* Several apps acted as listeners to the event rather than the triggers.\n'
    '* The desk motion sensor reported activity approximately 19 seconds '
    'before the OFF event; that is only a temporal correlation.\n'
)


def _outcome(text, evidence, request_class="live-read", confirmation=False):
    return SimpleNamespace(
        message=text, evidence=evidence, request_class=request_class,
        confirmation_required=confirmation, confirmation_count=int(confirmation),
        choices=[], automation_items=[],
        metrics={"outcome": "unresolved", "counters": {"model_rounds": 7}},
        investigation_coverage={
            "domain": "causal_provenance", "status": "partial-evidence",
            "rootCauseVerified": False,
        },
    )


def test_bridge_report_does_not_establish_external_action_origin():
    text = (
        "**External Reporting:** Example Bridge reported the state change. "
        "This indicates the action occurred outside of Hubitat's control."
    )
    fixed, changed = guard_unverified_initiator_claims(
        text, _source_packet(), "Why did Example Lamp turn off?",
    )
    assert changed
    assert "Example Bridge reported the state change." in fixed
    assert "occurred outside" not in fixed
    assert "does not identify the initiating controller" in fixed


def test_no_record_claim_is_bounded_not_global_absence():
    text = (
        "The exact initiator is unverified, as there is no record of a command "
        "being issued by Hubitat to trigger this transition."
    )
    fixed, changed = guard_unverified_initiator_claims(
        text, _source_packet(), "Why did Example Lamp turn off?",
    )
    assert changed
    assert "there is no record of a command being issued" not in fixed
    assert "in the queried command-event records" in fixed
    assert "cannot rule out" in fixed


def test_listener_subscription_is_not_automatic_negative_initiator_proof():
    raw = "Several apps acted as listeners to the event rather than the triggers."
    fixed, changed = guard_unverified_initiator_claims(
        raw, _source_packet(), "Why did Example Lamp turn off?",
    )
    assert changed
    assert "rather than the triggers" not in fixed
    assert "does not identify them as initiators" in fixed


def test_focal_sensor_state_is_source_verified_and_precise():
    text = "The desk motion sensor reported activity about 19 seconds before OFF."
    fixed, changed = guard_focal_sensor_value_precision(text, _source_packet())
    assert changed
    assert "reported motion=inactive" in fixed
    assert "19 seconds" in fixed
    assert "reported activity" not in fixed


def test_missing_native_window_or_other_sensor_is_not_converted():
    rows = _source_packet()
    text = "The desk motion sensor reported activity 19 seconds before OFF."
    for packet in (
        [r for r in rows if r.get("sub_tool") != "hub_list_device_events"],
        [dict(r, details=dict(r["details"], windowVerified=False))
         if r.get("sub_tool") == "hub_list_device_events" else r for r in rows],
    ):
        same, changed = guard_focal_sensor_value_precision(text, packet)
        assert not changed and same == text
    other = "The hallway sensor reported activity before the transition."
    same, changed = guard_focal_sensor_value_precision(other, rows)
    assert not changed and same == other


def test_wrong_boundary_sensor_sample_is_not_promoted_to_latest_off():
    rows = _source_packet()
    corr = next(r for r in rows if r.get("tool") == "homebrain_causal_secondary_correlation")
    corr["details"]["sensors"][0]["relevantCorrelations"][0]["subjectTransition"] = (
        "2026-11-06T20:53:25.948+00:00"
    )
    text = "The desk motion sensor reported activity 19 seconds before OFF."
    same, changed = guard_focal_sensor_value_precision(text, rows)
    assert not changed and same == text


def test_old_controller_alignment_does_not_create_unrelated_interval_repair():
    rows = _source_packet()
    subject = next(r for r in rows if r.get("tool") == "homebrain_device_history")
    subject["details"]["temporalAnalysis"]["observedIntervals"] = [{
        "start": "2026-11-06T15:13:18.213+00:00",
        "end": "2026-11-06T15:29:53.708+00:00",
        "startNatural": "3:13 pm on Friday 6 November 2026",
        "durationSeconds": 995,
    }]
    rows.append({
        "tool": "homebrain_device_history", "success": True,
        "details": {
            "label": "Example Controller", "attribute": "pushed",
            "observedEvents": [{
                "name": "pushed", "value": "2",
                "date": "2026-11-06T15:29:52.739+00:00",
            }],
        },
    })
    raw = (
        "The initiating controller remains unknown. The controller log shows "
        "no button activity at the focal transition."
    )
    unchanged, changed = guard_controller_boundary_claim(raw, rows)
    assert not changed and unchanged == raw
    # Without a verified focal OFF clock, legacy start-vs-end correction
    # remains available for a genuinely specified earlier turn-on.
    unscoped = [
        row for row in rows
        if row.get("tool") != "homebrain_causal_secondary_correlation"
    ]
    wrong = "The controller triggered the turn-on."
    repaired, changed = guard_controller_boundary_claim(wrong, unscoped)
    assert changed
    assert "interval end/turn-off boundary" in repaired


def test_full_api_repairs_source_roles_without_discarding_positive_evidence():
    rows = _source_packet()
    text = (
        "SenseCap Example issued an ON command at 20:58:15.\n"
        + EXAMPLE_BAD
        + "| Event | Time |\n| --- | --- |\n| OFF | 00:30:00 |\n"
    )
    result = build_agent_response(
        _outcome(text, rows), model="model", version="0.18.450",
        elapsed_ms=48000, submitted_question="Why did Example Lamp turn off?",
    )
    msg = result["message"]
    assert "SenseCap Example issued an ON command" in msg
    assert "occurred outside" not in msg
    assert "there is no record of a command being issued" not in msg
    assert "rather than the triggers" not in msg
    assert "reported motion=inactive" in msg
    assert "| OFF | 00:30:00 |" in msg
    assert result["evidence_validation"]["unverified_causal_origin_corrected"]
    assert result["evidence_validation"]["focal_sensor_value_corrected"]


def test_validator_and_write_confirmation_safety():
    packet = _source_packet()
    fixed, issues = validate_synthesis(
        EXAMPLE_BAD, packet,
        original_user="Why did Example Lamp turn off?", causal=True,
    )
    assert "causal_unverified_initiator" in issues
    assert "causal_focal_sensor_value_precision" in issues
    assert "reported motion=inactive" in fixed
    for kind, confirm in (("write", False), ("live-read", True)):
        result = build_agent_response(
            _outcome(EXAMPLE_BAD, packet, kind, confirm),
            model="model", version="0.18.450", elapsed_ms=100,
        )
        assert result["message"] == EXAMPLE_BAD
        assert "unverified_causal_origin_corrected" not in result["evidence_validation"]
        assert "focal_sensor_value_corrected" not in result["evidence_validation"]

"""Generic focal-event source-binding and causal publication regressions.

Only fictional source receipts; no live hub, provider or household data.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from api_response_builder import build_agent_response
from causal_attribution_guard import (
    _triggered_only_app_contexts,
    guard_triggered_listener_causal_claim,
)
from causal_claim_verification import (
    _scoped_question,
    guard_focal_sensor_state_claim,
)
from causal_initiator_provenance_guard import guard_unverified_initiator_claims


FOCAL = "2026-11-07T00:30:00.023+00:00"


def _packet() -> list[dict]:
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False, "effect": "read",
            "evidence_kind": "targeted_device_lookup",
            "details": {"reportedDeviceState": {
                "deviceId": "123", "label": "Example Light",
                "reportedAttributes": {"switch": "off"},
            }},
        },
        {
            "tool": "homebrain_device_history",
            "success": True, "supports_live_claim": True,
            "mutates": False, "effect": "read",
            "evidence_kind": "authoritative_device_event_history",
            "details": {
                "label": "Example Light", "attribute": "switch",
                "observedEvents": [
                    {"name": "switch", "value": "off",
                     "date": "2026-11-05T02:41:58.247+00:00",
                     "type": "physical",
                     "producedBy": {"label": "Example Bridge", "id": "900",
                                    "type": "device"},
                     "triggered": [{"name": "Old Monitor", "appId": 800}]},
                    {"name": "switch", "value": "off", "date": FOCAL,
                     "type": "physical",
                     "producedBy": {"label": "Example Bridge", "id": "900",
                                    "type": "device"},
                     "triggered": [{"name": "New Listener", "appId": 801}]},
                ],
                "boundaryEvents": [],
            },
        },
        {
            "tool": "homebrain_causal_secondary_correlation",
            "success": True, "effect": "read",
            "details": {
                "subject": "Example Light", "transition": "off",
                "requestedBoundary": "2026-11-07T00:30:00.023000+00:00",
                "sensors": [{"label": "Example Desk Sensor",
                             "relevantCorrelations": [{
                                 "boundaryRole": "end",
                                 "subjectTransition": FOCAL,
                                 "sensorEvent": "2026-11-07T00:29:40.936+00:00",
                                 "eventValue": "inactive",
                                 "signedDeltaSeconds": -19.087,
                             }]}],
            },
        },
    ]


def test_fallback_question_preserves_off_boundary_not_on():
    question = _scoped_question(_packet(), "")
    assert "Example Light turn off at 00:30:00" in question
    assert "turn on" not in question


def test_listener_context_binds_to_focal_event_not_old_history():
    contexts = _triggered_only_app_contexts(_packet())
    assert [row["appLabel"] for row in contexts] == ["New Listener"]
    draft = "Old Monitor caused the latest OFF. New Listener caused the latest OFF."
    fixed, changed = guard_triggered_listener_causal_claim(draft, _packet())
    assert changed
    assert "For this physical state event, New Listener" in fixed
    assert "For this physical state event, Old Monitor" not in fixed


def test_unqualified_generic_listener_cannot_be_replaced_by_arbitrary_app():
    draft = "An automation caused the latest OFF."
    assert guard_triggered_listener_causal_claim(draft, _packet()) == (draft, False)


def test_missing_focal_report_does_not_appropriate_older_listeners():
    packet = _packet()
    packet[1]["details"]["observedEvents"] = packet[1]["details"]["observedEvents"][:1]
    assert _triggered_only_app_contexts(packet) == []


def test_external_claim_not_excused_by_unverified_actor_in_following_clause():
    draft = (
        "The observed OFF was triggered externally to Hubitat, "
        "and the exact actor remains unverified."
    )
    graph = {
        "scope": "single-observed-event",
        "externalInitiatorVerified": False,
        "directCommand": None,
        "focus": {"subject": "Example Light", "off": FOCAL},
    }
    revised, changed = guard_unverified_initiator_claims(
        draft, _packet(), "Why did Example Light turn off?", graph=graph,
    )
    assert changed
    assert "triggered externally" not in revised
    assert "bounded evidence does not identify" in revised


def test_possible_external_action_remains_a_hypothesis():
    draft = "An external automation might have requested OFF; no initiator is verified."
    graph = {"scope": "single-observed-event",
             "externalInitiatorVerified": False, "directCommand": None}
    assert guard_unverified_initiator_claims(
        draft, _packet(), "Why did Example Light turn off?", graph=graph,
    ) == (draft, False)


def test_focal_sensor_inactive_is_not_described_as_activity():
    graph = {
        "scope": "single-observed-event",
        "offSensorCorrelations": [{
            "sensor": "Example Desk Sensor", "value": "inactive",
            "signedDeltaMs": -19087,
        }],
    }
    draft = "Example Desk Sensor reported activity 19 seconds before OFF."
    revised, changed = guard_focal_sensor_state_claim(
        draft, _packet(), "Why did Example Light turn off?", graph=graph,
    )
    assert changed
    assert "reported an inactive state" in revised
    assert "reported activity" not in revised
    other = "Another sensor reported activity 19 seconds before OFF."
    assert guard_focal_sensor_state_claim(
        other, _packet(), "Why?", graph=graph,
    ) == (other, False)


def test_final_api_rechecks_external_cause_after_model_repair():
    draft = (
        "The OFF transition was triggered externally to Hubitat, "
        "and the exact actor is unverified.\n\n"
        "Example Bridge reported the state at 00:30:00."
    )
    outcome = SimpleNamespace(
        message=draft, evidence=_packet(), request_class="live-read",
        choices=[], confirmation_required=False,
        investigation_coverage={"domain": "causal_provenance"},
        metrics={"outcome": "unresolved", "counters": {"model_rounds": 2}},
    )
    response = build_agent_response(
        outcome, submitted_question="Why did Example Light turn off?",
        model="fictional-model", elapsed_ms=33, version="test",
    )
    assert "triggered externally" not in response["message"]
    assert "00:30:00" in response["message"]
    assert response["evidence_validation"]["causal_initiator_claim_corrected"] is True
    assert response["outcome_presentation"]["value"] == "unresolved"


def test_causal_publisher_never_rewrites_pending_confirmations():
    draft = "The OFF transition was triggered externally to Hubitat."
    outcome = SimpleNamespace(
        message=draft, evidence=_packet(), request_class="write",
        choices=[], confirmation_required=True,
        investigation_coverage={"domain": "causal_provenance"},
        metrics={"outcome": "unresolved"},
    )
    response = build_agent_response(
        outcome, submitted_question="Why did Example Light turn off?",
        model="fictional-model", elapsed_ms=33, version="test",
    )
    assert "causal_initiator_claim_corrected" not in response["evidence_validation"]

"""Source-neutral focal event/source-role regression tests. Synthetic data only."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from api_response_builder import build_agent_response
from causal_attribution_guard import (
    _focal_physical_events,
    guard_triggered_listener_causal_claim,
)
from causal_claim_verification import _scoped_question
from causal_initiator_provenance_guard import guard_unverified_initiator_claims

FOCAL = "2026-11-07T00:30:00.023+00:00"
OLDER = "2026-11-05T02:41:58.247+00:00"


def _report(at, listeners):
    return {
        "name": "switch", "value": "off", "date": at,
        "type": "physical", "isStateChange": True,
        "producedBy": {"type": "device", "id": "7000", "label": "Example Bridge"},
        "triggered": [
            {"name": name, "appId": ident, "handler": "onEvent"}
            for name, ident in listeners
        ],
    }


def _evidence():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False, "effect": "read",
            "supports_live_claim": False,
            "evidence_kind": "targeted_device_lookup",
            "details": {"reportedDeviceState": {
                "deviceId": "9001", "label": "Example Lamp",
                "reportedAttributes": {"switch": "off"}
            }},
        },
        {
            "tool": "homebrain_device_history",
            "success": True, "mutates": False, "effect": "read",
            "supports_live_claim": True,
            "evidence_kind": "authoritative_device_event_history",
            "arguments": {"name": "Example Lamp"},
            "details": {
                "label": "Example Lamp", "attribute": "switch",
                "observedEvents": [
                    _report(FOCAL, [("Example Receiver", 502)]),
                    _report(OLDER, [("Example Monitor", 501)]),
                ],
                "boundaryEvents": [
                    _report(FOCAL, [("Example Receiver", 502)]),
                    _report(OLDER, [("Example Monitor", 501)]),
                ],
                "temporalAnalysis": {"intervalCount": 0},
                "sourceCoverageVerified": False,
            },
        },
        {
            "tool": "homebrain_causal_secondary_correlation",
            "success": True, "effect": "read", "mutates": False,
            "supports_live_claim": True,
            "details": {
                "subject": "Example Lamp", "transition": "off",
                "requestedBoundary": FOCAL,
            },
        },
    ]


def _outcome(message, *, request_class="live-read", confirmation_required=False):
    return SimpleNamespace(
        message=message, evidence=_evidence(),
        request_class=request_class, confirmation_required=confirmation_required,
        confirmation_count=1 if confirmation_required else 0,
        choices=[], automation_items=[],
        metrics={"outcome": "unresolved", "counters": {"model_rounds": 2}},
        investigation_coverage={
            "domain": "causal_provenance", "status": "partial-evidence",
            "rootCauseVerified": False,
        },
    )


def test_correlation_reconstructs_off_focus_not_a_fabricated_on_question():
    query = _scoped_question(_evidence(), "")
    assert "turn off at 00:30:00" in query
    assert "turn on" not in query


def test_focal_listener_selection_excludes_other_historical_boundaries():
    rows = _focal_physical_events(_evidence())
    assert len(rows) == 1
    assert rows[0]["date"] == FOCAL
    assert rows[0]["triggered"][0]["name"] == "Example Receiver"


def test_old_listener_cannot_be_attached_to_latest_state_event():
    draft = (
        "The initiating controller remains unverified. "
        "For this physical state event, Example Monitor is recorded only as "
        "a downstream listener in triggered[]; the event itself was produced "
        "by Example Bridge. This evidence does not establish that "
        "Example Monitor initiated the transition."
    )
    repaired, changed = guard_triggered_listener_causal_claim(draft, _evidence())
    assert changed
    assert "Example Monitor is recorded only as" not in repaired
    assert "another historical event" in repaired
    assert "initiating controller remains unverified" in repaired


def test_focal_listener_is_not_promoted_to_the_issuing_controller():
    draft = "Example Receiver triggered the Example Lamp OFF transition."
    repaired, changed = guard_triggered_listener_causal_claim(draft, _evidence())
    assert changed
    assert "Example Receiver is recorded only as a downstream listener" in repaired
    assert "Example Bridge" in repaired


def test_unqualified_external_assertion_is_not_rescued_by_later_uncertainty():
    draft = (
        "The most recent OFF transition was triggered externally to Hubitat, "
        "and the initiating actor remains unverified."
    )
    repaired, changed = guard_unverified_initiator_claims(
        draft, _evidence(), "Why did Example Lamp turn off?"
    )
    assert changed
    assert "was triggered externally" not in repaired
    assert "does not identify an initiating controller" in repaired


def test_final_serializer_guards_origin_command_denial_and_focal_listener():
    draft = (
        "The latest OFF transition was triggered externally to Hubitat, "
        "and the actor remains unverified.\n"
        "* **Command Analysis:** There is no recorded Hubitat command corresponding "
        "to this event. Hubitat recorded the state after it occurred; "
        "it did not issue the instruction to turn off.\n"
        "### Conclusion\n"
        "The initiator is unresolved. For this physical state event, "
        "Example Monitor is recorded only as a downstream listener in "
        "triggered[]; the event itself was produced by Example Bridge. "
        "This evidence does not establish that Example Monitor initiated it.\n"
        "| Time | Event |\n| --- | --- |\n| 00:30:00 | OFF |\n"
    )
    result = build_agent_response(
        _outcome(draft), model="gemma4:31b", elapsed_ms=200,
        version="0.18.449",
        submitted_question="Why did Example Lamp turn off most recently?",
    )
    message = result["message"]
    assert "was triggered externally" not in message
    assert "it did not issue the instruction" not in message
    assert "Example Monitor is recorded only as" not in message
    assert "No matching direct Hubitat command producer" in message
    assert "| 00:30:00 | OFF |" in message
    assert result["evidence_validation"]["unverified_causal_origin_corrected"]
    assert result["evidence_validation"]["focal_listener_scope_corrected"]
    assert result["outcome_presentation"]["value"] == "unresolved"


def test_no_focal_clock_cannot_choose_arbitrary_old_listener():
    data = [row for row in _evidence() if row["tool"] != "homebrain_causal_secondary_correlation"]
    message = "Example Monitor triggered Example Lamp OFF."
    corrected, changed = guard_triggered_listener_causal_claim(message, data)
    assert not changed
    assert corrected == message


def test_write_or_confirmation_bypasses_new_causal_publication_checks():
    draft = "The OFF transition was triggered externally to Hubitat."
    for request_class, needs_confirmation in (("write", False), ("live-read", True)):
        result = build_agent_response(
            _outcome(
                draft, request_class=request_class,
                confirmation_required=needs_confirmation,
            ),
            model="gemma4:31b", elapsed_ms=200, version="0.18.449",
            submitted_question="Why did Example Lamp turn off?",
        )
        assert result["message"] == draft
        assert "unverified_causal_origin_corrected" not in result["evidence_validation"]
        assert "focal_listener_scope_corrected" not in result["evidence_validation"]

"""Cross-domain provenance contracts for model-directed investigations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_initiator_provenance_guard import (
    build_state_report_provenance, render_state_report_provenance,
    guard_unverified_initiator_claims,
)
from investigation_checkpoint import build_evidence_checkpoint


def _history(name="Zone A Light", state="on", app="3001"):
    return {
        "success": True, "mutates": False,
        "tool": "homebrain_device_history",
        "evidence_kind": "deterministic_device_event_history",
        "details": {
            "label": name, "observedEvents": [{
                "name": "switch", "value": state,
                "date": "2026-10-30T14:50:37Z", "type": "physical",
                "producedBy": {"label": "Matter Bridge", "id": "900", "type": "device"},
                "triggered": [{"name": "Lighting Controller", "appId": app}],
            }],
        },
    }


def test_multiple_device_state_reports_never_prove_upstream_initiator():
    evidence = [_history(), _history("Zone B Light")]
    context = build_state_report_provenance(evidence)
    assert context["state_report_count"] == 2
    assert context["reporting_devices"] == ["Matter Bridge"]
    assert context["downstream_listener_app_ids"] == ["3001"]
    assert context["upstream_initiator_established"] is False
    assert "not who" in render_state_report_provenance(evidence)


def test_multi_device_external_conclusion_is_softened_without_proven_issuer():
    evidence = [_history(), _history("Zone B Light")]
    original = (
        "**Best-Supported Explanation:** The lights were toggled via physical "
        "interaction or an external controller.\n"
        "**Conclusion:** The lights were operated externally to Hubitat.\n"
    )
    fixed, changed = guard_unverified_initiator_claims(
        original, evidence, "Why did both lights change state?"
    )
    assert changed
    assert "not identify an initiating controller" in fixed
    assert "operated externally to Hubitat" not in fixed
    assert "**Conclusion:**" in fixed


def test_unchecked_command_history_does_not_become_global_denial():
    evidence = [_history("Heating Relay"), _history("Boiler Switch")]
    fixed, changed = guard_unverified_initiator_claims(
        "No Hubitat-initiated commands preceded these transitions.",
        evidence, "Why did the heating turn off?"
    )
    assert changed
    assert "cannot rule out unobserved command paths" in fixed


def test_provisional_qualification_and_source_timeline_are_preserved():
    evidence = [_history(), _history("Zone B Light")]
    message = (
        "An external controller is possible, but not verified.\n"
        "| 14:50 | Zone A Light | ON | Matter Bridge |\n"
    )
    fixed, changed = guard_unverified_initiator_claims(
        message, evidence, "Investigate the state changes"
    )
    assert not changed
    assert fixed == message


def test_unrelated_conversation_has_no_provenance_rewrite():
    message = "An external controller probably caused the change."
    fixed, changed = guard_unverified_initiator_claims(
        message, [], "Can you explain the integration?"
    )
    assert not changed and fixed == message


def test_checkpoint_promotes_missing_link_to_model_selected_reads():
    packet = build_evidence_checkpoint(
        "Determine why two devices toggled",
        [_history(), _history("Zone B Light")],
        available_read_tools=("hub_read_devices", "hub_read_apps_code"),
    )
    assert packet["state_report_provenance"]["state_report_count"] == 2
    assert any("independently logged command" in question
               for question in packet["next_unchecked_discriminators"])
    assert packet["source_success_is_not_causal_proof"] is True


def test_failures_and_mutations_cannot_establish_reporter_provenance():
    failed = _history()
    failed["success"] = False
    mutation = _history()
    mutation["mutates"] = True
    context = build_state_report_provenance([failed, mutation])
    assert context["state_report_count"] == 0

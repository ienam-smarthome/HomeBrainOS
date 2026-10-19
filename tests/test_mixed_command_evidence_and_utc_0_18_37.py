"""v0.18.37: positive mixed command evidence, UTC window and causal restraint."""
from __future__ import annotations

import sys
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from general_evidence_completion import assess_task_source_coverage
from historical_command_source_contract import (
    requested_event_boundary, history_window_instruction,
    mixed_command_events, focused_command_observation,
    incident_log_window_coverage, calibrate_command_causality,
)
from shared_investigation_completion import apply_shared_investigation_completion
from api_response_builder import build_agent_response


QUESTION = (
    "Investigate the Bedroom 3 Mesh OFF event on 12 October 2026 at "
    "approximately 01:30 BST. Compare possible command issuers, retrieve "
    "relevant original evidence, identify contradictions and explain what "
    "remains unverified. Read-only."
)


def receipt(op: str, args: dict, details=None, *, success=True) -> dict:
    return {
        "tool": ("hub_read_diagnostics" if op == "hub_get_logs" else "hub_read_devices"),
        "sub_tool": op, "arguments": {"tool": op, "args": args},
        "effect": "read", "mutates": False, "success": success,
        "details": details or {},
    }


def live_read(rows=None, log_since="2026-10-12T01:20:00Z",
              log_until="2026-10-12T01:40:00Z"):
    if rows is None:
        rows = [{
            "name": "healthStatus", "value": "offline",
            "date": "2026-10-12T01:33:46.925+0100",
            "producedBy": {"name": "Bedroom 3 Mesh", "deviceId": "7103"},
        }, {
            "name": "switch", "value": "off", "date": "2026-10-12T01:30:01.914+0100",
            "producedBy": {"name": "Bedroom 3 Mesh", "deviceId": "7103"},
            "triggered": [{"appId": 4129, "name": "SenseCap D1 Settings"}],
        }, {
            "name": "command-off", "type": "command", "value": None,
            "description": "Command called: off()",
            "date": "2026-10-12T01:30:01.743+0100",
            "producedBy": {"name": "Power saving: Bedroom 3 Mesh off @night", "appId": 3950},
        }]
    return [
        receipt("hub_list_device_events", {
            "deviceId": "7103", "since": "2026-10-12T00:00:00Z",
            "until": "2026-10-12T01:00:00Z",
        }, {"observedEvents": rows, "observedEventsTruncated": True}),
        receipt("hub_get_logs", {
            "appId": "3950", "since": log_since, "until": log_until,
        }, {"logCount": 0, "logs": []}),
    ]


def test_local_incident_boundary_utc_conversion_and_dst_rejection():
    instant = requested_event_boundary(QUESTION)
    assert instant.isoformat() == "2026-10-12T01:30:00+01:00"
    assert instant.astimezone(timezone.utc).isoformat() == "2026-10-12T00:30:00+00:00"
    directive = history_window_instruction(QUESTION)
    assert "2026-10-12T00:30:00Z" in directive
    assert "2026-10-12T00:20:00Z" in directive
    assert "2026-10-12T00:40:00Z" in directive
    assert requested_event_boundary(QUESTION.replace("BST", "GMT")) is None
    assert requested_event_boundary("At 01:30 last Monday") is None
    assert requested_event_boundary("12 October 2026 01:30 BST") is not None


def test_mixed_target_scoped_history_with_real_command_counts_as_both_sources():
    evidence = live_read()
    assert len(mixed_command_events(evidence[0])) == 1
    coverage = assess_task_source_coverage(
        ("device_history", "command_history"), evidence,
    )
    assert coverage.sources_checked
    assert coverage.checked == ("device_history", "command_history")


def test_empty_invalid_and_wrong_source_do_not_fabricate_command_coverage():
    for events in ([], [
        {"name": "switch", "value": "off", "date": "2026-10-12T01:30:01+0100"},
    ], [
        {"name": "command-off", "type": "command", "date": "not a date"},
    ], [
        {"name": "command-off", "type": "device", "date": "2026-10-12T01:30:01+0100"},
    ]):
        row = live_read(events)[0]
        assert mixed_command_events(row) == []
        coverage = assess_task_source_coverage(("command_history",), [row])
        assert coverage.missing == ("command_history",)
    forged = live_read()[0]
    forged["success"] = False
    assert mixed_command_events(forged) == []
    write_receipt = live_read()[0]
    write_receipt["effect"] = "write"
    assert mixed_command_events(write_receipt) == []


def test_recorded_app_issuer_is_not_a_physical_or_upstream_verdict():
    fact = focused_command_observation(QUESTION, live_read())
    assert fact is not None
    assert fact["deviceId"] == "7103"
    assert fact["recordedIssuerAppId"] == "3950"
    assert fact["commandRecorded"] is True
    assert fact["deliveryVerified"] is False
    assert fact["physicalActuationVerified"] is False
    assert fact["upstreamTriggerVerified"] is False
    assert focused_command_observation(QUESTION.replace("OFF event", "ON event"), live_read()) is None
    assert focused_command_observation(QUESTION.replace("12 October", "13 October"), live_read()) is None
    assert focused_command_observation(QUESTION.replace("Mesh OFF", "Mesh (device 9999) OFF"), live_read()) is None


def test_competing_app_issuers_do_not_create_false_unique_provenance():
    rows = live_read()[0]["details"]["observedEvents"]
    duplicate = dict(rows[-1])
    duplicate["producedBy"] = {"appId": 9999, "name": "Other app"}
    rows.append(duplicate)
    assert focused_command_observation(QUESTION, live_read(rows)) is None


def test_log_window_mismatch_detected_without_claiming_log_absence():
    result = incident_log_window_coverage(QUESTION, live_read(), app_id="3950")
    assert result is not None
    assert result["correctTimeWindowChecked"] is False
    assert result["requestedEventUTC"] == "2026-10-12T00:30:00+00:00"
    correct = incident_log_window_coverage(
        QUESTION, live_read(log_since="2026-10-12T00:20:00Z",
                            log_until="2026-10-12T00:40:00Z"),
        app_id="3950",
    )
    assert correct["correctTimeWindowChecked"] is True
    assert incident_log_window_coverage(QUESTION, live_read(), app_id="9999") is None


def test_overconfident_model_physical_exclusion_and_ack_are_calibrated():
    source = live_read()
    fact = focused_command_observation(QUESTION, source)
    window = incident_log_window_coverage(QUESTION, source, app_id="3950")
    draft = (
        "The evidence establishes that this was an automated action rather "
        "than a physical or external interaction.\n"
        "* **Physical Interaction (Contradicted):** A person did not press it.\n"
        "* **External/Cloud Integration (Unsupported):** No external interaction occurred.\n"
        "The device responded to this command within approximately 171ms.\n"
        "A targeted log read for App 3950 returned no entries for the window surrounding the event."
    )
    text, issues = calibrate_command_causality(draft, fact, window)
    assert "Physical interaction (not independently verified)" in text
    assert "External integration (not independently verified)" in text
    assert "physical acknowledgement was not independently verified" in text
    assert "recorded Hubitat command issuer" in text
    assert "did not cover the requested event time" in text
    assert set(issues) == {"upstream_or_physical_overclaim", "misaligned_app_log_claim"}
    assert "This verifies the recorded" in text


def test_shared_finalizer_has_command_history_checked_and_time_warning():
    evidence = live_read()
    draft = (
        "The Bedroom 3 Mesh was turned OFF at 01:30 BST. "
        "The evidence establishes that this was an automated action rather "
        "than a physical or external interaction. "
        "The device responded to this command within approximately 171ms."
    )
    original = SimpleNamespace(
        message=draft, route="unified-mcp-agent", request_class="live-read",
        evidence=evidence, investigation_coverage=None, choices=[],
        confirmation_required=False, confirmation_count=0, automation_items=[],
        metrics={"outcome": "unresolved", "counters": {"model_rounds": 7}, "timings_ms": {}},
    )
    result = apply_shared_investigation_completion(original, QUESTION)
    cov = result.investigation_coverage
    assert "command_history" in cov["sourceCoverage"]["checkedSourceKinds"]
    assert cov["sourceCoverage"]["missingSourceKinds"] == []
    assert cov["recordedCommandProvenance"]["recordedIssuerAppId"] == "3950"
    assert cov["causalInitiatorVerified"] is None
    assert cov["rootCauseVerified"] is False
    assert cov["incidentAppLogWindow"]["correctTimeWindowChecked"] is False
    assert result.metrics["outcome"] == "unresolved"
    assert "unchecked source classes: command_history" not in result.message
    assert "command-off" in result.message
    assert "did not cover" in result.message
    api = build_agent_response(
        result, model="gemma4:31b", elapsed_ms=43887, version="0.18.37",
    )
    assert api["investigation_coverage"]["recordedCommandProvenance"]["commandRecorded"]
    assert api["model_tier_requested"] if "model_tier_requested" in api else True


def test_source_class_and_app_log_check_do_not_prove_execution():
    no_producer = live_read([{
        "name": "switch", "value": "off",
        "date": "2026-10-12T01:30:01.914+0100",
        "producedBy": {"deviceId": "7103", "name": "Bedroom 3 Mesh"},
    }])
    assert focused_command_observation(QUESTION, no_producer) is None
    assert assess_task_source_coverage(("command_history",), no_producer).missing

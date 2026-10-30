"""Model-directed cross-source discovery and causal completion regressions.

These tests use arbitrary target labels/IDs. The host must never supply a
sensor ID or a new operation: only the live model tool catalog may do that.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from investigation_evidence_cycle import cross_source_discovery_checkpoint
from unified_investigation_bridge import (
    collect_unified_evidence, unified_investigation_followup,
)
from request_outcome_policy import classify_completed_request

QUESTION = (
    "Investigate why Zone Alpha Light and Zone Beta Light changed state "
    "on 30 October 2026 between 14:50 and 15:30 GMT"
)


def lookup(ident, label):
    return {
        "success": True, "mutates": False, "effect": "read",
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "evidence_kind": "targeted_device_lookup",
        "arguments": {"tool": "hub_list_devices",
                      "args": {"labelFilter": label}},
        "details": {"reportedDeviceState": {
            "deviceId": str(ident), "label": label,
            "reportedAttributes": {"switch": "off"}}},
    }


def level(ident, app="3001"):
    return {
        "success": True, "mutates": False, "effect": "read",
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "supports_live_claim": True,
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": str(ident),
                               "since": "2026-10-30T14:50:00Z",
                               "until": "2026-10-30T15:30:00Z"}},
        "details": {"observedEvents": [
            {"name": "command-setLevel", "date": "2026-10-30T14:50:39.100Z",
             "type": "command", "value": None,
             "producedBy": {"appId": app}},
            {"name": "level", "date": "2026-10-30T14:50:40.100Z",
             "type": "physical", "value": "60",
             "producedBy": {"deviceId": "900"}},
        ]},
    }


def journal(ident, *, with_source=True):
    source = [{
        "device_id": str(ident), "attribute": "switch", "value": "on",
        "date": "2026-10-30T14:50:37.000+00:00",
        "timestamp_basis": "source",
    }] if with_source else []
    return {
        "success": True, "mutates": False, "effect": "read",
        "tool": "homebrain_evidence_journal",
        "evidence_kind": "group_archived_switch_history",
        "arguments": {"device_id": str(ident),
                      "since": "2026-10-30T14:50:00+00:00",
                      "until": "2026-10-30T15:30:00+00:00"},
        "details": {"observations": [*source, {
            "device_id": str(ident), "attribute": "switch", "value": "on",
            "date": "2026-10-30T14:50:38.500+00:00",
            "timestamp_basis": "collector-received",
        }], "gapCount": 2, "coverageComplete": False},
    }


def receipts(with_journal=True):
    rows = [lookup(101, "Zone Alpha Light"), lookup(102, "Zone Beta Light"),
            level(101), level(102)]
    if with_journal:
        rows += [journal(101), journal(102)]
    return rows


def test_no_recovered_source_no_model_discovery_claim():
    assert cross_source_discovery_checkpoint(receipts(False), QUESTION) is None


def test_journal_source_becomes_model_visible_before_answer():
    prompt = cross_source_discovery_checkpoint(receipts(), QUESTION)
    assert prompt is not None
    assert "historicalJournalSourceTimeReports" in prompt
    assert '"sourceTimedOn":1' in prompt
    assert "independent" in prompt
    assert "sourceContinuityEstablished" in prompt
    assert '"upstreamInitiatorEstablished":false' in prompt
    assert "Choose only available, authorized READ tools" in prompt
    assert "do not invent sensor IDs" in prompt.lower() or "Do not invent sensor IDs" in prompt


def test_journal_does_not_satisfy_unchecked_independent_input_history():
    rows = receipts()
    facts = collect_unified_evidence(rows, QUESTION)
    assert facts is not None
    assert facts["journal_source_observations"] == 2
    assert facts["missing_independent_input_history"] is True
    assert facts["missing_switch_history_for_targets"] == [
        "Zone Alpha Light", "Zone Beta Light",
    ]
    next_read = unified_investigation_followup(rows, QUESTION)
    assert next_read
    assert "independent input" in next_read
    assert "NO reported switch" not in next_read
    assert "controller" in next_read.lower()


def test_collector_only_does_not_enable_source_driven_followup():
    rows = receipts(False) + [journal(101, with_source=False),
                             journal(102, with_source=False)]
    assert cross_source_discovery_checkpoint(rows, QUESTION) is None
    next_read = unified_investigation_followup(rows, QUESTION)
    assert "NO reported switch" in next_read


def test_input_history_followup_advances_to_controller_without_fixed_id():
    rows = receipts()
    rows.extend([
        lookup(201, "Door Motion"),
        {"success": True, "mutates": False, "effect": "read",
         "supports_live_claim": True,
         "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": "201",
                                "since": "2026-10-30T14:50:00Z"}},
         "details": {"observedEvents": [{
             "name": "motion", "value": "active",
             "date": "2026-10-30T14:50:36Z",
             "producedBy": {"deviceId": "201"}}]}},
    ])
    next_read = unified_investigation_followup(rows, QUESTION)
    assert next_read
    assert "CAUSAL CHAIN INCOMPLETE" in next_read
    assert "controller dependencies" in next_read
    assert "proof of external control" in next_read


def test_metrics_distinguish_successful_reads_from_unresolved_causal_question():
    assert classify_completed_request({"model_rounds": 5,
                                       "tool_calls": 16}) == "success"
    assert classify_completed_request({"model_rounds": 5, "tool_calls": 16,
                                       "causal_initiator_unresolved": 1}) == "unresolved"
    assert classify_completed_request({"causal_initiator_unresolved": 1,
                                       "mutation_verification_failures": 1}) == "failed"


def test_historical_checkpoint_not_triggered_without_scoped_target_data():
    assert cross_source_discovery_checkpoint([], QUESTION) is None
    assert cross_source_discovery_checkpoint([journal(101)], QUESTION) is None

"""Source-neutral deterministic floor regression for failed causal repairs."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import sys
from copy import deepcopy

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from causal_verified_fallback import verified_failed_repair_answer
from api_response_builder import build_agent_response

OFF = "2026-11-07T00:30:00.023+00:00"
ON = "2026-11-06T20:58:15.909+00:00"
QUESTION = ("Why did Example Lamp turn off most recently? "
            "Investigate using all available evidence. Do not change anything.")


def _packet():
    def event(when, value):
        return {
            "name": "switch", "value": value, "date": when,
            "isStateChange": True, "type": "physical",
            "producedBy": {
                "id": "800", "label": "Example Bridge", "type": "device"
            },
        }

    return [
        {"tool": "hub_read_devices", "success": True, "mutates": False,
         "evidence_kind": "targeted_device_lookup",
         "details": {"reportedDeviceState": {
             "deviceId": "9000", "label": "Example Lamp",
             "reportedAttributes": {"switch": "off"},
         }}},
        {"tool": "homebrain_device_history", "success": True,
         "mutates": False, "evidence_kind": "authoritative_device_event_history",
         "details": {"label": "Example Lamp", "attribute": "switch",
                     "boundaryEvents": [event(OFF, "off"), event(ON, "on")]}},
        {"tool": "homebrain_causal_secondary_correlation",
         "success": True, "mutates": False,
         "evidence_kind": "deterministic_causal_secondary_correlation",
         "details": {
             "subject": "Example Lamp", "transition": "off",
             "requestedBoundary": OFF,
             "historicalJournal": {"sensors": [{
                 "deviceId": "8001", "label": "Desk Sensor", "attribute": "motion",
                 "events": [{
                     "observedAt": "2026-11-07T00:29:41.617+00:00",
                     "value": "inactive", "timestampBasis": "collector-received",
                 }],
             }]},
         }},
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "mutates": False,
         "evidence_kind": "authoritative_device_event_history",
         "arguments": {"args": {
             "deviceId": "8001", "attribute": "motion",
             "since": "2026-11-07T00:25:00+00:00",
             "until": "2026-11-07T00:32:00+00:00",
         }},
         "details": {"label": "Desk Sensor", "deviceId": "8001",
                     "attribute": "motion", "windowVerified": True,
                     "events": [], "eventCount": 0,
                     "sourceHistoryComplete": False}},
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "mutates": False,
         "evidence_kind": "authoritative_command_event_history",
         "arguments": {"args": {
             "deviceId": "9000", "attribute": "command-off",
             "hoursBack": 168, "limit": 20,
         }},
         "details": {"eventName": "command-off", "eventCount": 1,
                     "events": [{
                         "name": "command-off",
                         "date": "2026-11-06T20:53:25.307+00:00",
                         "type": "command",
                         "producedBy": {
                             "label": "Example Button App", "id": "900",
                             "type": "app",
                         },
                     }]}},
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "mutates": False, "effect": "read",
         "arguments": {"args": {
             "appId": 250, "mode": "past",
             "since": "2026-11-06T15:13:08+00:00",
             "until": "2026-11-06T15:13:28+00:00",
         }},
         "details": {"nativePastLog": {
             "matchedRowsReported": 0, "returnedPageCount": 0
         }}},
    ]


def _outcome(evidence, counters=None, kind="live-read", confirm=False):
    return SimpleNamespace(
        message=("The Desk Sensor reported inactive 19 seconds before OFF. "
                 "Example App logs showed zero messages around the OFF time. "
                 "This suggests it came from outside the Hubitat system."),
        evidence=evidence, request_class=kind,
        confirmation_required=confirm, confirmation_count=1 if confirm else 0,
        choices=[], automation_items=[],
        metrics={"outcome": "unresolved",
                 "counters": counters if counters is not None else
                 {"synthesis_repair_failed": 1, "model_rounds": 7}},
        investigation_coverage={
            "domain": "causal_provenance", "rootCauseVerified": False,
            "status": "partial-evidence",
        },
    )


def test_factual_floor_rejects_unverified_sensor_clock_and_unrelated_logs():
    answer = verified_failed_repair_answer(_packet(), original_question=QUESTION)
    assert answer and "Example Lamp reported OFF" in answer
    assert "Example Bridge reported the state" in answer
    assert "3h 31m 44s" in answer
    assert "returned 1 records" in answer
    assert "no verified matching focal command" in answer
    assert "Desk Sensor motion=inactive" in answer
    assert "collector reception time" in answer
    assert "0 sensor-event rows" in answer
    assert "other times, not the focal OFF instant" in answer
    assert "19 seconds" not in answer
    assert "suggests it came from outside" not in answer
    assert "zero messages around" not in answer


def test_main_serializer_uses_floor_when_failed_repair_and_is_read_only():
    result = build_agent_response(
        _outcome(_packet()), model="example-model",
        elapsed_ms=34000, version="0.18.452",
        submitted_question=QUESTION,
    )
    assert result["success"] is True
    assert result["request_class"] == "live-read"
    assert result["evidence_validation"]["claim_validated_factual_floor"] == (
        "synthesis_repair_failed"
    )
    assert "19 seconds" not in result["message"]
    assert "initiating controller remains unverified" in result["message"]


def test_no_floor_when_repair_succeeds_or_scope_is_write_or_confirmation():
    for outcome in (
        _outcome(_packet(), counters={"synthesis_repair_failed": 0}),
        _outcome(_packet(), kind="write"),
        _outcome(_packet(), kind="live-read", confirm=True),
    ):
        answer = build_agent_response(
            outcome, model="example-model", elapsed_ms=1,
            version="0.18.452", submitted_question=QUESTION,
        )
        assert "claim_validated_factual_floor" not in answer["evidence_validation"]


def test_no_floor_without_unique_valid_focal_source_boundary():
    rows = _packet()
    for packet in (
        [r for r in rows if r.get("tool") != "homebrain_device_history"],
        [r for r in rows if r.get("tool") != "homebrain_causal_secondary_correlation"],
        [dict(r, details=dict(r["details"], requestedBoundary="2026-11-06T20:53:25+00:00"))
         if r.get("tool") == "homebrain_causal_secondary_correlation"
         else r for r in rows],
        [dict(r, success=False) if r.get("tool") == "homebrain_device_history"
         else r for r in rows],
    ):
        assert verified_failed_repair_answer(
            packet, original_question=QUESTION
        ) is None
    assert verified_failed_repair_answer(
        rows, original_question="Why did Example Lamp turn on?"
    ) is None


def test_source_timed_sensor_event_may_be_reported_but_not_inferred_causal():
    rows = _packet()
    native = rows[3]
    native["details"]["events"] = [{
        "name": "motion", "value": "inactive",
        "date": "2026-11-07T00:29:40.936+00:00",
    }]
    native["details"]["eventCount"] = 1
    answer = verified_failed_repair_answer(rows, original_question=QUESTION)
    assert "Source-timed sensor observations" in answer
    assert "Desk Sensor motion=inactive" in answer
    assert "00:29:40" in answer
    assert "Timing alone is not proof of a trigger" in answer
    native["details"]["windowVerified"] = False
    answer = verified_failed_repair_answer(rows, original_question=QUESTION)
    assert "Source-timed sensor observations" not in answer


def test_focal_command_positive_not_discarded_or_conflated_with_root_cause():
    rows = _packet()
    commands = rows[4]["details"]["events"]
    commands.append({
        "name": "command-off", "date": "2026-11-07T00:29:59.750+00:00",
        "type": "command",
        "producedBy": {"id": "901", "type": "app",
                       "label": "Example Timer App"},
    })
    rows[4]["details"]["eventCount"] = 2
    answer = verified_failed_repair_answer(rows, original_question=QUESTION)
    assert "issued by Example Timer App" in answer
    assert "underlying reason remains unverified" in answer
    assert "no verified matching focal command" not in answer


def test_false_or_unverified_reporter_prevents_publication():
    rows = _packet()
    rows[1]["details"]["boundaryEvents"][0]["producedBy"] = None
    assert verified_failed_repair_answer(rows, original_question=QUESTION) is None


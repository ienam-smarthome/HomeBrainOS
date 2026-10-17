"""v0.18.20: source text was collected, but model synthesis can still fail."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from source_analysis_completion import (
    source_analysis_failed, source_failure_summary,
    source_trace_ready_for_synthesis,
)
from shared_investigation_completion import apply_shared_investigation_completion
from api_response_builder import build_agent_response


REQUEST = (
    "Independently investigate Bedroom 3 Mesh device 7103. "
    "Retrieve the complete Groovy source of its actual driver, verify code ID "
    "3686, trace mqttStatus, lastSeen, dataAgeSeconds, deviceHealth, watchdog "
    "and command acknowledgements. Correlate device events and logs. Read-only."
)
FAILURE = (
    "I found Hubitat tools relevant to this request, but I could not "
    "produce a valid structured action. No command was sent."
)


def record(operation, args, *, details=None, success=True, effect="read"):
    row = {
        "tool": (
            "hub_read_apps_code" if operation == "hub_get_source"
            else "hub_read_diagnostics" if operation == "hub_get_logs"
            else "hub_read_devices"
        ),
        "sub_tool": operation, "arguments": {"tool": operation, "args": args},
        "success": success, "mutates": effect == "write", "effect": effect,
    }
    if details is not None:
        row["details"] = details
    return row


def complete_receipts():
    return [
        record("hub_get_device", {"deviceId": "7103", "mode": "configuration"}),
        record("hub_get_source", {"id": "3686", "type": "driver"}, details={
            "sourceRetrieved": True, "offset": 0, "chunkLength": 20531,
            "totalLength": 20531, "sourceCodeId": "3686",
        }),
        record("hub_list_device_events", {"deviceId": "7103", "hoursBack": 24}),
        record("hub_get_logs", {"deviceId": "7103", "since": "24h"}),
    ]


def outcome(message, receipts):
    return SimpleNamespace(
        request_class="live-read", route="unified-mcp-agent",
        message=message, evidence=receipts,
        metrics={"outcome":"success","counters":{},"timings_ms":{},
                 "model_round_details":[{"model":"deepseek-v4-pro",
                                          "provider":"ollama-cloud"}]},
        investigation_coverage=None,
    )


def test_completed_source_device_logs_and_history_stop_exploratory_reads():
    assert source_trace_ready_for_synthesis(REQUEST, complete_receipts())


def test_full_source_alone_does_not_claim_device_correlation_complete():
    rows = complete_receipts()
    for missing in range(4):
        partial = rows[:missing] + rows[missing + 1:]
        assert not source_trace_ready_for_synthesis(REQUEST, partial)
    assert not source_trace_ready_for_synthesis(
        "Read full Groovy source for installed app 4019.",
        complete_receipts(),
    )


def test_failed_or_mutating_receipts_cannot_close_source_trace():
    rows = complete_receipts()
    rows[2]["success"] = False
    assert not source_trace_ready_for_synthesis(REQUEST, rows)
    rows = complete_receipts()
    rows[3]["mutates"] = True
    assert not source_trace_ready_for_synthesis(REQUEST, rows)


def test_gapped_source_never_meets_sufficiency_checkpoint():
    rows = complete_receipts()
    rows[1]["details"]["chunkLength"] = 8000
    rows.append(record("hub_get_source", {"id": "3686", "type": "driver",
                                          "offset": 9000},
                       details={"sourceRetrieved": True, "offset": 9000,
                                "chunkLength": 11531, "totalLength": 20531,
                                "sourceCodeId": "3686"}))
    assert not source_trace_ready_for_synthesis(REQUEST, rows)


def test_generic_action_failure_is_not_reported_as_successful_source_answer():
    answer = apply_shared_investigation_completion(
        outcome(FAILURE, complete_receipts()), REQUEST,
    )
    coverage = answer.investigation_coverage
    assert coverage["fullImplementationVerified"] is True
    assert coverage["evidenceComplete"] is True  # retrieval only
    assert coverage["objectiveSatisfied"] is False
    assert coverage["analysisAnswerVerified"] is False
    assert coverage["methodBodyCoverage"]["status"] == "not-certified-by-source-span-receipts"
    assert answer.metrics["outcome"] == "unresolved"
    assert "analysis was not produced" in answer.message
    assert "source code ID 3686" in answer.message
    assert "20,531" not in answer.message  # do not imply word count
    assert "20531-offset-unit coverage" in answer.message
    assert "No device command was sent as part of this read-only" in answer.message
    api = build_agent_response(
        answer, model="deepseek-v4-pro", elapsed_ms=146918,
        version="0.18.20",
    )
    assert api["success"] is False
    assert api["metrics"]["outcome"] == "unresolved"
    assert api["model_usage"]["paid_rounds"] == 1
    assert api["outcome_presentation"]["value"] == "unresolved"


def test_normal_supported_source_answer_is_not_replaced():
    text = (
        "The observed Groovy getter reads a persisted duration setting; "
        "full historical runtime execution remains unverified."
    )
    answer = apply_shared_investigation_completion(
        outcome(text, complete_receipts()), REQUEST,
    )
    assert answer.investigation_coverage["analysisAnswerVerified"] is True
    assert answer.investigation_coverage["objectiveSatisfied"] is True
    assert answer.message == text
    assert build_agent_response(
        answer, model="deepseek-v4-pro", elapsed_ms=500,
        version="0.18.20",
    )["success"] is True


def test_no_source_recovery_does_not_invent_implementation_coverage():
    rows = complete_receipts()
    rows[1]["success"] = False
    recovered = apply_shared_investigation_completion(outcome(FAILURE, rows), REQUEST)
    assert recovered.investigation_coverage["fullImplementationVerified"] is False
    assert recovered.investigation_coverage["objectiveSatisfied"] is False
    assert "Only partial or unverified Groovy source" in recovered.message


def test_generic_structured_action_failure_detection_is_narrow():
    assert source_analysis_failed(FAILURE)
    assert source_analysis_failed("")
    assert not source_analysis_failed(
        "Source analysis: one command was not queued because its guard "
        "did not produce a valid structured action group; current driver "
        "implementation was independently reviewed. " + "Evidence " * 200
    )
    assert not source_analysis_failed(
        "The driver function processes a status packet and updates its "
        "stored MQTT connection state; hardware status is still unverified."
    )


def test_no_source_recovery_note_exposes_no_raw_code():
    text = source_failure_summary(complete_receipts())
    assert "Groovy source was retrieved" in text
    assert "mqttStatus" not in text

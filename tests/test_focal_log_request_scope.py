"""Native default past mode and focal scope, without private live payloads."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai/rootfs/app"))
from native_past_log_receipt import past_log_request_scope, summarize_past_log_requests
from claim_evidence_adapter import assess_evidence_shadow
from causal_coverage_claim_guard import guard_focal_log_coverage_claims
from method_command_source_contract import pending_command_app_decision_log
from synthesis_validator import validate_synthesis
from api_response_builder import build_agent_response
from test_claim_evidence_shadow_history_only import _actual_shape, _outcome, QUESTION

FOCAL = "2026-11-07T00:30:00.023Z"


def log_read(since="2026-11-07T00:25:00Z", until=None, **args):
    request = {"limit": 100, **args}
    if since is not None:
        request["since"] = since
    if until is not None:
        request["until"] = until
    return {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True, "mutates": False, "effect": "read",
            "arguments": {"tool": "hub_get_logs", "args": request},
            "details": {"nativePastLog": {
                "returnedRowsInspected": 100, "matchedRowsReported": 15000,
                "completeHistoricalCoverageVerified": False}}}


def receipts():
    rows = [row for row in _actual_shape() if row.get("sub_tool") != "hub_get_logs"]
    rows.extend([
        log_read("2026-11-06T23:50:00Z"),
        log_read("2026-11-06T23:55:00Z"),
        log_read(),
        log_read("2026-11-06T21:20:03Z", "2026-11-06T21:40:03Z", appId="123"),
    ])
    return rows


def test_default_past_mode_counts_all_reads_without_inventing_focal_coverage():
    scope = summarize_past_log_requests(receipts(), FOCAL)
    assert scope == {
        "past_log_requests": 4, "bounded_log_requests": 1,
        "unbounded_or_invalid_window_requests": 3,
        "app_scoped_log_requests": 1,
        "bounded_log_requests_covering_focal": 0,
        "bounded_app_log_requests_covering_focal": 0,
        "historical_completeness_verified": False,
        "returned_focal_event_absence_verified": False,
    }
    shadow = assess_evidence_shadow(receipts(), original_question=QUESTION)
    assert shadow["app_log_requests"] == 4
    assert shadow["app_log_requests_covering_focal"] == 0
    assert shadow["log_request_coverage"] == scope
    assert shadow["model_claims_assessed"] is False


def test_pairing_sample_includes_unpaired_raw_off_omitted_from_boundary_projection():
    from copy import deepcopy
    rows = receipts()
    history = next(row for row in rows if row.get("tool") == "homebrain_device_history")
    all_states = deepcopy(history["details"]["boundaryEvents"])
    history["details"]["observedEvents"] = all_states
    history["details"]["boundaryEvents"] = all_states[:-1]
    shadow = assess_evidence_shadow(rows, original_question=QUESTION)
    assert shadow["reported_off_count"] == 6
    assert shadow["returned_command_pairing"]["matching_recorded_commands"] == 2
    assert shadow["returned_command_pairing"]["unmatched_in_returned_records"] == 4
    assert shadow["log_request_coverage"]["past_log_requests"] == 4


@pytest.mark.parametrize("mode", [None, "past"])
def test_default_and_explicit_past_accept_offset_aware_bounded_requests(mode):
    args = {} if mode is None else {"mode": mode}
    row = log_read("2026-11-07T01:25:00+01:00", "2026-11-07T01:35:00+01:00",
                   appId="123", **args)
    scope = summarize_past_log_requests([row], FOCAL)
    assert scope["bounded_app_log_requests_covering_focal"] == 1
    assert scope["returned_focal_event_absence_verified"] is False


@pytest.mark.parametrize("changes", [
    {"success": False}, {"mutates": True}, {"effect": "write"},
    {"sub_tool": "hub_get_events"}, {"arguments": []},
])
def test_failed_mutating_wrong_tool_or_malformed_request_is_not_a_past_read(changes):
    row = log_read()
    row.update(changes)
    assert past_log_request_scope(row) is None


@pytest.mark.parametrize("mode", ["live", "hubEvents", "invalid", None])
def test_explicit_nonpast_or_null_mode_cannot_be_inferred_from_text(mode):
    assert past_log_request_scope(log_read(mode=mode)) is None


@pytest.mark.parametrize("since,until", [
    ("2026-11-07T00:25:00", "2026-11-07T00:35:00Z"),
    ("2026-11-07T00:35:00Z", "2026-11-07T00:25:00Z"),
    ("invalid", "2026-11-07T00:35:00Z"),
    (None, "2026-11-07T00:35:00Z"),
])
def test_invalid_or_one_sided_bounds_remain_reads_but_not_focal_coverage(since, until):
    scope = summarize_past_log_requests([log_read(since, until)], FOCAL)
    assert scope["past_log_requests"] == 1
    assert scope["bounded_log_requests_covering_focal"] == 0


def test_general_focal_request_is_not_app_execution_coverage_or_absence_proof():
    row = log_read(until="2026-11-07T00:35:00Z")
    scope = summarize_past_log_requests([row], FOCAL)
    assert scope["bounded_log_requests_covering_focal"] == 1
    assert scope["bounded_app_log_requests_covering_focal"] == 0
    row["details"]["nativePastLog"]["timeFilterUnparseable"] = 1
    assert summarize_past_log_requests([row], FOCAL)["bounded_log_requests"] == 0


def test_scope_summary_never_copies_messages_ids_or_private_fields():
    row = log_read(appId="123", secret="SECRET-ARG")
    row["details"]["nativePastLog"]["message"] = "SECRET-LOG"
    import json
    encoded = json.dumps(summarize_past_log_requests([row], FOCAL))
    assert "SECRET-" not in encoded and "123" not in encoded


def test_final_api_corrects_focal_log_absence_with_unchanged_receipts_and_rounds():
    rows = receipts()
    outcome = _outcome(rows)
    outcome.message = (
        "The specific trigger remains unknown as no corresponding event was "
        "captured in the hub's logs or command history for that window.\n"
        "| OFF | 00:30 | Example Bridge |\n"
        "The bridge reported OFF; the initiating controller remains unverified."
    )
    result = build_agent_response(outcome, model="test", elapsed_ms=1,
                                  version="0.18.456", submitted_question=QUESTION)
    assert result["evidence_validation"]["focal_log_coverage_corrected"] is True
    assert "no corresponding event was captured" not in result["message"]
    assert "Open-ended samples" in result["message"]
    assert "| OFF | 00:30 | Example Bridge |" in result["message"]
    assert result["evidence"] == rows
    assert result["metrics"]["counters"]["model_rounds"] == 7


def test_guard_preserves_positive_scoped_empty_results_and_uncertainty():
    message = ("The old app-log query returned zero entries.\n"
               "Logs contain messages from the bridge.\n"
               "Empty logs do not prove no automation executed.\n")
    assert guard_focal_log_coverage_claims(message, receipts(), QUESTION) == (message, False)


def test_synthesis_checks_focal_scope_before_model_repair():
    corrected, issues = validate_synthesis(
        "No corresponding event was captured in the hub logs for that window.",
        receipts(), original_user=QUESTION, causal=True,
    )
    assert "causal_focal_log_coverage" in issues
    assert "no corresponding event was captured" not in corrected.lower()


def test_unqualified_hub_command_absence_is_bounded_at_api_publication():
    outcome = _outcome(receipts())
    outcome.message = (
        "There is no recorded command issued by the hub to trigger this transition."
    )
    result = build_agent_response(outcome, model="test", elapsed_ms=1,
                                  version="0.18.456", submitted_question=QUESTION)
    assert "queried command-event records" in result["message"]
    assert "cannot rule out" in result["message"].lower()


def test_bounded_request_cannot_be_promoted_to_complete_historical_absence():
    rows = receipts() + [log_read(until="2026-11-07T00:35:00Z", appId="123")]
    text, changed = guard_focal_log_coverage_claims(
        "No automation execution was recorded in the logs around the event.", rows, QUESTION)
    assert changed and "historical completeness" in text
    sample = "The focal app-log query returned zero matching entries."
    assert guard_focal_log_coverage_claims(sample, rows, QUESTION) == (sample, False)


def test_unrelated_question_and_write_confirmation_paths_are_untouched():
    message = "No corresponding event was captured in the logs for that window."
    assert guard_focal_log_coverage_claims(message, receipts(), "What is the brightness?") == (message, False)
    for kind, confirm in (("write", False), ("confirmation", False), ("live-read", True)):
        outcome = _outcome(receipts(), request_class=kind, confirm=confirm)
        outcome.message = message
        result = build_agent_response(outcome, model="test", elapsed_ms=1,
                                      version="0.18.456", submitted_question=QUESTION)
        assert "focal_log_coverage_corrected" not in result["evidence_validation"]


def test_nonfocal_method_command_cannot_schedule_unrelated_app_decision_read():
    rows = receipts()
    history = next(row for row in rows if row.get("tool") == "homebrain_device_history")
    history["arguments"] = {"name": "Example Lamp"}
    history["details"]["observedEvents"] = [{
        "name": "command-setLevel", "type": "command",
        "date": "2026-11-06T21:30:03Z",
        "producedBy": {"type": "app", "id": "123", "label": "Example Rule"},
    }]
    assert pending_command_app_decision_log(QUESTION, rows) is None
    history["details"]["observedEvents"] = [{
        "name": "command-off", "type": "command", "date": FOCAL,
        "producedBy": {"type": "app", "id": "456", "label": "Example Rule"},
    }]
    query = pending_command_app_decision_log(QUESTION, rows)
    assert query is not None and query["args"]["appId"] == "456"
    assert query["args"]["since"].startswith("2026-11-07T00:20:")


@pytest.mark.parametrize("subject", ["Example Lamp", "Example Fan", "Example Heater"])
def test_whole_answer_cannot_mix_actor_uncertainty_with_definite_external_origin(subject):
    import json
    rows = json.loads(json.dumps(receipts()).replace("Example Lamp", subject))
    rows = [row for row in rows if row.get("sub_tool") != "hub_get_logs"]
    rows.append(log_read("2026-11-06T23:50:00Z", "2026-11-07T00:40:00Z"))
    rows.append({
        "tool": "homebrain_location_events", "success": True,
        "mutates": False, "effect": "read",
        "evidence_kind": "authoritative_location_event_history",
        "details": {"observedEvents": [
            {"name": "mode", "value": "Night", "date": "2026-11-06T23:00:03Z"},
            {"name": "mode", "value": "Late Night", "date": "2026-11-07T00:45:01Z"},
        ]},
    })
    question = QUESTION.replace("Example Lamp", subject)
    outcome = _outcome(rows)
    outcome.message = (
        "The bridge reported OFF at 00:30 GMT.\n"
        "| OFF | 00:30 GMT | 12,704s | Example Bridge |\n"
        "The hub reported Night mode before the transition.\n\n"
        "The specific initiator remains unverified because the action happened "
        "outside of Hubitat's control. The most likely candidates are:\n"
        "1. A physical switch or remote.\n"
        "2. A bridge-native schedule.\n"
        "3. An external integration.\n\n"
        "No automation execution was recorded in the logs around the event."
    )
    result = build_agent_response(outcome, model="test", elapsed_ms=1,
                                  version="0.18.458", submitted_question=question)
    message = result["message"]
    assert "outside of Hubitat's control" not in message
    assert "most likely candidates" not in message
    assert "unranked, unverified possibilities" in message
    assert "\n1." not in message and "\n2." not in message
    assert "A bounded general log request included the focal time" in message
    assert "Open-ended samples" not in message and "queries for other times" not in message
    assert "| OFF | 00:30 GMT | 12,704s | Example Bridge |" in message
    assert "The hub reported Night mode before the transition." in message
    assert result["evidence"] == rows
    assert result["evidence_validation"]["claim_evidence_shadow"]["model_claims_assessed"] is False


@pytest.mark.parametrize("joiner", [". ", "; ", " because ", " although ", " but "])
def test_independent_external_assertion_cannot_borrow_uncertainty_from_another_clause(joiner):
    from causal_initiator_provenance_guard import guard_unverified_initiator_claims
    text = "The actor is unverified" + joiner + "the action occurred outside Hubitat control."
    revised, changed = guard_unverified_initiator_claims(text, receipts(), QUESTION)
    assert changed and "occurred outside" not in revised


def test_ranked_candidate_heading_scopes_following_list_without_external_keyword():
    from causal_initiator_provenance_guard import guard_unverified_initiator_claims
    text = "The most likely causes are:\n1. A remote.\n2. A timer.\n\nReported OFF at 00:30."
    revised, changed = guard_unverified_initiator_claims(text, receipts(), QUESTION)
    assert changed and "most likely" not in revised
    assert "unranked, unverified possibilities" in revised
    assert "- A remote." in revised and "- A timer." in revised
    assert revised.endswith("Reported OFF at 00:30.")


def test_actual_general_focal_query_is_not_called_open_ended_or_misaligned():
    rows = [row for row in receipts() if row.get("sub_tool") != "hub_get_logs"]
    rows.append(log_read(until="2026-11-07T00:35:00Z"))
    text = "No app execution was captured in the logs around the OFF event."
    revised, changed = guard_focal_log_coverage_claims(text, rows, QUESTION)
    assert changed and "bounded general log request" in revised
    assert "App-specific execution coverage" in revised
    assert "Open-ended" not in revised and "other times" not in revised


def test_no_log_request_correction_does_not_invent_executed_samples():
    rows = [row for row in receipts() if row.get("sub_tool") != "hub_get_logs"]
    revised, changed = guard_focal_log_coverage_claims(
        "No event was captured in logs around the transition.", rows, QUESTION)
    assert changed and "No bounded request" in revised
    assert "Open-ended" not in revised and "other times" not in revised


def test_whole_answer_repair_is_used_by_synthesis_as_well_as_api():
    revised, issues = validate_synthesis(
        "The actor is unverified because the event happened outside Hubitat control. "
        "The most likely causes are:\n1. A remote.\n2. A timer.",
        receipts(), original_user=QUESTION, causal=True)
    assert "causal_unverified_initiator" in issues
    assert "happened outside" not in revised and "most likely" not in revised

"""Stage 7.1: negative claim scope and causal-question coverage regression.

Mocks and constructed fixtures only. Never infer global absence from missing
source records; never use an author's claimed citation type to certify prose.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import _CASES, _audit  # noqa: E402
from stage7_review_packet import build_review_packet  # noqa: E402
from stage71_evidence_scope import build_evidence_scope_review  # noqa: E402
from webui import render_page  # noqa: E402


def draft(text="No physical confirmation is recorded in these examined sources."):
    return {
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [{
            "text": text,
            "kind": "absence_proven",
            "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "off"}],
        }],
        "uncertainties": ["Execution is not independently established"],
        "next_evidence": "Check an independent actuator acknowledgement",
    }


def test_scoped_negative_claim_not_equated_with_global_nonexistence():
    c = _CASES["competing_commands"]
    report = build_evidence_scope_review(c, ["S1", "S2", "S3"])
    examined = report["model_examined_records"]
    complete = report["all_supplied_fictional_records"]
    assert len(examined["positive_confirmation_records"]) == 0
    assert {p["record_id"] for p in examined["records_marked_not_physically_acknowledged"]} == {
        "E1", "E2", "E3",
    }
    assert examined["explicit_coverage_gap_records"] == [{"source_id": "S3", "record_id": "E3"}]
    assert examined["reported_state_record_ids"] == ["I1"]
    assert set(examined["command_or_app_decision_record_ids"]) == {"E1", "E2"}
    assert examined["complete_history_proven"] is False
    assert examined["absence_outside_this_view_proven"] is False
    assert examined["unique_command_to_physical_outcome_link_proven"] is False
    assert complete["complete_history_proven"] is False
    assert report["negative_claim_scope"]["global_absence_proven"] is False
    assert report["negative_claim_scope"]["physical_nonexecution_proven"] is False
    assert report["causal_link_proven"] is False
    assert report["publisher_approval"] is False


def test_skipped_acknowledgement_cannot_be_treated_as_disproved_just_unread():
    c = _CASES["competing_commands"]
    report = build_evidence_scope_review(c, ["S1", "S2"])
    assert report["model_skipped_source_ids"] == ["S3", "S4", "S5"]
    assert report["model_examined_records"]["explicit_coverage_gap_records"] == []
    assert report["all_supplied_fictional_records"]["explicit_coverage_gap_records"] == [
        {"source_id": "S3", "record_id": "E3"}
    ]
    assert "not all events" in report["negative_claim_scope"]["reviewer_visible"]


def test_unread_positive_receipt_is_visible_to_reviewer_not_model():
    c = _CASES["competing_commands"]
    c = {**c, "catalog": [
        {**src, "records": [
            {**r, "physical_acknowledgement": True}
            if src["id"] == "S3" else r
            for r in src["records"]]}
        for src in c["catalog"]
    ]}
    report = build_evidence_scope_review(c, ["S1", "S2"])
    assert report["model_examined_records"]["positive_confirmation_records"] == []
    assert report["all_supplied_fictional_records"]["positive_confirmation_records"] == [
        {"source_id": "S3", "record_id": "E3"}
    ]
    assert report["causal_link_proven"] is False  # independent receipt ≠ unique cause
    assert report["negative_claim_scope"]["global_absence_proven"] is False


def test_negative_prose_remains_unproven_regardless_of_correct_source_atom():
    c = _CASES["competing_commands"]
    for words in (
        "No physical confirmation is recorded in the examined sources.",
        "Physical confirmation does not exist anywhere.",
        "Neither command ever physically executed.",
    ):
        answer = draft(words)
        legacy_audit = _audit(c, ["S1", "S2", "S3"], answer)
        assert legacy_audit["source_value_atoms_verified"] == 1
        assert legacy_audit["high_risk_unsupported_sentences"] == 1
        assert legacy_audit["prose_semantics_fully_verified"] is False
        packet = build_review_packet("competing_commands", c, ["S1", "S2", "S3"], answer)
        assert packet["author_sentences"][0]["text"] == words
        assert packet["author_sentences"][0]["human_factual_verdict"] == "not_reviewed"
        assert "overstates_global_absence" in packet["reviewer_rubric"]["negative_claim_scope"]
        assert packet["prose_fully_verified"] is False


@pytest.mark.parametrize("scenario", ["clock_conflict", "competing_commands", "stale_connectivity"])
def test_generic_question_obligations_not_hardcoded_room_or_device(scenario):
    c = _CASES[scenario]
    report = build_evidence_scope_review(c, [])
    ids = [x["id"] for x in report["review_questions"]]
    assert ids == [
        "reported_observations", "recorded_actions",
        "causal_attribution", "physical_and_negative_scope",
    ]
    assert all(row["human_answer_coverage"] == "not_reviewed"
               for row in report["review_questions"])
    assert len(report["model_skipped_source_ids"]) == 5
    assert report["model_examined_records"]["sources_examined"] == ["INITIAL"]
    assert report["all_supplied_fictional_records"]["sources_examined"] == [
        "INITIAL", "S1", "S2", "S3", "S4", "S5",
    ]
    assert report["scope_review_requires_independent_human"] is True
    assert not report["full_prose_semantics_certified"]


@pytest.mark.parametrize("selected", [["S9"], ["S1", "S1"], ["S1"] * 4])
def test_invalid_or_duplicate_model_selections_fail_closed(selected):
    with pytest.raises(ValueError):
        build_evidence_scope_review(_CASES["competing_commands"], selected)


def test_stage7_reviewer_packet_excludes_gold_labels_and_sensitive_data():
    original = _CASES["competing_commands"]
    case = {**original, "initial": {**original["initial"],
                                    "private_token": "NEVER-LEAK"}}
    pkt = build_review_packet("competing_commands", case, ["S1", "S2"], draft())
    contents = json.dumps(pkt)
    assert "NEVER-LEAK" not in contents
    assert "gold_sources" not in contents
    assert "required_types" not in contents
    assert pkt["evidence_scope_review"]["model_skipped_source_ids"] == [
        "S3", "S4", "S5",
    ]
    assert pkt["reviewer_rubric"]["question_coverage"] == [
        "addressed", "omitted", "unverifiable", "unclear",
    ]
    assert pkt["publisher_approval"] is False


def test_review_packet_still_uses_one_digest_of_bounded_original_records():
    c = _CASES["competing_commands"]
    first = build_review_packet("competing_commands", c, ["S2", "S1"], draft())
    again = build_review_packet("competing_commands", c, ["S2", "S1"], draft())
    assert first == again
    assert len(first["review_packet_id"]) == 16
    assert first["independent_human_review_required"] is True
    assert len(json.dumps(first)) < 32000


def test_phone_manual_scope_controls_require_actual_review_not_default_success():
    html = render_page("HomeBrainOS", "0.18.303")
    for expected in (
        "Stage 7.1 · Evidence scope and causal-question coverage",
        "Physical acknowledgements in examined sources",
        "A missing acknowledgement does not prove physical nonexecution.",
        "Negative/absence claim scope",
        "Question coverage ",
        "overstates_global_absence",
        "reviewer_negative_scope",
        "question_coverage:questionControls.map",
        "scopeElement.value!=='not_reviewed'",
        "production_publication_approval:false",
    ):
        assert expected in html


def test_production_publisher_and_agent_have_no_stage71_dependencies():
    for file in (
        "mcp_agent_orchestrator.py", "tool_executor.py",
        "causal_claim_publication.py", "final_answer_coordinator.py",
    ):
        assert "stage71_evidence_scope" not in (APP / file).read_text()

"""Stage 7.2 independent question-to-answer obligations and causal scope.

All source and model inputs are fictional. No paid Ollama calls, real device
reads, production publisher, or human ratings auto-approved in these tests.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import (  # noqa: E402
    _CASES, Stage6Benchmark, _audit,
)
from stage72_answer_coverage import build_answer_coverage_review  # noqa: E402
from stage7_review_packet import build_review_packet  # noqa: E402
from webui import render_page  # noqa: E402


def _draft(text="The fictional hall light was reported off.",
           kind="state_report", ids=None, atoms=None):
    return {
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [{
            "text": text, "kind": kind, "evidence_ids": ids or ["I1"],
            "atoms": atoms if atoms is not None else [
                {"record_id": "I1", "field": "state", "value": "off"},
            ],
        }],
        "uncertainties": ["Independent physical outcome is not verified"],
        "next_evidence": "Check the separate actuator acknowledgement history",
    }


@pytest.mark.parametrize("case", [
    "clock_conflict", "competing_commands", "stale_connectivity",
])
def test_independent_question_rubric_is_postrun_review_not_model_confirmation(case):
    fixture = _CASES[case]
    draft = _draft()
    review = build_answer_coverage_review(case, fixture, ["S1", "S2", "S3"], draft)
    assert review["schema"] == "homebrain-stage72-answer-coverage.v1"
    assert review["original_question"] == fixture["question"]
    assert len(review["obligations"]) >= 3
    assert all(row["reviewer_verdict"] == "not_reviewed"
               for row in review["obligations"])
    assert any(row["id"] == "causal_answer" for row in review["obligations"])
    assert all(row["source_overlap_is_not_prose_support"]
               for row in review["obligations"])
    assert review["reference_rubric_not_sent_to_model"] is True
    assert review["answer_directness_verified_automatically"] is False
    assert review["full_sentence_semantics_verified_automatically"] is False
    assert review["publisher_approval"] is False
    assert "gold_sources" not in json.dumps(review)
    assert "required_types" not in json.dumps(review)
    assert "api_key" not in json.dumps(review)


def test_case_covered_source_values_can_still_omit_causal_answer():
    fixture = _CASES["competing_commands"]
    draft = {
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [
            {"text": "The Inactivity App issued the off command.",
             "kind": "command_record", "evidence_ids": ["E1"],
             "atoms": [{"record_id": "E1", "field": "command", "value": "off"}]},
            {"text": "The Button App issued a brightness command.",
             "kind": "command_record", "evidence_ids": ["E2"],
             "atoms": [{"record_id": "E2", "field": "command", "value": "setLevel"}]},
            {"text": "Two distinct application commands were recorded.",
             "kind": "competing_commands", "evidence_ids": ["E1", "E2"],
             "atoms": []},
            {"text": "The light was reported off by the collector.",
             "kind": "state_report", "evidence_ids": ["I1"],
             "atoms": [{"record_id": "I1", "field": "state", "value": "off"}]},
        ],
        "uncertainties": ["Physical state is not independently verified"],
        "next_evidence": "Obtain an independent actuator acknowledgement",
    }
    checks = _audit(fixture, ["S1", "S2", "S3"], draft)
    assert checks["expected_finding_type_coverage"] == "3/3"
    assert checks["unsupported_typed_sentence_citations"] == 0
    assert checks["source_value_atoms_mismatched"] == 0
    review = build_answer_coverage_review(
        "competing_commands", fixture, ["S1", "S2", "S3"], draft)
    cause = next(row for row in review["obligations"]
                 if row["id"] == "causal_answer")
    assert set(cause["reference_records_available_to_model"]) == {
        "I1", "E1", "E2", "E3",
    }
    assert set(cause["reference_records_cited_by_model"]) == {
        "I1", "E1", "E2",
    }
    # Even with 3/3 typed finding coverage, the original "which app
    # caused OFF" question still requires human semantic evaluation.
    assert cause["reviewer_verdict"] == "not_reviewed"
    assert review["answer_directness_verified_automatically"] is False


def test_unread_relevant_source_not_auto_used_for_answer_credit():
    fixture = _CASES["competing_commands"]
    review = build_answer_coverage_review(
        "competing_commands", fixture, ["S1", "S2"], _draft())
    causal = next(x for x in review["obligations"]
                  if x["id"] == "causal_answer")
    assert causal["reference_records_not_examined_by_model"] == ["E3"]
    assert "E3" not in causal["reference_records_cited_by_model"]
    assert review["publisher_approval"] is False
    assert review["reference_evidence_revealed_only_postrun"] is True


def test_global_absence_and_scoped_unknown_get_same_reference_review_no_auto_truth():
    fixture = _CASES["competing_commands"]
    negative = _draft(
        "Neither command physically executed, and no acknowledgement exists anywhere.")
    scoped = _draft(
        "The available records do not verify the physical outcome of either command.")
    reviews = [build_answer_coverage_review(
        "competing_commands", fixture, ["S1", "S2", "S3"], d)
        for d in (negative, scoped)]
    assert reviews[0]["obligations"] == reviews[1]["obligations"]
    # The model's authored sentence semantics must be judged independently;
    # the evidence overlap cannot promote universal negative to truth.
    assert all(r["full_sentence_semantics_verified_automatically"] is False
               for r in reviews)


@pytest.mark.parametrize("choices", [["S999"], ["S1", "S1"], ["S1"] * 4])
def test_unknown_duplicate_or_excessive_choices_fail_closed(choices):
    with pytest.raises(ValueError):
        build_answer_coverage_review(
            "competing_commands", _CASES["competing_commands"], choices, _draft())


def test_unfounded_oracle_ids_or_citations_cannot_be_injected_into_review():
    fake = _draft()
    fake["sentences"][0]["evidence_ids"] = ["E5"]
    with pytest.raises(ValueError, match="unseen"):
        build_answer_coverage_review(
            "competing_commands", _CASES["competing_commands"],
            ["S1", "S2", "S3"], fake)
    with pytest.raises(ValueError, match="unknown"):
        build_answer_coverage_review(
            "not_a_case", _CASES["competing_commands"], ["S1"], _draft())


def test_stage7_packet_includes_host_reference_rubric_only_after_model_answer():
    fixture = _CASES["clock_conflict"]
    draft = _draft("The fictional lamp was reported on.")
    packet = build_review_packet("clock_conflict", fixture, ["S2", "S3"], draft)
    rubric = packet["answer_coverage_review"]
    assert rubric["original_question"] == fixture["question"]
    command = next(x for x in rubric["obligations"]
                   if x["id"] == "command_history")
    assert command["reference_records_not_examined_by_model"] == ["E1"]
    assert packet["unread_sources_only_disclosed_after_model_finished"]
    assert packet["publisher_approval"] is False
    assert packet["prose_fully_verified"] is False
    assert len(json.dumps(packet)) < 32000


class SyntheticCloud:
    def __init__(self):
        self.api_key = "mock-credential-never-displayed"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == [] and kwargs["disable_thinking"]
        serialized = json.dumps(messages)
        assert "independent_reviewer_question" not in serialized
        assert "reference_evidence_record_ids" not in serialized
        assert "reference_records_not_examined_by_model" not in serialized
        assert "Answer obligation " not in serialized
        assert "mock-credential" not in serialized
        payload = json.loads(messages[1]["content"])
        if "remaining_source_titles" in payload:
            index = len(payload["sources_already_examined"])
            choice = ["S1", "S2", "S3"][index]
            assert choice in [row["id"] for row in payload["remaining_source_titles"]]
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1", "action": "read",
                "source_id": choice, "reason": "Read a possibly material fictional record",
            })}
        return {"content": json.dumps(_draft())}


def test_live_mock_integration_has_four_calls_and_hidden_rubric():
    model = SyntheticCloud()
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "competing_commands", confirmed=True))
    assert result["success"] is True
    assert len(model.calls) == 4
    assert result["cloud_requests_attempted"] == 4
    assert result["independent_review_packet"]["answer_coverage_review"][
        "reference_rubric_not_sent_to_model"]
    assert result["publisher_approval"] is False
    assert "mock-credential" not in json.dumps(result)


def test_stage72_phone_ratings_default_unreviewed_and_never_publish():
    html = render_page("HomeBrainOS", "0.18.304")
    for phrase in (
        "Stage 7.2 · Did the answer resolve the actual question?",
        "Independent answer assessment",
        "Reference evidence IDs:",
        "Citation overlap is not semantic answer verification.",
        "answer_obligation_review:coverageControls.map",
        "coverageControls.every(item=>item.element.value!=='not_reviewed')",
        "production_publication_approval:false",
    ):
        assert phrase in html


def test_no_production_module_imports():
    for filename in (
        "mcp_agent_orchestrator.py", "tool_executor.py",
        "causal_claim_publication.py", "final_answer_coordinator.py",
    ):
        source = (APP / filename).read_text()
        assert "stage72_answer_coverage" not in source

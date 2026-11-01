"""Stage 7.5 independent host structural evidence and human answer review.

Regression cases use fictional source fixtures and mock model envelopes only.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import _CASES, _host_proof, Stage6Benchmark  # noqa: E402
from stage72_answer_coverage import build_answer_coverage_review  # noqa: E402
from stage75_evidence_answer_review import build_stage75_review  # noqa: E402
from stage7_review_packet import build_review_packet  # noqa: E402
from webui import render_page  # noqa: E402


def answer(*, include_relation=False, text="The OFF report does not establish which app caused it."):
    sentences = [
        {"text": "The first app issued OFF.", "kind": "command_record",
         "evidence_ids": ["E1"], "atoms": []},
        {"text": "The second app issued a brightness command.", "kind": "command_record",
         "evidence_ids": ["E2"], "atoms": []},
        {"text": "The light was reported OFF.", "kind": "state_report",
         "evidence_ids": ["I1"], "atoms": []},
        {"text": text, "kind": "unique_cause",
         "evidence_ids": ["E1", "E2", "I1"], "atoms": [],
         "epistemic": {"position": "not_established",
                       "scope": "examined_records"}},
    ]
    if include_relation:
        sentences.append({"text": "Two different application commands were recorded.",
                          "kind": "competing_commands",
                          "evidence_ids": ["E1", "E2"], "atoms": [],
                          "epistemic": {"position": "affirmed",
                                        "scope": "examined_records"}})
    for item in sentences:
        item.setdefault("epistemic", {"position": "affirmed", "scope": "examined_records"})
    return {"schema": "homebrain-stage6-answer.v3", "sentences": sentences,
            "uncertainties": ["Physical actuation and unique cause remain unverified"],
            "next_evidence": "Check independent device telemetry"}


def review(case="competing_commands", selected=None, draft=None):
    fixture = _CASES[case]
    selected = ["S1", "S2", "S3"] if selected is None else selected
    draft = draft or answer()
    coverage = build_answer_coverage_review(case, fixture, selected, draft)
    return build_stage75_review(fixture, selected, draft, coverage, _host_proof)


def test_observable_conflicting_commands_not_penalized_by_model_label_choice():
    result = review()
    source = result["source_evidence"]
    assert source["host_observable_reference_type_coverage"] == "3/3"
    assert source["model_declared_reference_type_coverage"] == "2/3"
    assert "competing_commands" in source["host_observable_reference_types"]
    assert result["natural_language_factual_semantics_verified"] is False
    assert result["publisher_approval"] is False
    with_relation = review(draft=answer(include_relation=True))
    assert with_relation["source_evidence"]["host_observable_reference_type_coverage"] == "3/3"
    assert with_relation["source_evidence"]["model_declared_reference_type_coverage"] == "3/3"


def test_causal_evidence_ladder_preserves_command_telemetry_and_missing_link():
    ladder = review()["causal_evidence_ladder"]
    assert set(ladder["recorded_command_ids"]) == {"E1", "E2"}
    assert ladder["reported_state_record_ids"] == ["I1"]
    assert ladder["independent_device_telemetry_ids"] == []
    assert ladder["command_acknowledgement_record_ids"] == []
    assert ladder["explicit_coverage_gap_ids"] == ["E3"]
    assert ladder["unique_causal_attribution_proven"] is False
    assert ladder["telemetry_alone_identifies_command_initiator"] is False


@pytest.mark.parametrize("case", ["clock_conflict", "competing_commands",
                                     "stale_connectivity"])
def test_structural_evidence_is_postrun_and_not_an_answer_certification(case):
    fixture = _CASES[case]
    draft = answer()
    # The synthetic answer's citations must be available for each scenario;
    # build a minimal scenario-specific envelope instead.
    draft["sentences"] = [{"text": "Reported state requires interpretation.",
                           "kind": "state_report", "evidence_ids": ["I1"],
                           "atoms": [], "epistemic": {
                               "position": "affirmed", "scope": "examined_records"}}]
    result = review(case=case, draft=draft)
    assert result["source_evidence"]["host_observable_reference_type_coverage"] == (
        f"{len(fixture['required_types'])}/{len(fixture['required_types'])}")
    assert all(item["independent_semantic_verdict"] == "not_reviewed"
               for item in result["original_question_review"]["obligations"])
    assert result["additional_cloud_requests"] == 0
    assert result["publisher_approval"] is False


def test_telemetry_establishes_observation_but_not_which_app_command_caused_it():
    result = review(case="stale_connectivity", draft={
        **answer(), "sentences": [{
            "text": "A plug packet was observed.", "kind": "device_telemetry",
            "evidence_ids": ["E2"], "atoms": [], "epistemic": {
                "position": "affirmed", "scope": "examined_records"}}]})
    ladder = result["causal_evidence_ladder"]
    assert ladder["independent_device_telemetry_ids"] == ["E2"]
    assert ladder["command_correlated_execution_confirmed"] is False


def test_coverage_and_unsafe_prose_share_evidence_but_neither_is_certified():
    safe = review()
    dishonest = review(draft=answer(
        text="The first app definitely caused the physical OFF state."))
    assert safe["source_evidence"] == dishonest["source_evidence"]
    assert safe["original_question_review"] == dishonest["original_question_review"]
    assert not dishonest["natural_language_factual_semantics_verified"]


def test_skipped_source_is_not_silently_credited_to_model():
    # E3 exists in the reviewer fixture but was not inspected by Gemma.
    result = review(selected=["S1", "S2"])
    obligation = next(item for item in result["original_question_review"]["obligations"]
                      if item["id"] == "causal_answer")
    assert obligation["reference_evidence_status"] == "reference_evidence_not_fully_examined"
    assert "E3" not in result["causal_evidence_ladder"]["explicit_coverage_gap_ids"]


@pytest.mark.parametrize("selected", [["S1", "S1"], ["S999"], ["S1"] * 4])
def test_invalid_selection_is_rejected(selected):
    with pytest.raises(ValueError):
        review(selected=selected)


def test_independent_packet_contains_worklist_without_giving_gemmas_answer_a_grade():
    case = _CASES["competing_commands"]
    packet = build_review_packet("competing_commands", case, ["S1", "S2", "S3"], answer())
    stage = packet["stage75_evidence_answer_review"]
    assert stage["source_evidence"]["host_observable_reference_type_coverage"] == "3/3"
    assert stage["original_question_review"]["no_automatic_answer_completeness_verdict"]
    assert packet["publisher_approval"] is False
    assert len(json.dumps(packet)) < 32000


class MockCloud:
    api_key = "private-test-key"
    base_url = "https://ollama.com"
    model_name = "gemma4:31b"
    timeout_seconds = 60
    configured = True

    def __init__(self):
        self.calls = []

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append(messages)
        text = json.dumps(messages)
        assert "stage75_evidence_answer_review" not in text
        assert "reference_evidence_status" not in text
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            index = len(body["sources_already_examined"])
            return {"content": json.dumps({"schema": "homebrain-stage6-next.v1",
                "action": "read", "source_id": ["S1", "S2", "S3"][index],
                "reason": "Read a potentially relevant fictional record"})}
        return {"content": json.dumps(answer())}


def test_four_calls_no_extra_inference_or_device_control():
    model = MockCloud()
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "competing_commands", confirmed=True))
    assert len(model.calls) == 4
    assert result["independent_review_packet"]["stage75_evidence_answer_review"][
        "source_evidence"]["host_observable_reference_type_coverage"] == "3/3"
    assert result["publisher_approval"] is False


def test_mobile_stage75_source_structure_and_obligation_review_separate():
    html = render_page("HomeBrainOS", "0.18.307")
    for phrase in ("Stage 7.5 · Source structure vs answer quality",
                   "Host-observable evidence types:", "Model-declared types:",
                   "Command-correlated execution proven:", "not independently fact-checked",
                   "model_declared_reference_type_coverage"):
        assert phrase in html


def test_no_production_runtime_imports_stage75():
    for filename in ("mcp_agent_orchestrator.py", "tool_executor.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage75_evidence_answer_review" not in (APP / filename).read_text()

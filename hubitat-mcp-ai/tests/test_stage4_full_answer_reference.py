"""Stage 4H complete-answer benchmark: all inference mocked in unit tests.

Actual Ollama inference occurs ONLY in the dedicated, separately gated
GitHub Actions job. Reference labels are pre-authored and never sent to
models. A citation-valid sentence still can assert unsupported causation.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from stage4_full_answer_reference import (
    evaluate_stage4h_full_answer_references,
)
from stage4h_github_full_answer_reference import (
    _prelabelled_full_answer_cases, summary_markdown, main,
)

_MODELS = ("qwen2.5:3b", "llama3.2:3b")


class ReferenceReview:
    def __init__(self, cases):
        self.expected = {}
        self.requests = []
        for case in cases:
            for row, oracle in zip(
                case["proposal"]["sections"][0]["sentences"],
                case["sentence_oracle"],
            ):
                old = self.expected.setdefault(row["text"], oracle)
                assert old == oracle

    def __call__(self, model, job):
        assert model in _MODELS
        assert job["task"] == "review"
        assert len(job["sentences"]) == 1
        row = job["sentences"][0]
        assert row["sentence_id"] == "s001"
        raw = json.dumps(job)
        for secret in ("answer_oracle", "sentence_oracle", "required_fact_ids",
                       "case_id", "question", "ground_truth"):
            assert secret not in raw
        self.requests.append((model, deepcopy(job)))
        label = self.expected[row["text"]]
        return {
            "schema": "homebrain-stage4b-semantic-review.v1",
            "assessments": [{
                "sentence_id": "s001",
                "verdict": "entailed" if label == "entailed" else "insufficient",
                "supporting_fact_ids": (
                    list(row["cited_fact_ids"]) if label == "entailed" else []),
            }],
        }


def evaluate(cases, reviewer):
    return evaluate_stage4h_full_answer_references(
        cases, reviewer_models=_MODELS, invoke=reviewer)


def test_fixed_reference_corpus_covers_complete_answers_across_four_domains():
    cases = _prelabelled_full_answer_cases()
    assert len(cases) == 8
    assert {c["domain"] for c in cases} == {
        "lighting", "heating", "ventilation", "history"}
    assert [c["answer_oracle"] for c in cases].count("adequate") == 4
    assert [c["answer_oracle"] for c in cases].count("unsupported") == 3
    assert [c["answer_oracle"] for c in cases].count("incomplete") == 1
    assert all(len(c["sentence_oracle"]) == 2 for c in cases)
    assert all(c["packet"]["shadow_only"] is True for c in cases)
    assert "192.168." not in json.dumps(cases)


def test_synthetic_host_reference_reviews_measure_answer_acceptance_and_omission():
    cases = _prelabelled_full_answer_cases()
    copy = deepcopy(cases)
    fake = ReferenceReview(cases)
    report = evaluate(cases, fake)
    assert cases == copy
    assert len(fake.requests) == 32
    assert report["cases"] == 8
    assert report["reference_sentences"] == 16
    assert report["reference_supported_sentences"] == 13
    assert report["reference_unsupported_sentences"] == 3
    assert report["review_attempts"] == 32
    assert report["review_responses"] == 32
    assert report["valid_review_pairs"] == 16
    assert report["complete_reviewed_answers"] == 8
    assert report["answers_with_full_fact_coverage"] == 7
    assert report["reference_facts_selected"] == (
        report["reference_facts_required"] - 1)
    assert report["adequate_answers_accepted"] == 4
    assert report["unsupported_answers_accepted"] == 0
    assert report["incomplete_answers_accepted"] == 0
    assert report["consensus_false_accepts"] == 0
    assert report["consensus_false_rejects"] == 0
    assert report["newly_generated_stage4g_answers_independently_scored"] is False
    assert report["answer_publication_permitted"] is False
    assert report["real_world_explanation_quality_established"] is False


def test_unsafe_consensus_hallucination_is_counted_at_sentence_and_answer_level():
    cases = _prelabelled_full_answer_cases()
    def all_accept(_, job):
        row = job["sentences"][0]
        return {
            "schema": "homebrain-stage4b-semantic-review.v1",
            "assessments": [{"sentence_id": "s001", "verdict": "entailed",
                             "supporting_fact_ids": list(row["cited_fact_ids"])}],
        }
    report = evaluate(cases, all_accept)
    assert report["consensus_false_accepts"] == 3
    assert report["unsupported_answers_accepted"] == 3
    assert report["incomplete_answers_accepted"] == 0
    assert report["adequate_answers_accepted"] == 4
    assert all(report["model_metrics"][m]["unsafe_accepted"] == 3
               for m in _MODELS)
    assert all(report["model_metrics"][m]["incomplete_accepted"] == 0
               for m in _MODELS)
    assert report["answer_publication_permitted"] is False


def test_blanket_rejection_is_measured_as_false_rejection_and_not_claimed_safe():
    cases = _prelabelled_full_answer_cases()
    def reject_all(_, job):
        return {"schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [{"sentence_id": "s001", "verdict": "insufficient",
                                 "supporting_fact_ids": []}]}
    result = evaluate(cases, reject_all)
    assert result["adequate_answers_accepted"] == 0
    assert result["adequate_answers_rejected"] == 4
    assert result["consensus_false_rejects"] == 13
    assert result["consensus_false_accepts"] == 0


def test_source_coverage_is_independent_of_model_judgments():
    cases = _prelabelled_full_answer_cases()
    result = evaluate(cases, ReferenceReview(cases))
    assert result["reference_facts_required"] > result["reference_facts_selected"]
    assert result["incomplete_answers_accepted"] == 0
    assert result["model_metrics"][_MODELS[0]]["incomplete_accepted"] == 0


def test_invalid_review_not_scored_as_false_acceptance_or_approval():
    cases = _prelabelled_full_answer_cases()
    true_review = ReferenceReview(cases)
    def inconsistent(model, job):
        if model == _MODELS[1]:
            return {"schema": "invalid", "assessments": []}
        return true_review(model, job)
    result = evaluate(cases, inconsistent)
    assert result["valid_review_pairs"] == 0
    assert result["unscored_incomplete_answers"] == 8
    assert result["complete_reviewed_answers"] == 0
    assert result["unsupported_answers_accepted"] == 0
    assert result["model_metrics"][_MODELS[1]]["invalid"] == 16
    assert result["answer_publication_permitted"] is False


def test_model_disagreement_preserved_instead_of_assuming_independence():
    cases = _prelabelled_full_answer_cases()
    fake = ReferenceReview(cases)
    def conflicting(model, job):
        if model == _MODELS[1]:
            row = job["sentences"][0]
            return {
                "schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [{"sentence_id": "s001", "verdict": "entailed",
                                 "supporting_fact_ids": list(row["cited_fact_ids"])}],
            }
        return fake(model, job)
    result = evaluate(cases, conflicting)
    assert result["reviewer_disagreements"] == 3
    assert result["consensus_false_accepts"] == 0
    assert result["model_metrics"][_MODELS[1]]["false_accepts"] == 3
    assert result["reference_labels_host_curated_not_externally_authenticated"]


@pytest.mark.parametrize("mutate", [
    lambda cases: cases.append(deepcopy(cases[0])),
    lambda cases: cases[0].update({"answer_oracle": "incomplete"}),
    lambda cases: cases[0].update({"answer_oracle": "unknown"}),
    lambda cases: cases[0].update({"case_id": "Private Name"}),
    lambda cases: cases[0]["proposal"]["sections"][0]["sentences"][0].update({
        "fact_ids": ["f999"]}),
    lambda cases: cases[0].update({"required_fact_ids": ["f999"]}),
    lambda cases: cases[0].update({"sentence_oracle": ["entailed"]}),
    lambda cases: cases[0]["packet"].update({"shadow_only": False}),
])
def test_reference_envelopes_fail_closed_on_invalid_labels_or_scopes(mutate):
    cases = _prelabelled_full_answer_cases()
    mutate(cases)
    with pytest.raises(ValueError):
        evaluate(cases, lambda *_: {})


def test_benchmark_oracles_not_sent_to_real_model_adapter():
    cases = _prelabelled_full_answer_cases()
    fake = ReferenceReview(cases)
    evaluate(cases, fake)
    assert len(fake.requests) == 32
    for _, task in fake.requests:
        data = json.dumps(task)
        assert "not-entailed" not in data
        assert "\\"answer_oracle\\"" not in data
        assert "answer_oracle" not in data
        assert "required_fact_ids" not in data


def test_report_and_summary_have_no_raw_text_ids_or_private_household_data():
    cases = _prelabelled_full_answer_cases()
    cases[0]["proposal"]["sections"][0]["sentences"][0]["text"] = (
        "PRIVATE-HOUSEHOLD-SECRET an issued command was recorded.")
    fake = ReferenceReview(cases)
    report = evaluate(cases, fake)
    raw = json.dumps(report) + summary_markdown(report)
    for secret in ("PRIVATE-HOUSEHOLD-SECRET", "Synthetic Controller",
                   "2026-01-01", '"101"', "fact_id", "f001",
                   "case_id", "question", "source_clock"):
        assert secret not in raw
    assert "No device access" in summary_markdown(report)


def test_cli_declines_before_any_local_inference_without_ack_or_env(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert main([]) == 2
    assert "acknowledgment required" in capsys.readouterr().err
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    assert "localhost-only" in capsys.readouterr().err


def test_cli_fake_transport_outputs_aggregate_metrics_only(monkeypatch, tmp_path, capsys):
    cases = _prelabelled_full_answer_cases()
    fake = ReferenceReview(cases)
    class Client:
        def __init__(self, **kwargs):
            self.attempted = 0
        def __call__(self, model, task):
            self.attempted += 1
            return fake(model, task)
    for k, v in (("GITHUB_ACTIONS", "true"), ("OLLAMA_NO_CLOUD", "1"),
                 ("OLLAMA_HOST", "127.0.0.1:11434"),
                 ("GITHUB_STEP_SUMMARY", str(tmp_path / "report.md"))):
        monkeypatch.setenv(k, v)
    monkeypatch.setattr("stage4h_github_full_answer_reference.CalibratedLoopbackOllama", Client)
    assert main(["--ack-github-synthetic-local-inference"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["complete_reviewed_answers"] == 8
    assert (tmp_path / "report.md").is_file()


def test_new_github_workflow_is_read_only_local_only_and_no_production_import():
    workflow = (
        ROOT.parent / ".github/workflows/stage4h-full-answer-reference.yml"
    ).read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "OLLAMA_NO_CLOUD: '1'" in workflow
    assert "OLLAMA_HOST: '127.0.0.1:11434'" in workflow
    assert "pull_request_target" not in workflow
    assert "upload-artifact@" not in workflow
    assert "${{ secrets." not in workflow
    for name in ("mcp_agent_orchestrator.py", "final_answer_coordinator.py",
                 "causal_claim_publication.py", "app.py"):
        assert "stage4_full_answer_reference" not in (
            ROOT / "rootfs" / "app" / name).read_text()

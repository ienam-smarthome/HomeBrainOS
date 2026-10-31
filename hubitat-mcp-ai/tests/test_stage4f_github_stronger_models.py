"""Stage 4F tests: mock models are NOT reported as real reviewer results."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "tools"))
from stage4c_local_model_eval import _constructed_cases
from stage4f_github_stronger_models import (
    _MODELS, _BALANCED_INSTRUCTIONS, CalibratedLoopbackOllama,
    evaluate, summary_markdown, main,
)


class FakeModel:
    def __init__(self, cases):
        self.actual = {
            c["draft"]["sections"][0]["sentences"][0]["text"]: c["oracle"][0]
            for c in cases
        }
        self.calls = []

    def __call__(self, model, task):
        assert model in _MODELS
        assert task["task"] == "review"
        assert "oracle" not in json.dumps(task)
        assert "case_id" not in json.dumps(task)
        self.calls.append((model, deepcopy(task)))
        row = task["sentences"][0]
        verdict = ("entailed" if self.actual[row["text"]] == "entailed"
                   else "insufficient")
        return {
            "schema": "homebrain-stage4b-semantic-review.v1",
            "assessments": [{
                "sentence_id": row["sentence_id"], "verdict": verdict,
                "supporting_fact_ids": (
                    list(row["cited_fact_ids"]) if verdict == "entailed" else []),
            }],
        }


def test_constructed_eight_cases_are_scored_per_3b_reviewer():
    cases = _constructed_cases()
    before = deepcopy(cases)
    client = FakeModel(cases)
    report = evaluate(invoke=client, cases=cases)
    assert cases == before
    assert report["case_count"] == 8
    assert report["model_requests_attempted"] == 16
    assert report["valid_complete_review_pairs"] == 8
    assert report["reference_scored_sentences"] == 8
    assert report["consensus_false_accept_count"] == 0
    assert report["consensus_false_reject_count"] == 0
    assert len(client.calls) == 16
    for model in _MODELS:
        row = report["reviewers"][model]
        assert row["requests"] == row["responses"] == row["valid"] == 8
        assert row["true_accepts"] == 4
        assert row["true_rejects"] == 4
        assert row["false_accept_rate"] == 0
        assert row["false_reject_rate"] == 0
    assert report["live_homebrain_approval"] is False
    assert report["production_answer_publisher_changed"] is False


def test_two_realistic_overcautious_models_are_measured_separately():
    cases = _constructed_cases()
    def reject_all(model, task):
        row = task["sentences"][0]
        return {"schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [{"sentence_id": row["sentence_id"],
                                 "verdict": "insufficient",
                                 "supporting_fact_ids": []}]}
    r = evaluate(invoke=reject_all, cases=cases)
    assert r["consensus_false_reject_count"] == 4
    assert r["consensus_false_reject_rate"] == 1.0
    assert r["consensus_false_accept_count"] == 0
    for name in _MODELS:
        assert r["reviewers"][name]["false_rejects"] == 4
        assert r["reviewers"][name]["true_accepts"] == 0


def test_one_bad_reviewer_is_visible_even_when_pair_rejects():
    cases = _constructed_cases()
    fake = FakeModel(cases)
    def mismatch(model, task):
        if model == _MODELS[1]:
            row = task["sentences"][0]
            return {"schema": "homebrain-stage4b-semantic-review.v1",
                    "assessments": [{"sentence_id": row["sentence_id"],
                                     "verdict": "insufficient",
                                     "supporting_fact_ids": []}]}
        return fake(model, task)
    r = evaluate(invoke=mismatch, cases=cases)
    assert r["reviewers"][_MODELS[0]]["false_rejects"] == 0
    assert r["reviewers"][_MODELS[1]]["false_rejects"] == 4
    assert r["reviewer_disagreement_sentences"] == 4
    assert r["consensus_false_reject_count"] == 4
    assert r["live_homebrain_approval"] is False


def test_concordant_hallucinations_are_counted_as_false_accepts():
    cases = _constructed_cases()
    fake = FakeModel(cases)
    def wrong(model, job):
        value = fake(model, job)
        if job["sentences"][0]["text"] == (
            "The boiler fired and every radiator valve opened."):
            value["assessments"][0]["verdict"] = "entailed"
            value["assessments"][0]["supporting_fact_ids"] = (
                list(job["sentences"][0]["cited_fact_ids"]))
        return value
    r = evaluate(invoke=wrong, cases=cases)
    assert r["consensus_false_accept_count"] == 1
    assert r["consensus_false_accept_rate"] == .25
    assert all(r["reviewers"][m]["false_accepts"] == 1 for m in _MODELS)
    assert r["production_answer_publisher_changed"] is False


def test_model_exception_and_invalid_response_are_not_counted_as_correct():
    cases = _constructed_cases()
    fake = FakeModel(cases)
    def bad(model, task):
        if model == _MODELS[0]:
            raise RuntimeError("SENSITIVE-HOME-DOOR")
        value = fake(model, task)
        value["assessments"][0]["supporting_fact_ids"] = ["f999"]
        return value
    r = evaluate(invoke=bad, cases=cases)
    assert r["valid_complete_review_pairs"] == 0
    assert r["model_invocation_errors"] == 8
    assert r["consensus_false_accept_rate"] is None
    assert r["consensus_false_reject_rate"] is None
    assert "SENSITIVE-HOME" not in json.dumps(r)
    assert r["reviewers"][_MODELS[0]]["responses"] == 0
    assert r["reviewers"][_MODELS[1]]["invalid"] == 8


def test_no_benchmark_oracle_allowed_in_model_review_request():
    cases = _constructed_cases()
    fake = FakeModel(cases)
    evaluate(invoke=fake, cases=cases)
    assert len(fake.calls) == 16
    for _, task in fake.calls:
        payload = json.dumps(task)
        assert "oracle" not in payload
        assert "reference_supported" not in payload
        assert "ground_truth" not in payload
        assert "benchmark" not in payload


def test_balanced_prompt_explains_positive_and_negative_entailment_without_examples():
    assert "MUST be accepted" in _BALANCED_INSTRUCTIONS
    assert "Choose insufficient" in _BALANCED_INSTRUCTIONS
    assert "outside assumptions" in _BALANCED_INSTRUCTIONS
    assert "bathroom" not in _BALANCED_INSTRUCTIONS.casefold()
    assert "motion" not in _BALANCED_INSTRUCTIONS.casefold()
    assert "required_fields" not in _BALANCED_INSTRUCTIONS


def test_loopback_transport_is_structured_and_does_not_prechoose_verdict():
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self, size):
            return json.dumps({"message": {"content": json.dumps({
                "schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [{"sentence_id": "s001",
                                 "verdict": "entailed",
                                 "supporting_fact_ids": ["f001"]}],
            })}}).encode()
    class Open:
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:11434/api/chat"
            j = json.loads(request.data)
            assert j["model"] == _MODELS[0]
            assert j["format"]["properties"]["assessments"]["minItems"] == 1
            assert j["options"]["temperature"] == 0
            assert j["options"]["num_predict"] == 512
            assert "required_fields" not in j["messages"][1]["content"]
            assert "oracle" not in j["messages"][1]["content"]
            assert j["messages"][0]["content"] == _BALANCED_INSTRUCTIONS
            return Response()
    client = CalibratedLoopbackOllama()
    client._opener = Open()
    reply = client(_MODELS[0], {
        "task": "review", "sentences": [{
            "sentence_id": "s001", "text": "A command was recorded.",
            "cited_fact_ids": ["f001"],
            "cited_host_facts": [{"fact_id": "f001", "kind": "issued_command"}],
        }], "source_facts_may_be_truncated": False,
    })
    assert reply["assessments"][0]["verdict"] == "entailed"
    assert client.attempted == client.succeeded == 1


def test_input_limit_rejects_unlabelled_or_mixed_private_cases():
    cases = _constructed_cases()
    cases[0]["trace_origin"] = "owner-labelled-redacted"
    with pytest.raises(ValueError):
        evaluate(invoke=lambda *_: {}, cases=cases)
    with pytest.raises(ValueError):
        evaluate(invoke=lambda *_: {}, cases=_constructed_cases()[:7])


def test_summary_contains_aggregate_statistics_not_source_text():
    r = evaluate(invoke=FakeModel(_constructed_cases()))
    output = json.dumps(r) + summary_markdown(r)
    for forbidden in ("The boiler fired", "Synthetic Controller", "2026-01-01",
                      '"101"', "case_id", "f001", "auth_token"):
        assert forbidden not in output
    assert "Qwen" not in output  # approved model tags only
    assert "Stage 4F" in output


def test_cli_rejects_no_consent_or_non_github_environment(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert main([]) == 2
    assert "acknowledgement" in capsys.readouterr().err
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    assert "GitHub loopback-only" in capsys.readouterr().err


def test_cli_with_fake_transport_still_cannot_publish(monkeypatch, capsys, tmp_path):
    source = _constructed_cases()
    fake = FakeModel(source)
    class Client:
        def __init__(self, **kwargs): self.attempted = 0
        def __call__(self, model, task):
            self.attempted += 1
            return fake(model, task)
    for key, value in (
        ("GITHUB_ACTIONS", "true"), ("OLLAMA_NO_CLOUD", "1"),
        ("OLLAMA_HOST", "127.0.0.1:11434"),
        ("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md")),
    ):
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("stage4f_github_stronger_models.CalibratedLoopbackOllama", Client)
    assert main(["--ack-github-synthetic-local-inference"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["valid_complete_review_pairs"] == 8
    assert not result["live_homebrain_approval"]
    assert (tmp_path / "summary.md").is_file()


def test_workflow_isolation_and_no_active_integration():
    wf = (ROOT.parent / ".github/workflows/stage4f-stronger-model-evaluation.yml"
          ).read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in wf
    assert "persist-credentials: false" in wf
    assert "OLLAMA_NO_CLOUD: '1'" in wf
    assert "OLLAMA_HOST: '127.0.0.1:11434'" in wf
    assert "pull_request_target" not in wf
    assert "upload-artifact@" not in wf
    assert "${{ secrets." not in wf
    assert "qwen2.5:3b" in wf and "llama3.2:3b" in wf
    assert "github.event.pull_request.head.repo.full_name == github.repository" in wf
    for filename in ("app.py", "mcp_agent_orchestrator.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage4f_github_stronger_models" not in (
            ROOT / "rootfs" / "app" / filename).read_text()

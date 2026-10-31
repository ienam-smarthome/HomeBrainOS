"""Stage 4K tests: fake inference validates experiment, NOT model quality."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from stage4k_github_matched_models import (
    _heldout_cases, _MODELS, evaluate_matched_models, summary_markdown, main,
)
from stage4j_github_prose_coverage import (
    _synthetic_prose_cases, Stage4JLocalExtractor,
)
from stage4_prose_atom_coverage import evaluate_stage4j_prose_claim_coverage


class FakeOracle:
    def __init__(self, cases):
        self.labelled = {r["sentence"]: deepcopy(r["reference_atoms"])
                         for r in cases}
        assert len(self.labelled) == len(cases)
        self.queries = []

    def __call__(self, model, job):
        assert model in _MODELS and job["task"] == "extract"
        assert set(job) == {"task", "schema", "sentence", "packet"}
        for prohibited in ("reference_atoms", "oracle", "gold_label",
                           "ground_truth", "expected_atom_count"):
            assert prohibited not in json.dumps(job)
        self.queries.append((model, deepcopy(job)))
        return {"schema": "homebrain-stage4j-atom-extraction.v1",
                "atoms": deepcopy(self.labelled[job["sentence"]])}


def _all():
    return _synthetic_prose_cases() + _heldout_cases()


def test_holdout_has_eight_new_constructed_cases_and_diverse_risks():
    b = _synthetic_prose_cases()
    h = _heldout_cases()
    assert len(b) == 12 and len(h) == 8
    assert len({c["sentence"] for c in b+h}) == 20
    assert len([a for c in h for a in c["reference_atoms"]
                if a["proposition"] in (
                    "upstream_cause", "physical_effect", "absence_of_event",
                    "complete_history")]) >= 4
    assert len([a for c in h for a in c["reference_atoms"]
                if a["proposition"] == "recorded_event"]) >= 3
    assert all(c["packet"]["shadow_only"] for c in h)


def test_same_immutable_corpus_each_model_and_no_reference_leakage():
    all_cases = _all()
    fake = FakeOracle(all_cases)
    b, h = deepcopy(all_cases[:12]), deepcopy(all_cases[12:])
    original = deepcopy((b, h))
    outcome = evaluate_matched_models(invoke=fake, baseline=b, holdout=h)
    assert (b, h) == original
    assert len(fake.queries) == 40
    for name in ("stage4j-baseline", "stage4k-holdout"):
        a = outcome["model_results"][_MODELS[0]][name]
        z = outcome["model_results"][_MODELS[1]][name]
        assert a == z
        assert a["valid_responses"] == a["case_count"]
        assert a["extraction_recall"] == 1.0
        assert a["extraction_precision"] == 1.0
        assert a["missed_high_risk_atoms"] == 0
        assert a["extra_atoms"] == 0
        assert outcome["model_differences"][name][
            "delta_high_risk_misses_7b_minus_3b"] == 0
    # In exactly the same order, models see identical source and task.
    assert [x[1] for x in fake.queries[:20]] == [
        x[1] for x in fake.queries[20:]]
    assert outcome["publisher_approval"] is False
    assert outcome["independent_human_adjudication_of_generated_answers"] is False


def test_disagreement_does_not_fabricate_7b_semantic_improvement():
    fake = FakeOracle(_all())
    def reject_everything_7b(model, job):
        if model == _MODELS[1]:
            return {"schema": "homebrain-stage4j-atom-extraction.v1",
                    "atoms": []}
        return fake(model, job)
    o = evaluate_matched_models(invoke=reject_everything_7b)
    for name in ("stage4j-baseline", "stage4k-holdout"):
        assert o["model_results"][_MODELS[1]][name]["extraction_recall"] == 0
        assert o["model_results"][_MODELS[1]][name][
            "missed_high_risk_atoms"] > 0
        assert o["model_differences"][name][
            "delta_high_risk_misses_7b_minus_3b"] > 0
    assert o["publisher_approval"] is False


def test_model_only_ablation_preserves_original_stage4j_3b_route():
    base = _synthetic_prose_cases()
    for name in _MODELS:
        result = evaluate_stage4j_prose_claim_coverage(
            base, model=name, invoke=FakeOracle(base))
        assert result["case_count"] == 12
    with pytest.raises(ValueError):
        evaluate_stage4j_prose_claim_coverage(base, model="qwen2.5:14b",
                                               invoke=lambda *_: {})


def test_model_only_ablation_uses_same_source_transport_prompt_and_schema():
    class Reply:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self, limit):
            return json.dumps({"message": {"content": json.dumps({
                "schema": "homebrain-stage4j-atom-extraction.v1",
                "atoms": []
            })}}).encode()
    requests = []
    class Open:
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:11434/api/chat"
            j = json.loads(request.data)
            requests.append(j)
            return Reply()
    client = Stage4JLocalExtractor()
    client._opener = Open()
    case = _synthetic_prose_cases()[0]
    for model in _MODELS:
        response = client(model, {"task": "extract",
                                  "sentence": case["sentence"],
                                  "packet": case["packet"]})
        assert response["atoms"] == []
    assert client.attempted == client.succeeded == 2
    assert requests[0]["model"] != requests[1]["model"]
    a, b = requests
    for key in ("messages", "format", "options", "stream"):
        assert a[key] == b[key]
    assert a["options"]["temperature"] == 0
    assert a["options"]["num_predict"] == 768
    assert "reference_atoms" not in json.dumps(a)


def test_empty_extractors_not_mislabelled_high_accuracy():
    def empty(_, __):
        return {"schema": "homebrain-stage4j-atom-extraction.v1", "atoms": []}
    out = evaluate_matched_models(invoke=empty)
    for name in _MODELS:
        for corpus in ("stage4j-baseline", "stage4k-holdout"):
            result = out["model_results"][name][corpus]
            assert result["extraction_recall"] == 0
            assert result["extraction_precision"] is None
            assert result["missed_high_risk_atoms"] == (
                result["reference_high_risk_atoms"])
    assert not out["publisher_approval"]


def test_transport_error_is_reported_not_silently_scored():
    def error(_, __):
        raise RuntimeError("PRIVATE HOME ADDRESS")
    out = evaluate_matched_models(invoke=error)
    for name in _MODELS:
        for corpus in ("stage4j-baseline", "stage4k-holdout"):
            result = out["model_results"][name][corpus]
            assert result["invocation_errors"] == result["case_count"]
            assert result["valid_responses"] == 0
    assert "PRIVATE HOME" not in json.dumps(out)


def test_model_cannot_mutate_corpus_or_hidden_oracle():
    fake = FakeOracle(_all())
    def tamper(model, job):
        job["packet"]["facts"][0]["entity_id"] = "modified"
        return fake(model, job)
    with pytest.raises(ValueError):
        evaluate_matched_models(invoke=tamper)


def test_reports_contain_safe_aggregate_only():
    out = evaluate_matched_models(invoke=FakeOracle(_all()))
    data = json.dumps(out)+summary_markdown(out)
    for forbidden in ("The source records", "The boiler", "The contact",
                      "2026-01-01", "Synthetic Controller", "f001",
                      '"101"', "fact_id", "required_fact_ids", "case_id",
                      "PRIVATE HOME"):
        assert forbidden not in data
    assert "not certify" in summary_markdown(out)
    assert out["comparison_of_created_answers"] is False


def test_cli_gates_ack_and_loopback(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert main([]) == 2
    assert "consent required" in capsys.readouterr().err
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    assert "no-cloud" in capsys.readouterr().err


def test_cli_aggregate_only_and_success_with_fake_transports(monkeypatch, tmp_path, capsys):
    fake = FakeOracle(_all())
    class Adapter:
        def __init__(self, **kwargs): self.attempted = 0
        def __call__(self, model, job):
            self.attempted += 1
            return fake(model, job)
    monkeypatch.setattr("stage4k_github_matched_models.Stage4JLocalExtractor",
                        Adapter)
    for key, value in (("GITHUB_ACTIONS", "true"), ("OLLAMA_NO_CLOUD", "1"),
                       ("OLLAMA_HOST", "127.0.0.1:11434"),
                       ("GITHUB_STEP_SUMMARY", str(tmp_path / "result.md"))):
        monkeypatch.setenv(key, value)
    assert main(["--ack-github-synthetic-local-inference"]) == 0
    printed = capsys.readouterr()
    assert printed.err == ""
    assert json.loads(printed.out)["matched_settings"]
    assert (tmp_path / "result.md").is_file()


def test_workflow_is_readonly_and_no_live_integration():
    wf = (ROOT.parent / ".github/workflows/stage4k-matched-3b-7b.yml"
          ).read_text()
    assert "permissions:\n  contents: read" in wf
    assert "persist-credentials: false" in wf
    assert "OLLAMA_NO_CLOUD: '1'" in wf
    assert "OLLAMA_HOST: '127.0.0.1:11434'" in wf
    assert "pull_request_target" not in wf
    assert "upload-artifact@" not in wf
    assert "${{ secrets." not in wf
    assert "qwen2.5:3b" in wf and "qwen2.5:7b" in wf
    for path in ("app.py", "mcp_agent_orchestrator.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage4k_github_matched_models" not in (
            ROOT / "rootfs" / "app" / path).read_text()

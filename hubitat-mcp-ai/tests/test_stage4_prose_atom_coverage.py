"""Stage 4J regression: oracle isolation, source-proof, missed claim metrics.

Mocks only. Real model weights are separately invoked by GitHub Actions.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from stage4_prose_atom_coverage import evaluate_stage4j_prose_claim_coverage
from stage4j_github_prose_coverage import (
    _synthetic_prose_cases, _json_schema, Stage4JLocalExtractor,
    summary_markdown, main,
)


class ReferenceExtractor:
    def __init__(self, cases):
        self.expected = {c["sentence"]: deepcopy(c["reference_atoms"]) for c in cases}
        self.requests = []

    def __call__(self, model, request):
        assert model == "qwen2.5:3b"
        assert request["task"] == "extract"
        assert set(request) == {"task", "schema", "sentence", "packet"}
        assert "reference_atoms" not in json.dumps(request)
        self.requests.append(deepcopy(request))
        return {
            "schema": "homebrain-stage4j-atom-extraction.v1",
            "atoms": deepcopy(self.expected[request["sentence"]]),
        }


def evaluate(cases, invoke):
    return evaluate_stage4j_prose_claim_coverage(
        cases, model="qwen2.5:3b", invoke=invoke,
    )


def test_constructed_multidomain_oracle_has_separate_safe_and_risky_atoms():
    cases = _synthetic_prose_cases()
    assert len(cases) == 12
    assert len({c["sentence"] for c in cases}) == 12
    assert all(c["packet"]["shadow_only"] is True for c in cases)
    high_risk = {"upstream_cause", "physical_effect",
                 "absence_of_event", "complete_history"}
    props = [atom["proposition"] for c in cases for atom in c["reference_atoms"]]
    assert {"recorded_event", "recorded_issuer", "recorded_clock",
            "recorded_gap", "packet_limit"} <= set(props)
    assert high_risk <= set(props)
    assert "192.168." not in json.dumps(cases)


def test_reference_extraction_matches_oracle_and_host_proves_only_source_witnesses():
    cases = _synthetic_prose_cases()
    before = deepcopy(cases)
    client = ReferenceExtractor(cases)
    result = evaluate(cases, client)
    assert before == cases
    assert len(client.requests) == 12
    assert result["case_count"] == result["valid_responses"] == 12
    assert result["correctly_extracted_atoms"] == result["reference_atoms"]
    assert result["missed_atoms"] == 0
    assert result["missed_high_risk_atoms"] == 0
    assert result["extra_atoms"] == 0
    assert result["extraction_recall"] == 1.0
    assert result["extraction_precision"] == 1.0
    assert result["host_unproven_high_risk_atoms"] == (
        result["reference_high_risk_atoms"])
    assert result["host_proven_extracted_atoms"] > 0
    assert result["proof_errors"] == 0
    assert not result["production_publisher_approval"]
    assert not result["extraction_completeness_on_unseen_prose_proven"]


def test_missed_implied_physical_effect_is_not_hidden_by_correct_command():
    cases = _synthetic_prose_cases()
    correct = ReferenceExtractor(cases)
    def partial(model, request):
        response = correct(model, request)
        if "boiler fired" in request["sentence"]:
            response["atoms"] = [
                atom for atom in response["atoms"]
                if atom["proposition"] != "physical_effect"
            ]
        return response
    result = evaluate(cases, partial)
    assert result["missed_high_risk_atoms"] == 1
    assert result["missed_atoms"] == 1
    assert result["host_proven_extracted_atoms"] > 0
    assert result["exact_extraction_cases"] == 11
    assert not result["production_publisher_approval"]


def test_all_empty_extractions_cannot_fake_perfect_safety():
    def empty(*_):
        return {"schema": "homebrain-stage4j-atom-extraction.v1", "atoms": []}
    result = evaluate(_synthetic_prose_cases(), empty)
    assert result["valid_responses"] == 12
    assert result["extraction_recall"] == 0
    assert result["extraction_precision"] is None
    assert result["missed_high_risk_atoms"] == result["reference_high_risk_atoms"]
    assert result["host_proven_extracted_atoms"] == 0
    assert result["exact_extraction_cases"] == 0


def test_wrong_source_type_does_not_become_safe_prose():
    cases = _synthetic_prose_cases()
    stub = ReferenceExtractor(cases)
    def wrong(model, req):
        response = stub(model, req)
        if "boiler fired" in req["sentence"]:
            response["atoms"][1]["proposition"] = "recorded_event"
        return response
    report = evaluate(cases, wrong)
    assert report["missed_high_risk_atoms"] == 1
    assert report["extra_atoms"] == 1
    assert report["reference_annotations_externally_authenticated"] is False


def test_inference_failures_count_all_missed_reference_atoms():
    cases = _synthetic_prose_cases()
    def throw(*_):
        raise RuntimeError("HOUSEHOLD-SECRET-IN-MODEL-ERROR")
    result = evaluate(cases, throw)
    assert result["invocation_errors"] == 12
    assert result["valid_responses"] == 0
    assert result["missed_atoms"] == result["reference_atoms"]
    assert result["missed_high_risk_atoms"] == result["reference_high_risk_atoms"]
    assert "HOUSEHOLD-SECRET" not in json.dumps(result)


def test_malformed_response_does_not_turn_into_source_certification():
    cases = _synthetic_prose_cases()
    def invalid(*_):
        return {"schema": "wrong", "atoms": []}
    result = evaluate(cases, invalid)
    assert result["invalid_responses"] == 12
    assert result["missed_atoms"] == result["reference_atoms"]
    assert result["host_proven_extracted_atoms"] == 0


@pytest.mark.parametrize("bad", [
    lambda out: out["atoms"][0].update({"proposition": "invented-trigger"}),
    lambda out: out["atoms"][0].update({"fact_ids": ["f999"]}),
    lambda out: out["atoms"][0].update({"fact_ids": ["f001", "f001"]}),
    lambda out: out["atoms"][0].update({"additional": "secret"}),
    lambda out: out["atoms"][0].update({"limit": "fake-full-proof"}),
    lambda out: out["atoms"].append(deepcopy(out["atoms"][0])),
])
def test_invalid_or_unbounded_model_claims_fail_closed(bad):
    cases = _synthetic_prose_cases()
    base = ReferenceExtractor(cases)
    def wrong(model, req):
        result = base(model, req)
        bad(result)
        return result
    stats = evaluate(cases, wrong)
    assert stats["invalid_responses"] >= 1
    assert stats["missed_atoms"] >= 1
    assert not stats["production_publisher_approval"]


def test_reference_labels_never_enter_model_inference_job():
    cases = _synthetic_prose_cases()
    client = ReferenceExtractor(cases)
    evaluate(cases, client)
    for job in client.requests:
        payload = json.dumps(job)
        assert "reference_atoms" not in payload
        assert "reference_high_risk_atoms" not in payload
        assert "oracle" not in payload
        assert "ground_truth" not in payload


def test_http_transport_uses_only_local_ollama_and_structured_role_schema():
    cases = _synthetic_prose_cases()
    class Reply:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self, length):
            return json.dumps({"message": {"content": json.dumps({
                "schema": "homebrain-stage4j-atom-extraction.v1",
                "atoms": [{"proposition": "recorded_event",
                           "fact_ids": [cases[0]["packet"]["facts"][0]["fact_id"]],
                           "limit": None}]
            })}}).encode()
    class Local:
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:11434/api/chat"
            raw = json.loads(request.data)
            assert raw["model"] == "qwen2.5:3b"
            assert raw["stream"] is False
            assert raw["format"]["properties"]["atoms"]["maxItems"] == 5
            assert "reference_atoms" not in raw["messages"][1]["content"]
            return Reply()
    client = Stage4JLocalExtractor()
    client._opener = Local()
    result = client("qwen2.5:3b", {
        "task": "extract", "sentence": cases[0]["sentence"],
        "packet": cases[0]["packet"],
    })
    assert result["atoms"][0]["proposition"] == "recorded_event"
    assert client.attempted == client.succeeded == 1


def test_source_ids_in_schema_come_from_packet_not_model():
    c = _synthetic_prose_cases()[0]
    schema = _json_schema(c["packet"])
    ids = [x["fact_id"] for x in c["packet"]["facts"]]
    assert schema["properties"]["atoms"]["items"]["properties"]["fact_ids"][
        "items"]["enum"] == ids
    assert "reference_atoms" not in json.dumps(schema)
    assert "default" not in json.dumps(schema)


def test_report_and_summary_never_expose_private_sentence_or_source_values():
    cases = deepcopy(_synthetic_prose_cases())
    cases[0]["sentence"] = "SECRET-HOUSEHOLD-CONTENT 123"
    cases[0]["reference_atoms"] = deepcopy(cases[1]["reference_atoms"])
    fake = ReferenceExtractor(cases)
    result = evaluate(cases, fake)
    printed = json.dumps(result) + summary_markdown(result)
    for secret in ("SECRET-HOUSEHOLD-CONTENT", "Synthetic Controller",
                   "2026-01-01", '"101"', "f001", "boiler fired",
                   "sentence", "reference_atoms", "case_id", "entity_id"):
        assert secret not in printed
    assert not result["production_publisher_approval"]


def test_cli_requires_user_consent_and_local_no_cloud_environment(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert main([]) == 2
    assert "consent required" in capsys.readouterr().err
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    assert "no-cloud" in capsys.readouterr().err


def test_cli_mocked_returns_only_aggregates(monkeypatch, capsys, tmp_path):
    cases = _synthetic_prose_cases()
    fake = ReferenceExtractor(cases)
    class Client:
        def __init__(self, **kwargs): self.attempted = 0
        def __call__(self, model, req):
            self.attempted += 1
            return fake(model, req)
    monkeypatch.setattr("stage4j_github_prose_coverage.Stage4JLocalExtractor", Client)
    for field, val in (
        ("GITHUB_ACTIONS", "true"), ("OLLAMA_NO_CLOUD", "1"),
        ("OLLAMA_HOST", "127.0.0.1:11434"),
        ("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md")),
    ):
        monkeypatch.setenv(field, val)
    assert main(["--ack-github-synthetic-local-inference"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["exact_extraction_cases"] == 12
    assert (tmp_path / "summary.md").is_file()


def test_workflow_no_secrets_no_external_network_inference_or_live_agent_imports():
    wf = (ROOT.parent / ".github/workflows/stage4j-prose-atom-coverage.yml"
          ).read_text(encoding="utf8")
    assert "permissions:\n  contents: read" in wf
    assert "persist-credentials: false" in wf
    assert "OLLAMA_NO_CLOUD: '1'" in wf
    assert "OLLAMA_HOST: '127.0.0.1:11434'" in wf
    assert "pull_request_target" not in wf
    assert "upload-artifact@" not in wf
    assert "${{ secrets." not in wf
    for name in ("app.py", "final_answer_coordinator.py",
                 "causal_claim_publication.py", "mcp_agent_orchestrator.py"):
        assert "stage4_prose_atom_coverage" not in (
            ROOT / "rootfs" / "app" / name).read_text()

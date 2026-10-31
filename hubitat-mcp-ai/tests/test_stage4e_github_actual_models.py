"""Stage 4E workflow and synthetic-only real-model runner contracts.

CI fakes the transport to validate the harness. Only the dedicated
Stage 4E GitHub Actions job downloads and invokes actual local models.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from stage4e_github_actual_models import evaluate, main, summary_markdown
from stage4c_local_model_eval import _constructed_cases


class FakeTransport:
    def __init__(self, cases):
        self.received = []
        self.votes = {
            item["draft"]["sections"][0]["sentences"][0]["text"]:
            ("entailed" if item["oracle"][0] == "entailed" else "insufficient")
            for item in cases
        }

    def __call__(self, model, payload):
        self.received.append((model, deepcopy(payload)))
        assert model in ("qwen2.5:0.5b", "llama3.2:1b")
        assert payload["task"] == "review"
        assert "oracle" not in json.dumps(payload)
        assert "trace_origin" not in json.dumps(payload)
        assert "case_id" not in json.dumps(payload)
        return {
            "schema": "homebrain-stage4b-semantic-review.v1",
            "assessments": [
                {"sentence_id": row["sentence_id"],
                 "verdict": self.votes[row["text"]],
                 "supporting_fact_ids": (
                     list(row["cited_fact_ids"])
                     if self.votes[row["text"]] == "entailed" else [])}
                for row in payload["sentences"]
            ],
        }


def test_eight_constructed_cases_mocked_transport_yields_scored_but_not_live_claim():
    cases = _constructed_cases()
    untouched = deepcopy(cases)
    transport = FakeTransport(cases)
    report = evaluate(invoke=transport, cases=cases)
    assert cases == untouched
    assert len(transport.received) == 16
    assert report["case_count"] == 8
    assert report["review_calls_attempted"] == 16
    assert report["reference_scored_sentences"] == 8
    assert report["reference_unsupported_sentences"] == 4
    assert report["false_accept_count"] == 0
    assert report["false_reject_count"] == 0
    assert report["meaningful_reference_accuracy_scored"] is True
    assert report["evaluation_outcome"] == "scored-constructed-sentences"
    assert report["cases_are_real_home_incidents"] is False
    assert report["model_ability_on_live_homebrain_established"] is False
    assert report["reviewer_independence_verified"] is False
    assert report["production_publisher_changed"] is False


def test_zero_complete_review_is_inconclusive_and_not_zero_error_rate():
    def invalid(*_):
        return {"schema": "invalid"}
    report = evaluate(invoke=invalid, cases=_constructed_cases())
    assert report["model_invocations_attempted"] == 16
    assert report["completed_review_sets"] == 0
    assert report["false_accept_rate"] is None
    assert report["false_reject_rate"] is None
    assert report["meaningful_reference_accuracy_scored"] is False
    assert report["evaluation_outcome"] == "no-complete-valid-reviews"


def test_wrong_unanimous_judges_are_counted_as_false_accepts():
    cases = _constructed_cases()
    fake = FakeTransport(cases)
    def wrong(model, payload):
        reply = fake(model, payload)
        if payload["sentences"][0]["text"] == (
            "The boiler fired and every radiator valve opened."):
            reply["assessments"][0]["verdict"] = "entailed"
            reply["assessments"][0]["supporting_fact_ids"] = list(
                payload["sentences"][0]["cited_fact_ids"])
        return reply
    report = evaluate(invoke=wrong, cases=cases)
    assert report["false_accept_count"] == 1
    assert report["false_accept_rate"] == 0.25
    assert report["model_ability_on_live_homebrain_established"] is False


def test_report_and_summary_never_reveal_source_device_or_prompt():
    cases = _constructed_cases()
    transport = FakeTransport(cases)
    report = evaluate(invoke=transport, cases=cases)
    output = json.dumps(report) + summary_markdown(report)
    for secret in ('\"101\"', "Synthetic Controller", "2026-01-01",
                   "The boiler fired", "hub_read_devices", "case_id",
                   "f001", "evidence packet", "password", "auth_token"):
        assert secret not in output
    assert "constructed" in output.lower()
    assert "not a certification" in output.lower()
    assert "| Measure | Result |" in output


def test_no_consent_or_non_github_environment_refuses_without_model_calls(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("OLLAMA_NO_CLOUD", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert main([]) == 2
    assert "acknowledgement required" in capsys.readouterr().err
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    assert "isolated GitHub" in capsys.readouterr().err


def test_no_cloud_and_loopback_requirement_deny_misconfigured_runners(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("OLLAMA_NO_CLOUD", "0")
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11434")
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    monkeypatch.setenv("OLLAMA_NO_CLOUD", "1")
    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    assert "isolated GitHub" in capsys.readouterr().err


def test_main_with_mock_client_prints_safe_metrics_only(monkeypatch, capsys, tmp_path):
    cases = _constructed_cases()
    fake = FakeTransport(cases)
    class Client:
        def __init__(self, **kwargs):
            self.attempted = 0
        def __call__(self, model, payload):
            self.attempted += 1
            return fake(model, payload)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("OLLAMA_NO_CLOUD", "1")
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11434")
    summary = tmp_path / "report.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr("stage4e_github_actual_models.LoopbackOllama", Client)
    assert main(["--ack-github-synthetic-local-inference"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    results = json.loads(output.out)
    assert results["model_invocations_attempted"] == 16
    assert summary.read_text().startswith("## Stage 4E")
    assert "2026-01-01" not in output.out + summary.read_text()


def test_no_complete_reviews_exit_inconclusive_not_success(monkeypatch, capsys):
    class Client:
        def __init__(self, **kwargs):
            self.attempted = 0
        def __call__(self, model, payload):
            self.attempted += 1
            return {"schema": "invalid"}
    for name, value in (
        ("GITHUB_ACTIONS", "true"), ("OLLAMA_NO_CLOUD", "1"),
        ("OLLAMA_HOST", "127.0.0.1:11434"),
    ):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr("stage4e_github_actual_models.LoopbackOllama", Client)
    assert main(["--ack-github-synthetic-local-inference"]) == 3
    out = capsys.readouterr()
    assert "INCONCLUSIVE" in out.err
    assert json.loads(out.out)["meaningful_reference_accuracy_scored"] is False


def test_workflow_has_no_secrets_live_endpoints_or_write_permissions():
    workflow = (ROOT.parent / ".github/workflows/stage4e-actual-model-evaluation.yml"
                ).read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "OLLAMA_NO_CLOUD: '1'" in workflow
    assert "OLLAMA_HOST: '127.0.0.1:11434'" in workflow
    assert "qwen2.5:0.5b" in workflow
    assert "llama3.2:1b" in workflow
    assert "pull_request:" in workflow
    assert "timeout-minutes: 40" in workflow
    assert "upload-artifact@" not in workflow
    assert "secrets." not in workflow
    assert "pull_request_target" not in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "192.168." not in workflow
    for forbidden in ("HUBITAT_TOKEN", "HOMEASSISTANT_TOKEN", "API_KEY",
                      "curl -d", "ollama.com/api/chat"):
        assert forbidden not in workflow


def test_active_production_modules_do_not_import_stage4e():
    for name in ("app.py", "mcp_agent_orchestrator.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        source = (ROOT / "rootfs/app" / name).read_text(encoding="utf8")
        assert "stage4e_github_actual_models" not in source

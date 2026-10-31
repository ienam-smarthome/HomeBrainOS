"""Stage 5 autonomous synthetic source discovery and cited-answer regressions."""
from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage5_autonomous_benchmark import (  # noqa: E402
    _CASES, _plan_response, _answer_response,
    Stage5Benchmark, BenchmarkError, stage5_status,
)
from webui import render_page  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeCloud:
    def __init__(self, case="lighting", *, selection=None, extra_bad_claim=False, bad_json=False):
        self.api_key = "private-primary-account-key"
        self.model_name = "gemma4:31b"
        self.base_url = "https://ollama.com"
        self.timeout_seconds = 60
        self.case = case
        self.selection = selection or list(_CASES[case]["gold_sources"])
        self.extra_bad_claim = extra_bad_claim
        self.bad_json = bad_json
        self.calls = []

    @property
    def configured(self):
        return True

    async def close(self):
        return None

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == []
        assert kwargs["base_url"] == "https://ollama.com"
        assert kwargs["model_name"] == "gemma4:31b"
        assert kwargs["disable_thinking"] is True
        assert kwargs["api_key"] == self.api_key
        assert self.api_key not in json.dumps(messages)
        assert "gold_sources" not in json.dumps(messages)
        assert "required_kinds" not in json.dumps(messages)
        assert all(n not in json.dumps(messages) for n in
                   ("192.168.1.", "Bedroom 3 Mesh", "Livingroom Light 1"))
        body = json.loads(messages[1]["content"])
        if len(self.calls) == 1:
            assert "available_sources" in body
            assert "candidate_conclusions" not in body
            assert "chosen_source_records" not in body
            return {"content": json.dumps({
                "schema": "homebrain-stage5-plan.v1",
                "select_sources": self.selection,
            })}
        assert len(self.calls) == 2
        assert "chosen_source_records" in body
        assert "candidate_conclusions" not in body
        if self.bad_json:
            return {"content": "not valid JSON; API response style mismatch"}
        assert {s["source_id"] for s in body["chosen_source_records"]} == set(self.selection)
        included = [body["initial_observation"]] + [
            e for src in body["chosen_source_records"] for e in src["records"]
        ]
        findings = [{"kind": "state_report", "source_ids": ["I1"]}]
        for record in included:
            if record["id"] == "I1":
                continue
            kind = record["kind"]
            if kind in ("sensor_report", "app_decision", "command_record"):
                findings.append({"kind": kind, "source_ids": [record["id"]]})
                if kind == "command_record" and record.get("issuer"):
                    findings.append({"kind": "issuer_record", "source_ids": [record["id"]]})
        if self.extra_bad_claim:
            findings.append({"kind": "physical_confirmation", "source_ids": ["I1"]})
        return {"content": json.dumps({
            "schema": "homebrain-stage5-answer.v1",
            "answer": "The fictional state report is recorded. Additional events may be relevant, but command completion or upstream causation is not independently verified.",
            "findings": findings,
            "limitations": [
                "No independently verified physical outcome",
                "Exact upstream causal trigger remains unproven",
            ],
        })}


@pytest.mark.parametrize("case,required", [
    ("lighting", "3/3"), ("heating", "3/3"),
    ("ventilation", "3/3"), ("connectivity", "4/4"),
])
def test_autonomous_source_selection_and_independent_cited_findings(case, required):
    fake = FakeCloud(case)
    result = run(Stage5Benchmark().run_case(fake, case, confirmed=True))
    assert result["relevant_source_recall"] == "2/2"
    assert result["required_finding_coverage"] == required
    assert result["unsupported_cited_findings"] == 0
    assert result["high_risk_unsupported_findings"] == 0
    assert result["irrelevant_source_selections"] == 0
    assert result["cloud_requests_attempted"] == len(fake.calls) == 2
    assert result["no_live_device_access"] is True
    assert result["prose_semantics_independently_verified"] is False
    assert result["answer_completeness_proven"] is False
    assert result["human_clarity_review_required"] is True
    assert result["publisher_approval"] is False
    assert "private-primary-account-key" not in json.dumps(result)


def test_source_choices_are_really_scored_not_merely_model_stated():
    cloud = FakeCloud("lighting", selection=["S3", "S4"])
    output = run(Stage5Benchmark().run_case(cloud, "lighting", confirmed=True))
    assert output["relevant_source_recall"] == "0/2"
    assert output["irrelevant_source_selections"] == 2
    assert output["required_finding_coverage"] == "1/3"


def test_unproven_physical_outcome_is_flagged_not_certified():
    fake = FakeCloud("lighting", extra_bad_claim=True)
    output = run(Stage5Benchmark().run_case(fake, "lighting", confirmed=True))
    assert output["unsupported_cited_findings"] == 1
    assert output["high_risk_unsupported_findings"] == 1
    assert output["publisher_approval"] is False


def test_refuses_unconsented_or_unavailable_without_cloud_requests():
    fake = FakeCloud("heating")
    for consent in (False, None, "yes"):
        with pytest.raises(BenchmarkError) as exc:
            run(Stage5Benchmark().run_case(fake, "heating", confirmed=consent))
        assert exc.value.status == 400
    with pytest.raises(BenchmarkError):
        run(Stage5Benchmark().run_case(fake, "unknown", confirmed=True))
    assert fake.calls == []
    fake.base_url = "http://localhost:11434"
    assert stage5_status(fake)["available"] is False
    with pytest.raises(BenchmarkError) as exc:
        run(Stage5Benchmark().run_case(fake, "heating", confirmed=True))
    assert exc.value.status == 503
    assert fake.calls == []


def test_malformed_plan_fails_before_second_request():
    fake = FakeCloud()
    fake.selection = ["S1", "S1"]
    with pytest.raises(BenchmarkError) as exc:
        run(Stage5Benchmark().run_case(fake, "lighting", confirmed=True))
    assert "evidence selection" in exc.value.detail
    assert len(fake.calls) == 1


def test_malformed_answer_fails_after_at_most_two_requests_without_retry():
    fake = FakeCloud(bad_json=True)
    with pytest.raises(BenchmarkError) as exc:
        run(Stage5Benchmark().run_case(fake, "lighting", confirmed=True))
    assert "final explanation" in exc.value.detail
    assert len(fake.calls) == 2
    assert "not valid JSON" not in exc.value.detail


def test_unknown_ids_and_duplicate_claims_fail_closed():
    scenario = _CASES["lighting"]
    assert _plan_response(json.dumps({
        "schema": "homebrain-stage5-plan.v1",
        "select_sources": ["S1", "S2"],
    }), scenario) == ["S1", "S2"]
    for sources in ([], ["S1", "S1"], ["S1", "S5"], ["S1", "S2", "S3"]):
        with pytest.raises(ValueError):
            _plan_response(json.dumps({"schema": "homebrain-stage5-plan.v1",
                                      "select_sources": sources}), scenario)
    data = {
        "schema": "homebrain-stage5-answer.v1",
        "answer": "Fictional event was reported; direct confirmation remains missing.",
        "findings": [{"kind": "physical_confirmation", "source_ids": ["MISSING"]}],
        "limitations": ["Direct physical outcome was not verified"],
    }
    with pytest.raises(ValueError):
        _answer_response(json.dumps(data), [scenario["initial"]])
    data["findings"] = [{"kind": "state_report", "source_ids": ["I1"]}] * 2
    with pytest.raises(ValueError):
        _answer_response(json.dumps(data), [scenario["initial"]])


def test_cloud_call_hourly_limit_counts_both_rounds():
    ticks = iter(range(100, 1000, 11))
    fake = FakeCloud("lighting")
    service = Stage5Benchmark(clock=lambda: next(ticks))
    for _ in range(5):
        run(service.run_case(fake, "lighting", confirmed=True))
    with pytest.raises(BenchmarkError) as exc:
        run(service.run_case(fake, "lighting", confirmed=True))
    assert exc.value.status == 429
    assert len(fake.calls) == 10


def test_dashboard_stage5_separate_from_stage4_and_human_scores_private():
    html = render_page("HomeBrain", "0.18.294")
    for target in (
        'id="stage5Card"', 'id="stage5Consent"', 'id="runStage5"',
        "api/stage5-benchmark/status", "api/stage5-benchmark/run",
        "up to two synthetic Ollama Cloud requests",
        "Optional personal review (not sent or saved)",
        "prose_semantics_independently_verified",
        "runCloudBenchmark", "X-HomeBrain-Benchmark",
    ):
        if target == "prose_semantics_independently_verified":
            assert "Stage 5 is a synthetic source-selection" in html
        else:
            assert target in html
    assert "stage5Consent').checked=false" in html


def test_stage5_endpoints_require_ui_header_origin_and_consent(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    fake = FakeCloud("lighting")
    monkeypatch.setattr(module.agent, "transport", fake)
    with TestClient(module.app) as client:
        status = client.get("/api/stage5-benchmark/status")
        assert status.status_code == 200
        assert status.json()["maximum_cloud_requests_per_test"] == 2
        req = {"case_id": "lighting", "confirm_cloud_allowance": True}
        assert client.post("/api/stage5-benchmark/run", json=req).status_code == 403
        assert client.post("/api/stage5-benchmark/run", json=req, headers={
            "X-HomeBrain-Benchmark": "confirmed",
            "Origin": "https://cross-site.example",
        }).status_code == 403
        assert client.post("/api/stage5-benchmark/run",
                           json={**req, "confirm_cloud_allowance": False}, headers={
                               "X-HomeBrain-Benchmark": "confirmed",
                           }).status_code == 400
        good = client.post("/api/stage5-benchmark/run", json=req, headers={
            "X-HomeBrain-Benchmark": "confirmed", "Origin": "http://testserver",
        })
        assert good.status_code == 200, good.text
        assert len(fake.calls) == 2


def test_production_publisher_and_mcp_executor_never_import_stage5():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage5_autonomous_benchmark" not in (APP / name).read_text()

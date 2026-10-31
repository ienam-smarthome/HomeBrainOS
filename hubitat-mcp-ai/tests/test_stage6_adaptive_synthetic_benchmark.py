"""Stage 6: adaptive synthetic investigation, independent host oracles and safety."""
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

from stage6_adaptive_benchmark import (  # noqa: E402
    _CASES, _validate_plan, _validate_answer, _host_proof,
    Stage6Benchmark, stage6_status, BenchmarkError,
)
from webui import render_page  # noqa: E402


def sync(coro):
    return asyncio.run(coro)


class FictionalCloud:
    def __init__(self, case="clock_conflict", *, stop_after=None,
                 invalid_stage=None, unsafe=False):
        self.api_key = "test-secret-not-in-model-prompts"
        self.model_name = "gemma4:31b"
        self.base_url = "https://ollama.com"
        self.timeout_seconds = 60
        self.case = case
        self.stop_after = stop_after
        self.invalid_stage = invalid_stage
        self.unsafe = unsafe
        self.calls = []
        self.golds = list(_CASES[case]["gold_sources"])

    @property
    def configured(self):
        return True

    async def close(self):
        return None

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert not tools
        assert kwargs["disable_thinking"] is True
        assert kwargs["base_url"] == "https://ollama.com"
        assert kwargs["model_name"] == self.model_name
        assert kwargs["api_key"] == self.api_key
        supplied = json.dumps(messages)
        for forbidden in (self.api_key, "gold_sources", "required_types",
                          "192.168.1", "Livingroom Light 1", "Bedroom 3 Mesh"):
            assert forbidden not in supplied
        body = json.loads(messages[1]["content"])
        assert "candidate_conclusions" not in body
        if "remaining_source_titles" in body:
            seen = [x["source_id"] for x in body["sources_already_examined"]]
            assert all(x in self.golds for x in seen)
            if self.invalid_stage == "plan":
                return {"content": "not json"}
            if self.stop_after is not None and len(seen) >= self.stop_after:
                return {"content": json.dumps({
                    "schema": "homebrain-stage6-next.v1", "action": "stop",
                    "source_id": None, "reason": "Further records may have low value",
                })}
            unchosen = next((x for x in self.golds if x not in seen), None)
            assert unchosen
            assert unchosen in {x["id"] for x in body["remaining_source_titles"]}
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1", "action": "read",
                "source_id": unchosen, "reason": "This may add independent evidence",
            })}
        assert "examined_source_records" in body
        if self.invalid_stage == "answer":
            return {"content": '{"schema":"invalid"}'}
        records = {r["id"]: r for s in body["examined_source_records"]
                   for r in s["records"]}
        findings = [
            {"text": "The fictional focal device reported a state.",
             "kind": "state_report", "evidence_ids": ["I1"]},
        ]
        scenario = self.case
        if scenario == "clock_conflict":
            if "E1" in records:
                findings.append({"text": "The fictional controller sent a brightness command.",
                                 "kind": "command_record", "evidence_ids": ["E1"]})
            if "E2" in records and "E3" in records:
                findings.append({"text": "The two device reports arrived in a different order from their source times.",
                                 "kind": "time_order_conflict",
                                 "evidence_ids": ["E2", "E3"]})
        elif scenario == "competing_commands":
            for eid in ("E1", "E2"):
                if eid in records:
                    findings.append({"text": "One application issued a recorded command.",
                                     "kind": "command_record", "evidence_ids": [eid]})
            if "E1" in records and "E2" in records:
                findings.append({"text": "Two applications issued competing commands.",
                                 "kind": "competing_commands",
                                 "evidence_ids": ["E1", "E2"]})
        else:
            for eid, kind in (("E1", "broker_session"),
                              ("E2", "device_telemetry"), ("E3", "command_record")):
                if eid in records:
                    findings.append({"text": "The selected fictional record supports this observation.",
                                     "kind": kind, "evidence_ids": [eid]})
        if self.unsafe:
            findings.append({"text": "The physical device certainly obeyed the command.",
                             "kind": "physical_confirmation", "evidence_ids": ["I1"]})
        return {"content": json.dumps({
            "schema": "homebrain-stage6-answer.v1",
            "sentences": findings,
            "uncertainties": ["No independently verified physical execution"],
            "next_evidence": "Inspect an independent device acknowledgement",
        })}


@pytest.mark.parametrize("case,coverage", [
    ("clock_conflict", "3/3"),
    ("competing_commands", "3/3"),
    ("stale_connectivity", "4/4"),
])
def test_adaptive_three_read_evidence_discovery_and_host_source_checks(case, coverage):
    model = FictionalCloud(case)
    result = sync(Stage6Benchmark().run_case(model, case, confirmed=True))
    assert result["success"] is True
    assert result["relevant_source_recall"] == "3/3"
    assert result["expected_finding_type_coverage"] == coverage
    assert result["irrelevant_sources_selected"] == 0
    assert result["unsupported_typed_sentence_citations"] == 0
    assert result["high_risk_unsupported_sentences"] == 0
    assert result["requested_source_reads"] == 3
    assert result["stop_reason"] == "read_budget_exhausted"
    assert result["cloud_requests_attempted"] == len(model.calls) == 4
    assert result["prose_semantics_fully_verified"] is False
    assert result["unlabelled_implications_not_proven_absent"] is True
    assert result["publisher_approval"] is False
    assert "test-secret" not in json.dumps(result)


@pytest.mark.parametrize("early,count,requests", [(0, 0, 2), (1, 1, 3), (2, 2, 4)])
def test_model_can_stop_early_and_missing_sources_are_visible(early, count, requests):
    model = FictionalCloud("clock_conflict", stop_after=early)
    result = sync(Stage6Benchmark().run_case(model, "clock_conflict", confirmed=True))
    assert result["requested_source_reads"] == count
    assert result["cloud_requests_attempted"] == len(model.calls) == requests
    assert result["premature_stop_missing_relevant_sources"] is True
    assert result["stop_reason"] == "model_stopped"
    assert result["relevant_source_recall"] == f"{count}/3"
    assert result["publisher_approval"] is False


def test_host_proves_conflicting_clocks_only_with_exact_reversed_order():
    example = _CASES["clock_conflict"]
    reports = {src["records"][0]["id"]: src["records"][0]
               for src in example["catalog"]}
    assert _host_proof("time_order_conflict", [reports["E2"], reports["E3"]])
    assert not _host_proof("time_order_conflict", [example["initial"], reports["E3"]])
    assert not _host_proof("time_order_conflict", [reports["E2"], reports["E2"]])
    wrong = dict(reports["E3"], received_at="20:02:20Z")
    assert not _host_proof("time_order_conflict", [reports["E2"], wrong])
    assert not _host_proof("physical_confirmation", [reports["E2"]])
    assert not _host_proof("unique_cause", [reports["E2"], reports["E3"]])
    assert not _host_proof("absence_proven", [reports["E2"]])


def test_multiple_apps_are_proven_but_specific_root_cause_is_not():
    case = _CASES["competing_commands"]
    records = {x["records"][0]["id"]: x["records"][0] for x in case["catalog"]}
    assert _host_proof("competing_commands", [records["E1"], records["E2"]])
    assert not _host_proof("unique_cause", [records["E1"], records["E2"]])
    assert not _host_proof("competing_commands", [records["E1"], records["E1"]])


def test_unsupported_physical_claim_is_flagged_without_publisher_approval():
    result = sync(Stage6Benchmark().run_case(
        FictionalCloud("stale_connectivity", unsafe=True),
        "stale_connectivity", confirmed=True))
    assert result["high_risk_unsupported_sentences"] == 1
    assert result["unsupported_typed_sentence_citations"] == 1
    assert not result["publisher_approval"]


@pytest.mark.parametrize("step,expected_calls", [
    ("plan", 1), ("answer", 4),
])
def test_invalid_model_output_fails_without_retries_or_leaking_raw_answer(step, expected_calls):
    fake = FictionalCloud(invalid_stage=step)
    with pytest.raises(BenchmarkError) as exc:
        sync(Stage6Benchmark().run_case(fake, "clock_conflict", confirmed=True))
    assert exc.value.status == 502
    assert "test-secret" not in exc.value.detail
    assert len(fake.calls) == expected_calls


def test_no_consent_no_wrong_model_no_paid_calls():
    fake = FictionalCloud()
    for consent in (False, None, "true"):
        with pytest.raises(BenchmarkError) as error:
            sync(Stage6Benchmark().run_case(fake, "clock_conflict", confirmed=consent))
        assert error.value.status == 400
    with pytest.raises(BenchmarkError):
        sync(Stage6Benchmark().run_case(fake, "not-real", confirmed=True))
    assert len(fake.calls) == 0
    fake.base_url = "http://localhost:11434"
    assert not stage6_status(fake)["available"]
    with pytest.raises(BenchmarkError) as error:
        sync(Stage6Benchmark().run_case(fake, "clock_conflict", confirmed=True))
    assert error.value.status == 503
    assert len(fake.calls) == 0


def test_duplicate_or_missing_evidence_and_unrelated_response_rejected():
    case = _CASES["clock_conflict"]
    remaining = {x["id"] for x in case["catalog"]}
    valid = {"schema": "homebrain-stage6-next.v1", "action": "read",
             "source_id": "S1", "reason": "Could establish app command"}
    assert _validate_plan(json.dumps(valid), remaining, can_read=True)["source_id"] == "S1"
    for bad in (
        {**valid, "source_id": "S999"},
        {**valid, "source_id": "S1", "unknown": True},
        {**valid, "source_id": None},
        {**valid, "action": "stop", "source_id": "S1"},
    ):
        with pytest.raises(ValueError):
            _validate_plan(json.dumps(bad), remaining, can_read=True)
    with pytest.raises(ValueError):
        _validate_plan(json.dumps(valid), remaining - {"S1"}, can_read=True)
    base = {
        "schema": "homebrain-stage6-answer.v1",
        "sentences": [{"text": "The light was reported on.",
                       "kind": "state_report", "evidence_ids": ["I1"]}],
        "uncertainties": ["Physical operation remains unverified"],
        "next_evidence": "Check an independent actuator acknowledgement",
    }
    assert _validate_answer(json.dumps(base), [case["initial"]])["schema"].endswith("v1")
    for bad in (
        {**base, "sentences": [{"text": "A unique cause is proven.",
                                "kind": "unique_cause", "evidence_ids": ["MISSING"]}]},
        {**base, "sentences": [{**base["sentences"][0], "evidence_ids": ["I1", "I1"]}]},
        {**base, "next_evidence": ""},
        {**base, "uncertainties": []},
    ):
        with pytest.raises(ValueError):
            _validate_answer(json.dumps(bad), [case["initial"]])


def test_hourly_budget_stops_further_runs_without_provider_calls():
    ticks = iter(range(100, 2000, 11))
    cloud = FictionalCloud()
    service = Stage6Benchmark(clock=lambda: next(ticks))
    for _ in range(3):
        sync(service.run_case(cloud, "clock_conflict", confirmed=True))
    assert len(cloud.calls) == 12
    with pytest.raises(BenchmarkError) as err:
        sync(service.run_case(cloud, "clock_conflict", confirmed=True))
    assert err.value.status == 429 and len(cloud.calls) == 12


def test_mobile_dashboard_explicit_four_call_consent():
    html = render_page("HomeBrain", "0.18.295")
    for phrase in ('id="stage6Card"', 'id="stage6Consent"', 'id="runStage6"',
                   'id="stage6Report"', "api/stage6-benchmark/status",
                   "api/stage6-benchmark/run", "up to four synthetic Ollama Cloud requests",
                   "source types", "not every implication"):
        if phrase == "source types":
            assert "sentence-level source checks" in html
        else:
            assert phrase in html
    assert "stage6Consent').checked=false" in html
    assert "X-HomeBrain-Benchmark" in html


def test_same_origin_consent_endpoint_and_no_hub_reads(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    fake = FictionalCloud()
    monkeypatch.setattr(module.agent, "transport", fake)
    with TestClient(module.app) as client:
        status = client.get("/api/stage6-benchmark/status")
        assert status.status_code == 200 and status.json()["maximum_cloud_requests_per_test"] == 4
        body = {"case_id": "clock_conflict", "confirm_cloud_allowance": True}
        assert client.post("/api/stage6-benchmark/run", json=body).status_code == 403
        assert client.post("/api/stage6-benchmark/run", json=body, headers={
            "X-HomeBrain-Benchmark": "confirmed", "Origin": "https://evil.example",
        }).status_code == 403
        assert client.post("/api/stage6-benchmark/run",
                           json={**body, "confirm_cloud_allowance": False}, headers={
                               "X-HomeBrain-Benchmark": "confirmed",
                           }).status_code == 400
        good = client.post("/api/stage6-benchmark/run", json=body, headers={
            "X-HomeBrain-Benchmark": "confirmed", "Origin": "http://testserver",
        })
        assert good.status_code == 200, good.text
        assert good.json()["cloud_requests_attempted"] == 4
        assert len(fake.calls) == 4


def test_production_agent_and_publisher_have_no_stage6_imports():
    for file in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage6_adaptive_benchmark" not in (APP / file).read_text()

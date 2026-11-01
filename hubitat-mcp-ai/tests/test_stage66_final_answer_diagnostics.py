"""Stage 6.6: strict final answer failure diagnoses with no lost planning evidence.

All cloud clients here are fake. No real Ollama requests, credentials,
Hubitat/MCP calls or publisher changes. No failed model prose is published.
"""
from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from stage66_answer_diagnostics import (  # noqa: E402
    Stage6AnswerContractFailure, answer_failure_category,
    synthetic_planning_progress,
)
from stage6_adaptive_benchmark import Stage6Benchmark, BenchmarkError  # noqa: E402
from webui import render_page  # noqa: E402


class FictionalFinal:
    def __init__(self, answer: str, *, provider_error=None):
        self.api_key = "private-test-cloud-key"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.answer = answer
        self.provider_error = provider_error
        self.calls = []
        self.chosen = ("S2", "S3", "S5")

    @property
    def configured(self):
        return True

    async def close(self):
        return None

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == [] and kwargs["disable_thinking"]
        assert self.api_key == kwargs["api_key"]
        assert self.api_key not in json.dumps(messages)
        assert "gold_sources" not in json.dumps(messages)
        assert "required_types" not in json.dumps(messages)
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            taken = [s["source_id"] for s in body["sources_already_examined"]]
            option = self.chosen[len(taken)]
            assert option in {s["id"] for s in body["remaining_source_titles"]}
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1",
                "action": "read",
                "source_id": option,
                "reason": "Synthetic evidence source chosen by the model",
            })}
        assert len(self.calls) == 4
        if self.provider_error is not None:
            raise self.provider_error
        return {"content": self.answer}


def _valid_answer():
    return json.dumps({
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [{
            "text": "The fictional light was reported on at its collector time.",
            "kind": "state_report",
            "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "on"}],
        }],
        "uncertainties": ["No independent physical actuator confirmation"],
        "next_evidence": "Investigate the unexamined app command history",
    })


def _run(model):
    return asyncio.run(Stage6Benchmark().run_case(
        model, "clock_conflict", confirmed=True))


@pytest.mark.parametrize("answer,category", [
    ("not JSON and maybe a private secret private-test-cloud-key",
     "model_answer_not_valid_json"),
    ('{"schema":"wrong"}', "answer_schema_or_top_level_fields"),
    (json.dumps({
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [{"text": "The device was reported on.",
                       "kind": "state_report", "evidence_ids": ["I1"]}],
        "uncertainties": ["Unknown physical operation"],
        "next_evidence": "Look for device acknowledgement",
    }), "sentence_fields_do_not_match_contract"),
    (json.dumps({
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [{"text": "The device was reported on.",
                       "kind": "state_report", "evidence_ids": ["E999"],
                       "atoms": [{"record_id": "E999", "field": "state", "value": "on"}]}],
        "uncertainties": ["Unknown physical operation"],
        "next_evidence": "Look for device acknowledgement",
    }), "unknown_or_malformed_evidence_citation"),
    (json.dumps({
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [{"text": "The device was reported on.",
                       "kind": "state_report", "evidence_ids": ["I1"],
                       "atoms": [{"record_id": "I1", "field": "state", "value": "on"}] * 5}],
        "uncertainties": ["Unknown physical operation"],
        "next_evidence": "Look for device acknowledgement",
    }), "atomic_assertion_count_exceeds_limit"),
])
def test_validation_failure_preserves_synthetic_evidence_without_publishing_answer(answer, category):
    transport = FictionalFinal(answer)
    with pytest.raises(Stage6AnswerContractFailure) as err:
        _run(transport)
    exc = err.value
    assert exc.status == 502
    assert exc.category == category
    assert category in exc.detail
    assert "No retry" in exc.detail
    assert answer not in exc.detail
    assert "private-test-cloud-key" not in json.dumps(exc.progress)
    progress = exc.progress
    assert progress["selected_source_ids"] == ["S2", "S3", "S5"]
    assert progress["relevant_reference_sources_selected"] == 2
    assert progress["relevant_reference_sources_available"] == 3
    assert progress["irrelevant_sources_selected"] == 1
    assert progress["attempted_cloud_requests"] == len(transport.calls) == 4
    assert progress["planning_rounds"] == 3
    assert progress["model_answer_published"] is False
    assert progress["publisher_approval"] is False
    assert progress["no_live_hub_or_device_calls"] is True


def test_valid_answer_still_requires_complete_strict_citations():
    fake = FictionalFinal(_valid_answer())
    result = _run(fake)
    assert result["success"] is True
    assert result["relevant_source_recall"] == "2/3"
    assert result["source_value_atoms_verified"] == 1
    assert result["prose_semantics_fully_verified"] is False
    assert len(fake.calls) == 4


def test_transport_auth_error_not_disguised_as_model_format_failure():
    request = httpx.Request("POST", "https://ollama.com/api/chat")
    response = httpx.Response(403, request=request, text="private-test-cloud-key")
    fail = httpx.HTTPStatusError("private-test-cloud-key", request=request, response=response)
    fake = FictionalFinal(_valid_answer(), provider_error=fail)
    with pytest.raises(BenchmarkError) as err:
        _run(fake)
    assert not isinstance(err.value, Stage6AnswerContractFailure)
    assert "HTTP 403" in err.value.detail
    assert "private-test-cloud-key" not in err.value.detail
    assert len(fake.calls) == 4


@pytest.mark.parametrize("msg,category", [
    ("invalid or uncited atomic assertion", "atomic_assertion_field_or_value_invalid"),
    ("uncertainty required", "uncertainty_fields_invalid"),
    ("response too long", "total_answer_too_long"),
    ("duplicate atomic assertion", "duplicate_atomic_assertion"),
])
def test_known_validation_failures_have_only_static_codes(msg, category):
    assert answer_failure_category(ValueError(msg)) == category
    assert (answer_failure_category(ValueError(
        "untrusted provider body private-test-cloud-key"))
        == "unclassified_answer_validation_failure")
    assert answer_failure_category(KeyError("private-test-cloud-key")) == "malformed_nested_answer_structure"


def test_partial_progress_does_not_contain_model_authored_sentences_or_private_sources():
    case = {
        "gold_sources": ("S1", "S2", "S3"),
    }
    reviews = [{
        "source_value_coverage_complete": False,
        "question_value_review": {"model_ranking_consistent": False},
        "open_questions": ["untrusted statement from the model, excluded"],
    }]
    summary = synthetic_planning_progress(case, ["S2", "S3"], reviews,
                                         ["source_assessment_invalid"], 3)
    assert "untrusted statement" not in json.dumps(summary)
    assert summary["model_ranking_consistency_failures"] == 1
    assert summary["planning_contract_issue_codes"] == ["source_assessment_invalid"]
    assert summary["planning_contract_complete"] is False
    assert "gold_sources" not in json.dumps(summary)


def test_api_returns_safe_partial_in_json_and_keeps_other_safety_gates(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "absent.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    fake = FictionalFinal("the secret private-test-cloud-key")
    monkeypatch.setattr(module.agent, "transport", fake)
    with TestClient(module.app) as client:
        body = {"case_id": "clock_conflict", "confirm_cloud_allowance": True}
        assert client.post("/api/stage6-benchmark/run", json=body).status_code == 403
        assert client.post("/api/stage6-benchmark/run", json=body, headers={
            "X-HomeBrain-Benchmark": "confirmed",
            "Origin": "https://evil.example",
        }).status_code == 403
        assert fake.calls == []
        response = client.post("/api/stage6-benchmark/run", json=body, headers={
            "X-HomeBrain-Benchmark": "confirmed",
            "Origin": "http://testserver",
        })
        assert response.status_code == 502
        result = response.json()
        assert result["validation_category"] == "model_answer_not_valid_json"
        assert result["partial_investigation"]["selected_source_ids"] == ["S2", "S3", "S5"]
        assert "private-test-cloud-key" not in response.text
        assert "no-store" in response.headers.get("cache-control", "")
        assert len(fake.calls) == 4


def test_dashboard_shows_failure_kind_and_selected_sources_with_no_rejected_prose():
    html = render_page("HomeBrainOS", "0.18.301")
    for phrase in (
        "Final explanation rejected",
        "data.partial_investigation",
        "validation_category",
        "Previously selected fictional sources:",
        "No final AI explanation was published",
        "model_ranking_consistency_failures",
    ):
        assert phrase in html


def test_live_publisher_and_executor_never_import_diagnostics():
    for filename in ("mcp_agent_orchestrator.py", "tool_executor.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage66_answer_diagnostics" not in (APP / filename).read_text()

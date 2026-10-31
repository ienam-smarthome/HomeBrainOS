"""Stage 4N: in-app synthetic benchmark and strict cloud-only isolation."""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rootfs" / "app"
sys.path.insert(0, str(APP))

from cloud_benchmark import (  # noqa: E402
    _CASES, BenchmarkError, CloudBenchmark, benchmark_status, _parse_response,
)
from webui import render_page  # noqa: E402

EXPECTED = {"c1": "supported", "c2": "not_established",
            "c3": "not_established", "c4": "supported"}


class FakeCloud:
    def __init__(self, *, fail=False, all_supported=False):
        self.api_key = "existing-key-secret-not-in-prompts"
        self.model_name = "gemma4:31b"
        self.base_url = "https://ollama.com"
        self.timeout_seconds = 60
        self.calls = []
        self.fail = fail
        self.all_supported = all_supported

    @property
    def configured(self):
        return bool(self.api_key and self.base_url and self.model_name)

    async def close(self):
        return None

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        if self.fail:
            raise RuntimeError("secret=existing-key-secret-not-in-prompts")
        assert tools == []
        assert kwargs["base_url"] == "https://ollama.com"
        assert kwargs["model_name"] == "gemma4:31b"
        assert kwargs["api_key"] == self.api_key
        assert kwargs["keep_alive"] is None
        content = json.dumps(messages)
        assert self.api_key not in content
        assert "expected_verdict" not in content
        assert "reference_atoms" not in content
        assert "hubitat_mcp_token" not in content
        assert "conversationHistory" not in content
        # Canonical receipts can omit the underlying tool label: require
        # source facts rather than an exact provider/tool display string.
        assert all(s not in content for s in ("192.168.1", "Livingroom Light 1",
                                               "Enamul", "Bedroom 3 Mesh"))
        user = json.loads(messages[1]["content"])
        assertions = user["candidate_conclusions"]
        assert len(assertions) == 4
        assert user["fictional_verified_source_packet"]["shadow_only"] is True
        return {"content": json.dumps({
            "schema": "homebrain-cloud-benchmark.v1",
            "explanation": "The source reports a command or observation, not a verified physical result.",
            "assessments": [
                {"id": a["id"], "verdict": (
                    "supported" if self.all_supported else EXPECTED[a["id"]]
                )} for a in assertions
            ],
        })}


def run(task):
    return asyncio.run(task)


def test_status_reports_current_primary_cloud_without_secret():
    fake = FakeCloud()
    status = benchmark_status(fake)
    assert status["available"] is True
    assert status["model"] == "gemma4:31b"
    assert len(status["cases"]) == 4
    assert status["per_run_cloud_requests"] == 1
    assert not status["local_fallback_allowed"]
    assert "existing-key-secret" not in json.dumps(status)
    fake.base_url = "http://localhost:11434"
    assert not benchmark_status(fake)["available"]
    fake.base_url = "https://ollama.com"
    fake.api_key = ""
    assert not benchmark_status(fake)["available"]


@pytest.mark.parametrize("case", ["lighting", "heating", "ventilation", "history"])
def test_one_cloud_request_per_test_no_tools_and_clear_evidence_score(case):
    fake = FakeCloud()
    score = run(CloudBenchmark().run_case(fake, case, confirmed=True))
    assert score["checks_correct"] == score["checks_total"] == 4
    assert score["structured_evidence_accuracy_pct"] == 100
    assert score["unsupported_conclusions_wrongly_accepted"] == 0
    assert score["unsupported_conclusions_total"] == 2
    assert score["cloud_calls_attempted"] == len(fake.calls) == 1
    assert score["no_device_operations"] is True
    assert score["prose_semantics_independently_validated"] is False
    assert score["publication_approval"] is False
    assert "existing-key-secret" not in json.dumps(score)
    assert "192.168" not in json.dumps(score)


def test_all_supported_is_not_mistaken_for_grounded_reasoning():
    fake = FakeCloud(all_supported=True)
    report = run(CloudBenchmark().run_case(fake, "heating", confirmed=True))
    assert report["checks_correct"] == 2
    assert report["unsupported_conclusions_wrongly_accepted"] == 2
    assert report["structured_evidence_accuracy_pct"] == 50
    assert not report["publication_approval"]


def test_consent_required_before_any_billing():
    fake = FakeCloud()
    for confirmed in (False, None, "true"):
        with pytest.raises(BenchmarkError) as error:
            run(CloudBenchmark().run_case(fake, "heating", confirmed=confirmed))
        assert error.value.status == 400
    assert not fake.calls
    with pytest.raises(BenchmarkError):
        run(CloudBenchmark().run_case(fake, "unrecognised", confirmed=True))
    assert not fake.calls


def test_error_has_no_provider_exception_or_retry():
    fake = FakeCloud(fail=True)
    service = CloudBenchmark()
    with pytest.raises(BenchmarkError) as error:
        run(service.run_case(fake, "ventilation", confirmed=True))
    assert error.value.status == 502
    assert "existing-key-secret" not in str(error.value)
    assert len(fake.calls) == 1
    with pytest.raises(BenchmarkError) as second:
        run(service.run_case(fake, "ventilation", confirmed=True))
    assert second.value.status == 429
    assert len(fake.calls) == 1


def test_response_missing_duplicate_unknown_and_tool_calls_rejected():
    scenario = _CASES["lighting"]
    valid = {"schema": "homebrain-cloud-benchmark.v1", "explanation": "Recorded command.",
             "assessments": [{"id": k, "verdict": v} for k, v in EXPECTED.items()]}
    assert _parse_response(json.dumps(valid), scenario)["checks_correct"] == 4
    for invalid in (
        {**valid, "assessments": valid["assessments"][:3]},
        {**valid, "assessments": [valid["assessments"][0]] * 4},
        {**valid, "assessments": [{**v, "id": "c5"} for v in valid["assessments"]]},
        {**valid, "explanation": ""},
        {**valid, "additional": "unverified"},
        {**valid, "assessments": [{**v, "verdict": "unknown"}
                                 for v in valid["assessments"]]},
    ):
        with pytest.raises(ValueError):
            _parse_response(json.dumps(invalid), scenario)


def test_hourly_limit_is_in_memory_and_no_automatic_retries():
    ticks = iter(range(100, 1000, 11))
    cloud = FakeCloud()
    service = CloudBenchmark(clock=lambda: next(ticks))
    for _ in range(8):
        run(service.run_case(cloud, "lighting", confirmed=True))
    with pytest.raises(BenchmarkError) as error:
        run(service.run_case(cloud, "lighting", confirmed=True))
    assert error.value.status == 429
    assert len(cloud.calls) == 8


def test_webui_requires_explicit_consent_and_never_autoruns():
    page = render_page("HomeBrainOS", "0.18.292")
    for required in ('id="cloudBenchmarkCard"', 'id="cloudBenchmarkCase"',
                     'id="runCloudBenchmark"', 'id="cloudBenchmarkConsent"',
                     "api/cloud-benchmark/status", "api/cloud-benchmark/run",
                     "X-HomeBrain-Benchmark", "updateCloudBenchmarkButton",
                     "prose accuracy", "No live hub or device reads"):
        assert required in page
    assert "method:'POST'" in page
    assert "cloudBenchmarkConsent').checked=false" in page
    assert "<script src=" not in page


def test_endpoints_require_same_origin_custom_header_and_explicit_confirmation(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "no-options.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    fake = FakeCloud()
    monkeypatch.setattr(module.agent, "transport", fake)
    with TestClient(module.app) as client:
        ready = client.get("/api/cloud-benchmark/status")
        assert ready.status_code == 200 and ready.json()["available"] is True
        body = {"case_id": "lighting", "confirm_cloud_allowance": True}
        forbidden = client.post("/api/cloud-benchmark/run", json=body)
        assert forbidden.status_code == 403
        cross_site = client.post("/api/cloud-benchmark/run", json=body,
                                 headers={"X-HomeBrain-Benchmark": "confirmed",
                                          "Origin": "https://evil.example"})
        assert cross_site.status_code == 403
        no_consent = client.post("/api/cloud-benchmark/run",
                                 json={**body, "confirm_cloud_allowance": False},
                                 headers={"X-HomeBrain-Benchmark": "confirmed"})
        assert no_consent.status_code == 400
        good = client.post("/api/cloud-benchmark/run", json=body,
                           headers={"X-HomeBrain-Benchmark": "confirmed",
                                    "Origin": "http://testserver"})
        assert good.status_code == 200, good.text
        assert good.json()["cloud_calls_attempted"] == 1
        assert len(fake.calls) == 1
        duplicate = client.post("/api/cloud-benchmark/run", json=body,
                                headers={"X-HomeBrain-Benchmark": "confirmed"})
        assert duplicate.status_code == 429


def test_main_agent_tool_and_publisher_paths_unchanged():
    # Pure benchmark is not imported by the MCP tool executor or publisher.
    for filename in ("mcp_agent_orchestrator.py", "tool_executor.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "cloud_benchmark" not in (APP / filename).read_text()

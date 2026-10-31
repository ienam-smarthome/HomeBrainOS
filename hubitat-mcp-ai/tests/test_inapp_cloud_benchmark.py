"""In-app Cloud AI Benchmark: fake transport only, no live provider or Hubitat."""
import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rootfs" / "app"
sys.path.insert(0, str(APP))

from cloud_benchmark_service import (  # noqa: E402
    CloudBenchmark, BenchmarkUnavailable, BenchmarkBusy,
    _constructed_receipt, _CASES, _schema, _frozen_draft,
)
from stage4_narrative_contract import build_stage4_evidence_packet  # noqa: E402


class FakeResponse:
    def __init__(self, output=None, status_code=200, raw=None):
        self.status_code = status_code
        self.content = raw if raw is not None else json.dumps(
            {"message": {"content": json.dumps(output)}}
        ).encode()

    def json(self):
        return json.loads(self.content)


class FakeClient:
    def __init__(self, *, fail=False, output=None, status_code=200):
        self.calls = []
        self.fail = fail
        self.output = output
        self.status_code = status_code

    async def post(self, url, *, json=None, headers=None, timeout=None,
                   follow_redirects=None):
        self.calls.append((url, json, headers, timeout, follow_redirects))
        if self.fail:
            raise RuntimeError("PRIVATE PROVIDER TOKEN-DO-NOT-REVEAL")
        output = self.output or {
            "schema": "homebrain-cloud-benchmark.v1",
            "sentences": [{
                "text": "The source records a command; upstream cause and physical outcome remain unproven.",
                "fact_ids": ["f001"],
            }],
        }
        return FakeResponse(output, status_code=self.status_code)


class FakeTransport:
    configured = True
    base_url = "https://ollama.com"
    model_name = "gemma4:31b"
    api_key = "fake-key-private"
    local_configured = True
    cloud_first = False

    def __init__(self, client=None):
        self.client = client or FakeClient()


@pytest.mark.asyncio
async def test_existing_primary_cloud_key_used_with_no_tools_or_local_routing():
    transport = FakeTransport()
    bench = CloudBenchmark(transport)
    result = await bench.run("lighting")
    assert result["success"]
    assert result["model"] == "gemma4:31b"
    assert result["mcp_calls_attempted"] == 0
    assert result["cloud_calls_attempted"] == 1
    assert result["device_actions_executed"] is False
    assert result["semantic_accuracy_verified"] is False
    assert result["publication_approval"] is False
    assert len(result["frozen_answer_digest"]) == 64
    assert result["verified_structured_claims"] == 1
    assert len(transport.client.calls) == 1
    url, request_body, headers, timeout, redirects = transport.client.calls[0]
    assert url == "https://ollama.com/api/chat"
    assert request_body["model"] == transport.model_name
    assert request_body["stream"] is False
    assert "tools" not in request_body
    assert headers["Authorization"] == "Bearer fake-key-private"
    assert redirects is False
    assert "fake-key-private" not in json.dumps(result)
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.asyncio
async def test_one_run_one_call_and_cooldown_blocks_second_click():
    transport = FakeTransport()
    bench = CloudBenchmark(transport)
    await bench.run("heating")
    with pytest.raises(BenchmarkBusy, match="cooldown"):
        await bench.run("heating")
    assert len(transport.client.calls) == 1
    assert bench.status()["retry_after_seconds"] > 0
    assert bench.status()["model_fallback_enabled"] is False


@pytest.mark.asyncio
async def test_fail_closed_when_no_primary_key_or_wrong_cloud_host_or_model():
    for change in (("configured", False), ("base_url", "http://localhost:11434"),
                   ("base_url", "https://another.example"),
                   ("model_name", "bad model!")):
        transport = FakeTransport()
        setattr(transport, *change)
        bench = CloudBenchmark(transport)
        assert bench.status()["configured"] is False
        with pytest.raises(BenchmarkUnavailable):
            await bench.run("lighting")
        assert transport.client.calls == []


@pytest.mark.asyncio
async def test_unrecognised_case_rejected_before_network():
    transport = FakeTransport()
    with pytest.raises(ValueError, match="Unknown"):
        await CloudBenchmark(transport).run("bathroom-real-devices")
    assert transport.client.calls == []


@pytest.mark.asyncio
async def test_error_suppressed_and_never_retried():
    transport = FakeTransport(FakeClient(fail=True))
    with pytest.raises(BenchmarkUnavailable) as e:
        await CloudBenchmark(transport).run("ventilation")
    assert "PRIVATE" not in str(e.value)
    assert len(transport.client.calls) == 1


@pytest.mark.asyncio
async def test_provider_rejection_has_no_body_or_account_data():
    transport = FakeTransport(FakeClient(status_code=429))
    with pytest.raises(BenchmarkUnavailable) as e:
        await CloudBenchmark(transport).run("history")
    assert "Cloud" in str(e.value)
    assert len(transport.client.calls) == 1


@pytest.mark.asyncio
async def test_semantically_fabricated_effect_not_misreported_as_verified():
    transport = FakeTransport(FakeClient(output={
        "schema": "homebrain-cloud-benchmark.v1",
        "sentences": [{
            "text": "The command proves that the boiler fired and all valves opened.",
            "fact_ids": ["f001"],
        }],
    }))
    result = await CloudBenchmark(transport).run("heating")
    assert "boiler fired" in result["answer"]
    assert result["source_bound"] is True
    assert result["semantic_accuracy_verified"] is False
    assert result["independent_review_required"] is True
    assert result["publication_approval"] is False


@pytest.mark.asyncio
async def test_malformed_model_result_rejected():
    for output in (
        {"schema": "wrong", "sentences": []},
        {"schema": "homebrain-cloud-benchmark.v1",
         "sentences": [{"text": "invented", "fact_ids": ["f999"]}]},
        {"schema": "homebrain-cloud-benchmark.v1",
         "sentences": [{"text": "invented", "fact_ids": []}]},
        {"schema": "homebrain-cloud-benchmark.v1",
         "sentences": [{"text": "invented", "fact_ids": ["f001", "f001"]}]},
    ):
        transport = FakeTransport(FakeClient(output=output))
        with pytest.raises(BenchmarkUnavailable):
            await CloudBenchmark(transport).run("lighting")
        assert len(transport.client.calls) == 1


def test_cases_are_independently_constructed_and_source_scoped():
    assert len(_CASES) == 4
    assert {c[0] for c in _CASES} == {"lighting", "heating", "ventilation", "history"}
    for case in _CASES:
        receipt = _constructed_receipt(case)
        assert "192.168" not in json.dumps(receipt)
        packet = build_stage4_evidence_packet([receipt])
        assert packet["shadow_only"] is True
        assert 1 <= len(packet["facts"]) <= 8
        assert _schema(packet)["properties"]["sentences"]["maxItems"] == 3


def test_no_live_devices_or_model_routing_in_new_service():
    text = (APP / "cloud_benchmark_service.py").read_text()
    assert "mcp_client" not in text
    assert "agent.chat" not in text
    assert "paid_credit_guard" not in text
    assert "local_base_url" not in text
    assert "follow_redirects=False" in text
    app_text = (APP / "app.py").read_text()
    assert '"/api/cloud-benchmark/run"' in app_text
    assert 'confirm_cloud_usage: Literal[True]' in app_text
    assert 'origin.netloc.casefold() != host' in app_text
    assert '"application/json"' in app_text
    ui = (APP / "webui.py").read_text()
    assert 'id="cloudBenchConsent"' in ui
    assert 'id="cloudBenchRun"' in ui
    assert "source_bound" not in ui or "independently fact-checked" in ui
    assert 'apiPath(\\'api/cloud-benchmark/run\\')' in ui
    assert 'confirm_cloud_usage:true' in ui

"""Stage 4O: real Ollama Cloud failure diagnostics without leaking secrets."""
import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from cloud_benchmark import (  # noqa: E402
    CloudBenchmark, BenchmarkError, _CASES, _parse_response,
)
from chat_transport import EmptyOllamaAssistantMessage  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class CloudStub:
    def __init__(self, problem=None, answer=None):
        self.api_key = "secret-key-test-never-log"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.problem = problem
        self.answer = answer
        self.calls = []

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert not tools
        assert kwargs["disable_thinking"] is True
        assert kwargs["api_key"] == self.api_key
        assert self.api_key not in json.dumps(messages)
        if self.problem:
            raise self.problem
        return {"content": self.answer}


def _valid_payload():
    return json.dumps({
        "schema": "homebrain-cloud-benchmark.v1",
        "explanation": "A source command was recorded but physical operation was not verified.",
        "assessments": [
            {"id": "c1", "verdict": "supported"},
            {"id": "c2", "verdict": "not_established"},
            {"id": "c3", "verdict": "not_established"},
            {"id": "c4", "verdict": "supported"},
        ],
    })


def test_one_ollama_request_accepts_fenced_json_but_no_extra_prose():
    fence = chr(96) * 3
    raw = fence + "json\n" + _valid_payload() + "\n" + fence
    st = CloudStub(answer=raw)
    report = run(CloudBenchmark().run_case(st, "lighting", confirmed=True))
    assert report["checks_correct"] == 4
    assert len(st.calls) == 1
    assert report["prose_semantics_independently_validated"] is False
    assert not report["publication_approval"]
    for invalid in (
        "Explanation: " + _valid_payload(),
        raw + "\nAnd a hidden claim.",
        raw + raw,
        fence + "json\n{\"schema\": 12}\n" + fence,
        "not JSON at all",
    ):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            _parse_response(invalid, _CASES["lighting"])


@pytest.mark.parametrize("problem,word", [
    (400, "request format"),
    (401, "credentials"),
    (403, "credentials"),
    (404, "model"),
    (429, "quota"),
    (503, "server error"),
])
def test_provider_http_errors_are_safe_and_specific(problem, word):
    req = httpx.Request("POST", "https://ollama.com/api/chat")
    res = httpx.Response(problem, request=req, text="private prompt secret-key-test-never-log")
    exc = httpx.HTTPStatusError("sensitive-data", request=req, response=res)
    fake = CloudStub(problem=exc)
    with pytest.raises(BenchmarkError) as error:
        run(CloudBenchmark().run_case(fake, "lighting", confirmed=True))
    assert word in str(error.value)
    assert "No retry" in str(error.value)
    assert "secret-key-test-never-log" not in str(error.value)
    assert "sensitive-data" not in str(error.value)
    assert len(fake.calls) == 1


@pytest.mark.parametrize("problem,word", [
    (httpx.ReadTimeout("secret-key-test-never-log"), "timed out"),
    (httpx.ConnectError("secret-key-test-never-log"), "connection"),
    (EmptyOllamaAssistantMessage("secret-key-test-never-log"), "no usable answer"),
    (RuntimeError("secret-key-test-never-log"), "unexpected processing error"),
])
def test_provider_failures_are_distinguished_and_never_retried(problem, word):
    fake = CloudStub(problem=problem)
    with pytest.raises(BenchmarkError) as error:
        run(CloudBenchmark().run_case(fake, "heating", confirmed=True))
    assert word in str(error.value)
    assert "secret-key-test-never-log" not in str(error.value)
    assert len(fake.calls) == 1


@pytest.mark.parametrize("answer,word", [
    ("A normal sentence not JSON", "not a valid JSON"),
    ('{"schema":"unrelated"}', "assessment fields"),
    ('{"schema":"homebrain-cloud-benchmark.v1","explanation":"","assessments":[]}', "assessment fields"),
])
def test_model_format_failures_show_kind_without_raw_answer(answer, word):
    fake = CloudStub(answer=answer)
    with pytest.raises(BenchmarkError) as error:
        run(CloudBenchmark().run_case(fake, "lighting", confirmed=True))
    assert word in str(error.value)
    assert answer not in str(error.value)
    assert len(fake.calls) == 1


def test_benchmark_still_forbids_tools_and_does_not_import_device_runtime():
    import cloud_benchmark
    source = Path(cloud_benchmark.__file__).read_text()
    for marker in ("HubitatMCPClient", "ToolExecutor(", "agent.process_user_request", "mcp.call("):
        assert marker not in source

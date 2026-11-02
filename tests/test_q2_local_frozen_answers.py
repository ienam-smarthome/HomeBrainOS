"""Q2 actual local frozen answer transport: no cloud, no fictional score."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
FILE = ROOT / "hubitat-mcp-ai/tools/q2_local_frozen_answers.py"
spec = importlib.util.spec_from_file_location("q2_local_frozen_answers", FILE)
q2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q2)


def test_actual_calls_are_exact_same_prompt_first_attempts_only():
    calls = []
    time = [0.0]
    def fake(model, prompt):
        calls.append((model, prompt))
        return f"Model says {model} on packet #{len(calls)}"
    def clock():
        time[0] += 0.125
        return time[0]
    result = q2.run_frozen_trial(fake, clock=clock)
    assert len(calls) == 8
    assert result["case_count"] == 4
    assert result["attempts"] == 8
    assert result["complete_same_prompt_first_answer_pairs"] == 4
    assert result["human_source_reviewed_pairs"] == 0
    assert result["quality_measurement"] == "not_measured"
    assert result["claude_or_gemma_comparison"] == "not_run"
    assert result["cloud_cost"] == 0
    assert all(x["attempt_index"] == 1 for x in result["records"])
    assert all(x["wall_ms"] == 125 for x in result["records"])
    for i in range(0, 8, 2):
        assert calls[i][0] == "qwen2.5:0.5b"
        assert calls[i+1][0] == "llama3.2:1b"
        assert calls[i][1] == calls[i+1][1]
        assert "required_findings" not in calls[i][1]
        assert result["records"][i]["packet_sha256"] == result["records"][i+1]["packet_sha256"]
        assert result["records"][i]["prompt_sha256"] == result["records"][i+1]["prompt_sha256"]
    text = json.dumps(result)
    assert "Model says" not in text
    assert "reviewer" not in text


@pytest.mark.parametrize("bad", ["", "  ", None, "x" * 20000])
def test_empty_malformed_oversized_response_is_error_no_fake_pair(bad):
    with pytest.raises(ValueError, match="Missing valid first answer"):
        q2.run_frozen_trial(lambda model, prompt: bad, clock=lambda: 1.0)


def test_second_model_exception_does_not_retry_or_fabricate():
    calls = []
    def fake(model, prompt):
        calls.append(model)
        if model == q2.MODELS[1]:
            raise TimeoutError("local inference timed out")
        return "first answer"
    with pytest.raises(TimeoutError):
        q2.run_frozen_trial(fake)
    assert calls == list(q2.MODELS)


def test_strict_isolation_prevents_host_or_cloud_access(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("OLLAMA_NO_CLOUD", "1")
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11434")
    q2.require_isolated_runner()
    c = q2.LocalOnlyOllama()
    assert c.url == "http://127.0.0.1:11434/api/chat"
    for k, v in [
        ("OLLAMA_NO_CLOUD", "0"),
        ("OLLAMA_HOST", "my-hub.local:11434"),
        ("GITHUB_ACTIONS", "false"),
    ]:
        with monkeypatch.context() as m:
            m.setenv(k, v)
            with pytest.raises(ValueError, match="isolated GitHub"):
                q2.require_isolated_runner()


def test_cli_requires_ack_and_runner(monkeypatch, capsys):
    assert q2.main([]) == 2
    assert "acknowledgement" in capsys.readouterr().err
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert q2.main(["--ack-no-cloud-synthetic-only"]) == 2
    assert "incomplete" in capsys.readouterr().err


def test_http_redirect_guard_cannot_reach_external_site():
    guard = q2.NoRedirect()
    with pytest.raises(ValueError, match="Redirect refused"):
        guard.redirect_request(None, None, 302, "redirect", {}, "https://example.com")

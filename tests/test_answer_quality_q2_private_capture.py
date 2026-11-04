"""Q2: opt-in private capture needs real first answers and never fake scores."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from answer_quality_fixed_packets import build_fixed_packets, validate_run_manifest
from answer_quality_paired_reviews import build_paired_review_report
from answer_quality_q2_private_capture import (
    CLOUD_URL, DEFAULT_CASES, LOCAL_URL, OPTIONS,
    OllamaTransport, NoRedirect, CaptureTransportError, check_private_path, collect_pairs,
    main, save_private, selected_packets, sha256, unfilled_review_template,
    validate_arms,
)


def packets():
    return selected_packets(DEFAULT_CASES)


def test_registered_q2_cases_and_digest_stable():
    p = packets()
    assert len(p) == 4
    assert [x["case_id"] for x in p] == list(DEFAULT_CASES)
    assert all(len(x["packet_sha256"]) == 64 for x in p)
    with pytest.raises(ValueError, match="Unknown frozen"):
        selected_packets(("invented",))
    with pytest.raises(ValueError, match="distinct"):
        selected_packets((DEFAULT_CASES[0], DEFAULT_CASES[0]))
    with pytest.raises(ValueError, match="1–4"):
        selected_packets(tuple(DEFAULT_CASES) + ("extra",))


def test_dry_run_has_no_model_network_or_output(monkeypatch, capsys):
    monkeypatch.setattr("answer_quality_q2_private_capture.OllamaTransport", lambda **kw: (_ for _ in ()).throw(AssertionError("called")))
    assert main([]) == 0
    out = capsys.readouterr()
    assert "DRY RUN ONLY" in out.out
    assert "not_measured" not in out.out


def test_cloud_needs_explicit_ack_and_key():
    local = ("ollama-local", "qwen3.5:4b")
    cloud = ("ollama-cloud", "gemma4:31b")
    with pytest.raises(ValueError, match="acknowledged"):
        validate_arms(cloud, local, cloud_ack=False, env={"OLLAMA_API_KEY": "secret"})
    with pytest.raises(ValueError, match="missing"):
        validate_arms(cloud, local, cloud_ack=True, env={})
    validate_arms(cloud, local, cloud_ack=True, env={"OLLAMA_API_KEY": "secret"})
    with pytest.raises(ValueError, match="distinct"):
        validate_arms(local, local, cloud_ack=True, env={})


def test_cloud_tag_cannot_bypass_explicit_cloud_acknowledgement():
    with pytest.raises(ValueError, match="Cloud-tagged"):
        validate_arms(("ollama-local", "gemma4:31b-cloud"),
                      ("ollama-local", "qwen3.5:4b"),
                      cloud_ack=False, env={})


def test_cloud_and_local_no_run_in_ci(monkeypatch):
    local1 = ("ollama-local", "qwen3.5:4b")
    local2 = ("ollama-local", "llama3.2:3b")
    for var in ("CI", "GITHUB_ACTIONS"):
        with pytest.raises(ValueError, match="public CI"):
            validate_arms(local1, local2, cloud_ack=False, env={var: "true"})


def test_local_pair_has_one_request_per_arm_exact_frozen_prompt():
    seen = []
    moments = iter([x * .1 for x in range(16)])
    def invoke(provider, model, prompt):
        seen.append((provider, model, prompt))
        return f"private answer {len(seen)}"
    left = ("ollama-cloud", "gemma4:31b")
    right = ("ollama-local", "qwen3.5:4b")
    before, after, session, raw = collect_pairs(packets(), left, right, "a"*40, invoke, clock=lambda: next(moments))
    assert len(seen) == 8
    assert len(raw) == 8
    assert session["quality_measurement"] == "not_measured"
    assert session["same_prompt_per_case"] is True
    assert session["complete_first_calls"] == 8
    assert session["first_attempt_independently_authenticated"] is False
    assert session["public_repo_safe_to_upload"] is False
    for i in range(0, 8, 2):
        assert seen[i][2] == seen[i + 1][2]
        assert "required_findings" not in seen[i][2]
        assert "forbidden_claims" not in seen[i][2]
    assert all(v["attempt_index"] == 1 for v in before["runs"] + after["runs"])
    assert all(v["elapsed_ms"] == 100 for v in before["runs"] + after["runs"])
    assert before["runs"][0]["answer_sha256"] == sha256("private answer 1")
    assert after["runs"][0]["answer_sha256"] == sha256("private answer 2")
    assert len(validate_run_manifest(before, build_fixed_packets())) == 4
    assert len(validate_run_manifest(after, build_fixed_packets())) == 4
    assert "private answer" not in json.dumps([before, after, session])
    assert OPTIONS == {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 320}
    # Without actual human grades, the official scorecard remains unmeasured.
    report = build_paired_review_report(before, after, {"schema":"homebrain-answer-quality-paired-reviews.v1", "pairs":[]})
    assert report["measurement_status"] == "not_measured"
    assert report["human_reviewed_pairs"] == 0


def test_unfilled_review_rows_cannot_be_passed_as_scores():
    left, right, session, raw = collect_pairs(packets()[:1],
        ("ollama-cloud", "gemma4:31b"), ("ollama-local", "qwen3.5:4b"),
        "a"*40, lambda provider, model, prompt: "first answer", clock=lambda: 1.0)
    form = unfilled_review_template(left, right)
    assert len(form["pairs"]) == 1
    assert form["pairs"][0]["baseline_answer_sha256"] == sha256("first answer")
    assert form["pairs"][0]["baseline_review"]["grounding"] is None
    with pytest.raises(ValueError):
        build_paired_review_report(left, right, form)


def test_model_failure_fails_closed_and_does_not_retry():
    calls = []
    def invoke(provider, model, prompt):
        calls.append(model)
        if len(calls) == 2:
            raise TimeoutError("no completion")
        return "first"
    with pytest.raises(ValueError, match="unexpected-transport-error") as exc:
        collect_pairs(packets(), ("ollama-local","qwen3.5:4b"),
                      ("ollama-local","llama3.2:3b"), "a"*40, invoke)
    assert "llama3.2:3b" in str(exc.value)
    assert calls == ["qwen3.5:4b", "llama3.2:3b"]


@pytest.mark.parametrize("bad", ["", " ", "x" * 17000, None])
def test_reject_invalid_answer(bad):
    with pytest.raises(ValueError, match="Missing, empty or oversized"):
        collect_pairs(packets()[:1], ("ollama-local","qwen3.5:4b"),
                      ("ollama-local","llama3.2:3b"), "a"*40,
                      lambda provider, model, prompt: bad, clock=lambda: 1.0)


def test_private_dir_outside_repo_and_no_overwrite(tmp_path):
    new = tmp_path / "new-secret-dir"
    assert check_private_path(new) == new.resolve()
    new.mkdir()
    with pytest.raises(ValueError, match="no overwrite"):
        check_private_path(new)
    with pytest.raises(ValueError, match="inside repository"):
        check_private_path(ROOT / "scripts" / "private-output-bad")


def test_private_write_boundary_rejects_repo_path():
    with pytest.raises(ValueError, match="inside repository"):
        save_private(ROOT / "scripts" / "unsafe-private",
                     {"runs": []}, {"runs": []}, {}, {})


def test_private_files_never_contain_raw_answers_in_manifests(tmp_path):
    left, right, session, raw = collect_pairs(packets()[:1],
        ("ollama-cloud", "gemma4:31b"), ("ollama-local", "qwen3.5:4b"),
        "a"*40, lambda provider, model, prompt: "CONFIDENTIAL-PRIVATE-FIRST-ANSWER", clock=lambda: 1.0)
    folder = tmp_path / "fresh"
    save_private(folder, left, right, session, raw)
    assert (folder / "aq_command_issuer_vs_reporter.baseline.txt").read_text() == "CONFIDENTIAL-PRIVATE-FIRST-ANSWER"
    assert "CONFIDENTIAL-PRIVATE-FIRST-ANSWER" not in (folder / "baseline.json").read_text()
    assert "CONFIDENTIAL-PRIVATE-FIRST-ANSWER" not in (folder / "candidate.json").read_text()
    assert "CONFIDENTIAL-PRIVATE-FIRST-ANSWER" not in (folder / "reviews-unfilled.json").read_text()
    if os.name != "nt":
        assert folder.stat().st_mode & 0o777 == 0o700
        assert (folder / "baseline.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="no overwrite"):
        save_private(folder, left, right, session, raw)


class Reply:
    def __init__(self, json_payload):
        self.status = 200
        self.raw = json.dumps(json_payload).encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.raw[:limit]


class FakeOpener:
    def __init__(self, objs):
        self.objs = iter(objs)
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        return Reply(next(self.objs))


def test_local_transport_no_cloud_headers_and_no_tools():
    tr = OllamaTransport(env={})
    tr.local = FakeOpener([
        {"models": [{"name": "qwen3.5:4b"}]},
        {"capabilities": ["completion", "thinking"], "thinking": {"values": [False, True]}},
        {"model":"qwen3.5:4b", "done":True, "message":{"content":"verified result"}},
    ])
    assert tr("ollama-local", "qwen3.5:4b", "fixed packet") == "verified result"
    assert len(tr.local.requests) == 3
    assert tr.local.requests[1].full_url.endswith("/api/show")
    assert json.loads(tr.local.requests[1].data) == {"model": "qwen3.5:4b"}
    req = tr.local.requests[2]
    assert req.full_url == LOCAL_URL
    assert req.get_header("Authorization") is None
    body = json.loads(req.data)
    assert body["stream"] is False
    assert body["messages"] == [{"role":"user", "content":"fixed packet"}]
    assert "tools" not in body
    assert body["options"] == OPTIONS
    assert body["think"] is False


def test_cloud_transport_exact_official_endpoint_token_not_logged():
    tr = OllamaTransport(env={"OLLAMA_API_KEY":"TOP_SECRET"})
    tr.cloud = FakeOpener([
        {"model":"gemma4:31b", "done":True, "message":{"content":"cloud answer"}},
    ])
    assert tr("ollama-cloud", "gemma4:31b", "fixed packet") == "cloud answer"
    req = tr.cloud.requests[0]
    assert req.full_url == CLOUD_URL
    assert req.get_header("Authorization") == "Bearer TOP_SECRET"
    assert "TOP_SECRET" not in json.dumps(json.loads(req.data))
    assert "think" not in json.loads(req.data)  # Cloud transport unchanged.


def test_unknown_local_model_never_sends_chat_or_pulls():
    tr = OllamaTransport(env={})
    tr.local = FakeOpener([{"models": [{"name":"other-model:1b"}]}])
    with pytest.raises(ValueError, match="not present"):
        tr("ollama-local", "qwen3.5:4b", "fixed packet")
    assert len(tr.local.requests) == 1
    assert tr.local.requests[0].full_url.endswith("/api/tags")


@pytest.mark.parametrize("payload", [
    {"model":"gemma4:31b", "done":False, "message":{"content":"partial"}},
    {"model":"incorrect", "done":True, "message":{"content":"wrong"}},
    {"model":"gemma4:31b", "done":True, "message":{"content":""}},
    {"model":"gemma4:31b", "done":True, "message":{"content":"x", "tool_calls":[{"fn":"danger"}]}}])
def test_provider_response_must_be_final_correct_model_and_text_only(payload):
    tr = OllamaTransport(env={"OLLAMA_API_KEY":"secret"})
    tr.cloud = FakeOpener([payload])
    with pytest.raises(ValueError):
        tr("ollama-cloud", "gemma4:31b", "fixed packet")


def test_redirect_refused_and_key_not_leaked():
    with pytest.raises(ValueError):
        NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://elsewhere")
    class Fails:
        def open(self, req, timeout):
            raise RuntimeError("leaked token secret here")
    tr = OllamaTransport(env={"OLLAMA_API_KEY":"secret"})
    tr.cloud = Fails()
    with pytest.raises(CaptureTransportError, match="cloud-inference: network-or-provider-failure") as exc:
        tr("ollama-cloud", "gemma4:31b", "fixed packet")
    assert "leaked" not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_local_non_thinking_model_omits_think_field():
    tr = OllamaTransport(env={})
    tr.local = FakeOpener([
        {"models": [{"name": "llama3.2:3b"}]},
        {"capabilities": ["completion", "tools"]},
        {"model": "llama3.2:3b", "done": True, "message": {"content": "Llama answer"}},
    ])
    assert tr("ollama-local", "llama3.2:3b", "frozen prompt") == "Llama answer"
    assert len(tr.local.requests) == 3
    body = json.loads(tr.local.requests[2].data)
    assert "think" not in body
    assert body["options"] == OPTIONS


def test_thinking_only_response_is_specific_failure_with_no_retry():
    tr = OllamaTransport(env={})
    tr.local = FakeOpener([
        {"models": [{"name": "qwen3.5:4b"}]},
        {"capabilities": ["thinking"], "thinking": {"values": [False, True]}},
        {"model": "qwen3.5:4b", "done": True,
         "message": {"content": "", "thinking": "secret hidden reason text"}},
    ])
    with pytest.raises(ValueError, match="thinking only, no final answer") as exc:
        tr("ollama-local", "qwen3.5:4b", "frozen prompt")
    assert "secret hidden" not in str(exc.value)
    assert len(tr.local.requests) == 3


def test_model_without_boolean_off_refuses_unsupported_thinking_mode():
    tr = OllamaTransport(env={})
    tr.local = FakeOpener([
        {"models": [{"name": "reason-model:8b"}]},
        {"capabilities": ["thinking"], "thinking": {"values": ["low", "high"]}},
    ])
    with pytest.raises(ValueError, match="does not expose a supported no-thinking mode"):
        tr("ollama-local", "reason-model:8b", "frozen prompt")
    assert len(tr.local.requests) == 2


def test_legacy_capability_only_requests_top_level_no_thinking():
    tr = OllamaTransport(env={})
    tr.local = FakeOpener([
        {"models": [{"name": "qwen3.5:4b"}]},
        {"capabilities": ["completion", "thinking"]},
        {"model": "qwen3.5:4b", "done": True, "message": {"content": "ok"}},
    ])
    assert tr("ollama-local", "qwen3.5:4b", "frozen prompt") == "ok"
    assert json.loads(tr.local.requests[-1].data)["think"] is False


def test_false_only_thinking_capability_disables_toggle_not_model():
    tr = OllamaTransport(env={})
    tr.local = FakeOpener([
        {"models": [{"name": "llama3.2:3b"}]},
        {"thinking": {"values": [False]}},
        {"model": "llama3.2:3b", "done": True, "message": {"content": "ok"}},
    ])
    assert tr("ollama-local", "llama3.2:3b", "frozen prompt") == "ok"
    assert "think" not in json.loads(tr.local.requests[-1].data)


def test_failed_arm_identified_without_exposing_raw_response():
    calls = []
    def invoke(provider, model, prompt):
        calls.append(model)
        raise ValueError("Model returned thinking only, no final answer (no automatic retry)")
    with pytest.raises(ValueError, match="baseline") as exc:
        collect_pairs(packets()[:1], ("ollama-local", "qwen3.5:4b"),
                      ("ollama-local", "llama3.2:3b"), "a" * 40, invoke)
    assert len(calls) == 1
    assert "qwen3.5:4b" in str(exc.value)
    assert "secret" not in str(exc.value)


def test_transport_timeout_is_safe_and_identifies_exact_stage():
    class TimeoutOpener:
        def open(self, request, timeout):
            raise TimeoutError("private prompt, key=LEAKED_SECRET")
    tr = OllamaTransport(env={"OLLAMA_API_KEY": "LEAKED_SECRET"})
    tr.cloud = TimeoutOpener()
    with pytest.raises(CaptureTransportError, match="cloud-inference: timeout") as exc:
        tr("ollama-cloud", "gemma4:31b", "frozen packet")
    assert "private" not in str(exc.value)
    assert "LEAKED_SECRET" not in str(exc.value)


def test_wrapped_url_timeout_is_not_hidden():
    class WrappedTimeout:
        def open(self, request, timeout):
            raise URLError(TimeoutError("SECRET-DETAIL"))
    tr = OllamaTransport(env={})
    tr.local = WrappedTimeout()
    with pytest.raises(CaptureTransportError, match="local-model-inventory: timeout") as exc:
        tr("ollama-local", "qwen3.5:4b", "frozen packet")
    assert "SECRET-DETAIL" not in str(exc.value)


def test_http_error_reports_safe_code_without_secret_response_body():
    class Reject:
        def open(self, request, timeout):
            raise HTTPError(request.full_url, 503, "SECRET PROVIDER", {}, None)
    tr = OllamaTransport(env={"OLLAMA_API_KEY": "SECRET-KEY"})
    tr.cloud = Reject()
    with pytest.raises(CaptureTransportError, match="cloud-inference: http-status-503") as exc:
        tr("ollama-cloud", "gemma4:31b", "frozen packet")
    assert "SECRET" not in str(exc.value)


def test_case_model_stage_provenance_for_timeout_no_retry():
    called = []
    def failing(provider, model, prompt):
        called.append((provider, model))
        if len(called) == 2:
            raise CaptureTransportError("local-inference", "timeout")
        return "baseline answer held only in memory"
    with pytest.raises(ValueError, match="aq_command_issuer_vs_reporter") as exc:
        collect_pairs(packets()[:1], ("ollama-local", "qwen3.5:4b"),
                      ("ollama-local", "llama3.2:3b"), "a" * 40, failing)
    assert "candidate (ollama-local/llama3.2:3b)" in str(exc.value)
    assert "local-inference: timeout" in str(exc.value)
    assert "baseline answer" not in str(exc.value)
    assert len(called) == 2


def test_arbitrary_model_exception_is_redacted_not_logged():
    def leak(provider, model, prompt):
        raise ValueError("PRIVATE_UNTRUSTED_PROVIDER_OUTPUT")
    with pytest.raises(ValueError, match="invalid-model-response") as exc:
        collect_pairs(packets()[:1], ("ollama-local", "qwen3.5:4b"),
                      ("ollama-local", "llama3.2:3b"), "a" * 40, leak)
    assert "PRIVATE_UNTRUSTED_PROVIDER_OUTPUT" not in str(exc.value)


def test_filesystem_error_is_scoped_and_private(tmp_path, monkeypatch):
    left, right, session, raw = collect_pairs(packets()[:1],
        ("ollama-local", "qwen3.5:4b"), ("ollama-local", "llama3.2:3b"),
        "a" * 40, lambda *args: "answer", clock=lambda: 1.0)
    def fail_write(path, text):
        raise PermissionError("PRIVATE_PATH_WITH_SECRET")
    monkeypatch.setattr("answer_quality_q2_private_capture._write_private_file", fail_write)
    with pytest.raises(CaptureTransportError, match="private-output: filesystem-write-failed") as exc:
        save_private(tmp_path / "new", left, right, session, raw)
    assert "PRIVATE_PATH_WITH_SECRET" not in str(exc.value)

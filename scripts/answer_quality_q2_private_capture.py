#!/usr/bin/env python3
"""Opt-in Q2 first-answer A/B capture; private review, no device or tool access.

No model requests happen during imports, tests, or a dry run. When explicitly
run by a person, the two allowed Ollama transports receive the *same* frozen
synthetic/anonymised question once each, with no retries. Raw answers stay in
an explicitly selected new private directory, outside the source repository.
This is transport evidence, NOT an automated truth, Claude, or safety score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from time import monotonic
from typing import Any, Callable
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from answer_quality_comparison_prompt import render_comparison_prompt
from answer_quality_fixed_packets import build_fixed_packets, RUN_SCHEMA

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CASES = (
    "aq_command_issuer_vs_reporter",
    "aq_early_heating_off_resume",
    "aq_network_broker_vs_device_health",
    "aq_rule_parent_type_gap",
)
PROVIDERS = ("ollama-local", "ollama-cloud")
OPTIONS = {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 320}
LOCAL_URL = "http://127.0.0.1:11434/api/chat"
CLOUD_URL = "https://ollama.com/api/chat"
MAX_RESPONSE = 65536
MAX_ANSWER = 16384
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
MODEL_RE = re.compile(r"^[a-zA-Z0-9_.:/-]{1,80}$")

# Never show untrusted exception text from a model invocation: it can contain
# private prompts, provider bodies, local paths, or API credentials.
SAFE_MODEL_ERRORS = frozenset({
    "Oversized provider response",
    "Invalid model response JSON",
    "Unexpected model response type",
    "Local model not present in local Ollama inventory; no pull attempted",
    "Local model does not expose a supported no-thinking mode",
    "Model response not marked complete",
    "Model generation exhausted output token limit; first answer incomplete (no automatic retry)",
    "Model finished with a nonstandard completion reason; answer not accepted",
    "Provider model identity does not match requested model",
    "Model returned tool calls instead of a text-only answer",
    "Model returned thinking only, no final answer (no automatic retry)",
    "Model returned empty final answer (no automatic retry)",
    "Model final answer exceeded the private capture limit",
    "Unknown provider/model",
})


class CaptureTransportError(RuntimeError):
    """Only enum-like stage/category tokens; never raw provider exceptions."""
    def __init__(self, stage: str, category: str):
        self.stage = stage
        self.category = category
        super().__init__(f"{stage}: {category}; no automatic retry")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Provider redirect refused")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_arms(left: tuple[str, str], right: tuple[str, str], *,
                  cloud_ack: bool, env: dict[str, str]) -> None:
    if left == right:
        raise ValueError("Comparison arms must be distinct models or providers")
    for provider, model in (left, right):
        if provider not in PROVIDERS or not MODEL_RE.fullmatch(model):
            raise ValueError("Unknown or malformed comparison arm")
        if provider == "ollama-local" and "cloud" in model.casefold():
            raise ValueError("Cloud-tagged model cannot be used via local-only arm")
        if provider == "ollama-cloud":
            if not cloud_ack:
                raise ValueError("Cloud use must be explicitly acknowledged; costs are possible")
            if not env.get("OLLAMA_API_KEY", "").strip():
                raise ValueError("Cloud key missing from OLLAMA_API_KEY environment")
    if env.get("GITHUB_ACTIONS") == "true" or env.get("CI", "").lower() not in ("", "false", "0"):
        raise ValueError("Private capture cannot run in public CI")


def selected_packets(case_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    if not case_ids or len(case_ids) > 4 or len(set(case_ids)) != len(case_ids):
        raise ValueError("Select 1–4 distinct frozen cases")
    packets = {p["case_id"]: p for p in build_fixed_packets()}
    if any(case_id not in packets for case_id in case_ids):
        raise ValueError("Unknown frozen source case")
    return [packets[c] for c in case_ids]


def check_private_path(path: Path, repo: Path = REPO) -> Path:
    """Only a new output location *outside* the public checkout is allowed."""
    target = path.expanduser().resolve()
    if target.exists() or target.is_symlink():
        raise ValueError("Choose a new private output directory; no overwrite or reuse")
    if target == repo.resolve() or repo.resolve() in target.parents:
        raise ValueError("Private answers must never be stored inside repository")
    if target == Path(target.anchor):
        raise ValueError("Refusing filesystem root for private output")
    return target


def current_build_sha() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                capture_output=True, text=True, timeout=4, check=True)
    except (OSError, subprocess.SubprocessError):
        raise CaptureTransportError("local-git", "checkout-identity-failed") from None
    return result.stdout.strip()


class OllamaTransport:
    """Explicit URLs only: no URL interpolation, redirects or client tools."""
    def __init__(self, *, env: dict[str, str], timeout: int = 120):
        if type(timeout) is not int or not 1 <= timeout <= 180:
            raise ValueError("Timeout outside permitted range")
        self.timeout = timeout
        self.key = env.get("OLLAMA_API_KEY", "")
        self.local = build_opener(ProxyHandler({}), NoRedirect())
        self.cloud = build_opener(NoRedirect())
        self._checked_local: set[str] = set()
        self._local_think_disabled: dict[str, bool] = {}

    def _call(self, opener, req: Request, *, stage: str = "model-transport") -> dict[str, Any]:
        try:
            with opener.open(req, timeout=self.timeout) as response:
                if response.status != 200:
                    raise CaptureTransportError(stage, "unexpected-http-status")
                raw = response.read(MAX_RESPONSE + 1)
        except CaptureTransportError:
            raise
        except Exception as exc:
            # Classify without exposing HTTP error bodies or URLError.reason.
            # HTTPError is also a URLError, so check HTTP codes first.
            if isinstance(exc, HTTPError):
                category = f"http-status-{int(exc.code)}"
            elif (isinstance(exc, (TimeoutError, socket.timeout))
                  or (isinstance(exc, URLError)
                      and isinstance(exc.reason, (TimeoutError, socket.timeout)))):
                category = "timeout"
            elif (isinstance(exc, (ConnectionRefusedError, ConnectionResetError))
                  or (isinstance(exc, URLError)
                      and isinstance(exc.reason, (ConnectionRefusedError, ConnectionResetError)))):
                category = "connection-failed"
            else:
                category = "network-or-provider-failure"
            raise CaptureTransportError(stage, category) from None
        if len(raw) > MAX_RESPONSE:
            raise ValueError("Oversized provider response")
        try:
            obj = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid model response JSON") from None
        if not isinstance(obj, dict):
            raise ValueError("Unexpected model response type")
        return obj

    def _verify_local_installed(self, model: str) -> None:
        if model in self._checked_local:
            return
        tags = self._call(self.local, Request("http://127.0.0.1:11434/api/tags"),
                          stage="local-model-inventory")
        names = {entry.get("name") for entry in tags.get("models", [])
                 if isinstance(entry, dict)} if isinstance(tags.get("models"), list) else set()
        if model not in names:
            raise ValueError("Local model not present in local Ollama inventory; no pull attempted")
        # Thinking models can spend a small output budget entirely in
        # message.thinking, leaving message.content empty. This local
        # /api/show call checks model support without invoking inference.
        info = self._call(self.local, Request(
            "http://127.0.0.1:11434/api/show",
            data=json.dumps({"model": model}).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"}),
            stage="local-model-capabilities")
        controls = info.get("thinking")
        capabilities = info.get("capabilities")
        if isinstance(controls, dict) and isinstance(controls.get("values"), list):
            values = controls["values"]
            if False in values:
                # Ollama documents [false] alone as no thinking support.
                disable_thinking = len(values) > 1
            elif "thinking" in (capabilities if isinstance(capabilities, list) else []):
                raise ValueError("Local model does not expose a supported no-thinking mode")
            else:
                disable_thinking = False
        else:
            # Older Ollama versions may expose only the broad capability.
            disable_thinking = (
                isinstance(capabilities, list) and "thinking" in capabilities
            )
        self._local_think_disabled[model] = disable_thinking
        self._checked_local.add(model)

    def __call__(self, provider: str, model: str, prompt: str) -> str:
        if provider == "ollama-local":
            self._verify_local_installed(model)
        if provider not in PROVIDERS or not MODEL_RE.fullmatch(model):
            raise ValueError("Unknown provider/model")
        request_fields = {
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": OPTIONS,
        }
        if provider == "ollama-local" and self._local_think_disabled[model]:
            # Top-level API field, NOT options.think. Request answer-only
            # output on thinking-capable local models without extra rounds.
            request_fields["think"] = False
        payload = json.dumps(
            request_fields, ensure_ascii=True, separators=(",", ":")
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if provider == "ollama-cloud":
            headers["Authorization"] = "Bearer " + self.key
        req = Request(CLOUD_URL if provider == "ollama-cloud" else LOCAL_URL,
                      method="POST", data=payload, headers=headers)
        result = self._call(self.cloud if provider == "ollama-cloud" else self.local, req,
                            stage="cloud-inference" if provider == "ollama-cloud" else "local-inference")
        if result.get("done") is not True:
            raise ValueError("Model response not marked complete")
        # Ollama may report done=true even when num_predict is exhausted.
        # A provider-reported length stop is not a complete first answer.
        # Older providers can omit done_reason; absence is not proof of stop.
        stop_reason = result.get("done_reason")
        if stop_reason == "length":
            raise ValueError("Model generation exhausted output token limit; first answer incomplete (no automatic retry)")
        if stop_reason is not None and stop_reason != "stop":
            raise ValueError("Model finished with a nonstandard completion reason; answer not accepted")
        if result.get("model") != model:
            raise ValueError("Provider model identity does not match requested model")
        msg = result.get("message")
        answer = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(msg, dict) and msg.get("tool_calls"):
            raise ValueError("Model returned tool calls instead of a text-only answer")
        if not isinstance(answer, str) or not answer.strip():
            if isinstance(msg, dict) and isinstance(msg.get("thinking"), str) and msg["thinking"].strip():
                raise ValueError("Model returned thinking only, no final answer (no automatic retry)")
            raise ValueError("Model returned empty final answer (no automatic retry)")
        if len(answer.encode("utf-8")) > MAX_ANSWER:
            raise ValueError("Model final answer exceeded the private capture limit")
        return answer


def collect_pairs(packets: list[dict[str, Any]],
                  left: tuple[str, str], right: tuple[str, str],
                  build_sha: str, invoke: Callable[[str, str, str], str],
                  clock: Callable[[], float] = monotonic):
    """Requests exactly once per case and arm; outputs are NOT a quality score."""
    if not SHA_RE.fullmatch(build_sha):
        raise ValueError("Build SHA must be 40 lowercase hex characters")
    records = {"baseline": [], "candidate": []}
    raw: dict[str, str] = {}
    prompt_hashes: dict[str, str] = {}
    for packet in packets:
        case_id = packet["case_id"]
        prompt = render_comparison_prompt(case_id)
        prompt_hashes[case_id] = sha256(prompt)
        for side, (provider, model) in (("baseline", left), ("candidate", right)):
            start = clock()
            try:
                answer = invoke(provider, model, prompt)  # one attempt, no retry
            except (ValueError, CaptureTransportError) as exc:
                # Include exact frozen case and model arm without logging the
                # prompt or any exception text from arbitrary model providers.
                safe = (str(exc) if isinstance(exc, CaptureTransportError)
                        or str(exc) in SAFE_MODEL_ERRORS else "invalid-model-response")
                raise ValueError(f"{case_id}: {side} ({provider}/{model}): {safe}") from None
            except Exception:
                raise ValueError(f"{case_id}: {side} ({provider}/{model}): unexpected-transport-error; no automatic retry") from None
            end = clock()
            elapsed = end - start
            if (not isinstance(answer, str) or not answer.strip()
                    or len(answer.encode("utf-8")) > MAX_ANSWER):
                raise ValueError("Missing, empty or oversized raw first answer")
            if not (0 <= elapsed <= 10000):
                raise ValueError("Invalid measured response time")
            records[side].append({
                "case_id": case_id,
                "packet_sha256": packet["packet_sha256"],
                "answer_sha256": sha256(answer),
                "model": model,
                "provider": provider,
                "build_sha": build_sha,
                "attempt_index": 1,
                "elapsed_ms": round(elapsed * 1000),
            })
            raw[f"{case_id}.{side}.txt"] = answer
    return (
        {"schema": RUN_SCHEMA, "runs": records["baseline"]},
        {"schema": RUN_SCHEMA, "runs": records["candidate"]},
        {"schema": "homebrain-q2-private-first-answer-capture.v1",
         "cases": [p["case_id"] for p in packets],
         "prompt_sha256_by_case": prompt_hashes,
         "requested_options": OPTIONS,
         "local_thinking_policy": "request_no_thinking_if_model_supports_it; cloud_unchanged",
         "same_prompt_per_case": True,
         "complete_first_calls": len(raw),
         "quality_measurement": "not_measured",
         "first_attempt_independently_authenticated": False,
         "provider_input_delivery_independently_authenticated": False,
         "deployment_build_sha_independently_verified": False,
         "public_repo_safe_to_upload": False,
         "cloud_cost_usd": "not_measured",
         "notes": "Raw answers are for private human review, not to commit or share publicly."},
        raw,
    )


def unfilled_review_template(baseline: dict, candidate: dict) -> dict:
    """Digest-linked placeholders are NOT human-reviewed grades."""
    lhs = {row["case_id"]: row for row in baseline["runs"]}
    rhs = {row["case_id"]: row for row in candidate["runs"]}
    if lhs.keys() != rhs.keys():
        raise ValueError("Missing paired answer digest")
    def blank_grade():
        return {
            "grounding": None, "causal_calibration": None,
            "useful_first_attempt": None, "clarity": None, "safety": None,
            "grounded_factual_conclusions": None,
            "factual_conclusions_evaluated": None,
            "unsupported_definitive_causal_claims": None,
        }
    return {
        "schema": "homebrain-answer-quality-paired-reviews.v1",
        "pairs": [
            {
                "case_id": case_id,
                "baseline_answer_sha256": lhs[case_id]["answer_sha256"],
                "candidate_answer_sha256": rhs[case_id]["answer_sha256"],
                "reviewer": None,
                "evidence_reference_sha256": None,
                "baseline_review": blank_grade(),
                "candidate_review": blank_grade(),
            }
            for case_id in lhs
        ],
    }


def _write_private_file(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)


def save_private(path: Path, baseline: dict, candidate: dict,
                 session: dict, answers: dict[str, str]) -> None:
    path = check_private_path(path)
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name, answer in answers.items():
            _write_private_file(path / name, answer)
        for name, payload in (("baseline.json", baseline), ("candidate.json", candidate),
                              ("session.json", session),
                              ("reviews-unfilled.json", unfilled_review_template(baseline, candidate))):
            _write_private_file(path / name, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except OSError:
        # The destination may be partially created; never overwrite on rerun.
        raise CaptureTransportError("private-output", "filesystem-write-failed") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--baseline-provider", choices=PROVIDERS, default="ollama-cloud")
    parser.add_argument("--baseline-model", default="gemma4:31b")
    parser.add_argument("--candidate-provider", choices=PROVIDERS, default="ollama-local")
    parser.add_argument("--candidate-model", default="qwen3.5:4b")
    parser.add_argument("--private-dir", type=Path)
    parser.add_argument("--build-sha")
    parser.add_argument("--ack-cloud-usage", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    selected = tuple(args.case_id) if args.case_id else DEFAULT_CASES
    try:
        packets = selected_packets(selected)
        left = (args.baseline_provider, args.baseline_model)
        right = (args.candidate_provider, args.candidate_model)
        if not args.run:
            print("DRY RUN ONLY: Q2 fixed cases: " + ", ".join(selected))
            print("No inference, cloud usage, or stored answers. To run requires "
                  "--run, a new --private-dir, and --ack-cloud-usage for cloud models.")
            return 0
        if args.private_dir is None:
            raise ValueError("Explicit new --private-dir required")
        validate_arms(left, right, cloud_ack=args.ack_cloud_usage, env=os.environ)
        target = check_private_path(args.private_dir)
        build = args.build_sha or current_build_sha()
        transport = OllamaTransport(env=os.environ, timeout=args.timeout_seconds)
        left_manifest, right_manifest, session, answers = collect_pairs(
            packets, left, right, build, transport)
        save_private(target, left_manifest, right_manifest, session, answers)
    except (ValueError, CaptureTransportError) as exc:
        # Only known, sanitised errors reach stderr; no provider bodies or paths.
        print(f"Q2 capture incomplete: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("Q2 capture incomplete: unexpected local setup or private file error", file=sys.stderr)
        return 2
    print("Q2 first-answer capture complete. Private files saved locally; "
          "factual/source review NOT MEASURED. Do not commit the output directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
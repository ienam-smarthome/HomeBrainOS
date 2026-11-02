#!/usr/bin/env python3
"""Q2: bounded actual LOCAL model first-answer transport on frozen source packets.

This is an actual model-response/latency trial, not a human quality review.
Never touches Hubitat, Home Assistant, home/household files, cloud endpoints or
live tools. Every answer is held only in memory; only hashes and timing leave it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from time import monotonic
from typing import Callable
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
from answer_quality_comparison_prompt import render_comparison_prompt  # noqa: E402
from answer_quality_fixed_packets import build_fixed_packets  # noqa: E402

SCHEMA = "homebrain-answer-quality-q2-local-first-answers.v1"
MODELS = ("qwen2.5:0.5b", "llama3.2:1b")
CASES = (
    "aq_command_issuer_vs_reporter",
    "aq_early_heating_off_resume",
    "aq_network_broker_vs_device_health",
    "aq_rule_parent_type_gap",
)
OPTIONS = {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 320}
MAX_OUTPUT = 16_384
MAX_HTTP = 65_536


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused for local inference")


def require_isolated_runner() -> None:
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("OLLAMA_NO_CLOUD") == "1"
        and os.environ.get("OLLAMA_HOST") == "127.0.0.1:11434"
    ):
        raise ValueError("Q2 inference requires isolated GitHub no-cloud loopback environment")


class LocalOnlyOllama:
    def __init__(self, timeout_seconds: int = 180):
        require_isolated_runner()
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 180:
            raise ValueError("Invalid timeout")
        self.url = "http://127.0.0.1:11434/api/chat"
        self.timeout = timeout_seconds
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def __call__(self, model: str, prompt: str) -> str:
        if model not in MODELS or not isinstance(prompt, str) or len(prompt) > 15000:
            raise ValueError("Invalid model or frozen prompt")
        request = Request(self.url, data=json.dumps({
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": OPTIONS,
        }, ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
        method="POST", headers={"Content-Type": "application/json"})
        with self.opener.open(request, timeout=self.timeout) as response:
            if response.status != 200:
                raise ValueError("Unexpected local inference status")
            raw = response.read(MAX_HTTP + 1)
        if len(raw) > MAX_HTTP:
            raise ValueError("Oversized local inference envelope")
        result = json.loads(raw)
        if not isinstance(result, dict) or not isinstance(result.get("message"), dict):
            raise ValueError("Invalid local model response envelope")
        answer = result["message"].get("content")
        if not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_OUTPUT:
            raise ValueError("Empty or oversized first answer")
        return answer


def run_frozen_trial(
    invoke: Callable[[str, str], str],
    clock: Callable[[], float] = monotonic,
) -> dict:
    """One attempt per model per exactly frozen prompt; never auto-retry."""
    packets = {p["case_id"]: p for p in build_fixed_packets()}
    if any(case_id not in packets for case_id in CASES):
        raise ValueError("Frozen Q2 selection is not present")
    records = []
    completed = []
    for case_id in CASES:
        p = packets[case_id]
        prompt = render_comparison_prompt(case_id)
        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        matched = []
        for model in MODELS:
            start = clock()
            # If a model errors, fail the job; never silently replace
            # the first attempt with a successful retry or an empty answer.
            answer = invoke(model, prompt)
            end = clock()
            if not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_OUTPUT:
                raise ValueError("Missing valid first answer")
            elapsed = round((end - start) * 1000)
            if not math.isfinite(end - start) or elapsed < 0:
                raise ValueError("Invalid first-answer wall time")
            records.append({
                "case_id": case_id,
                "packet_sha256": p["packet_sha256"],
                "prompt_sha256": prompt_sha,
                "model": model,
                "provider": "ollama-local",
                "attempt_index": 1,
                "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
                "answer_characters": len(answer),
                "wall_ms": elapsed,
            })
            matched.append(prompt_sha)
        completed.append(len(set(matched)) == 1)

    if not all(completed) or len(records) != len(CASES) * len(MODELS):
        raise ValueError("Paired first prompts were not identical")
    return {
        "schema": SCHEMA,
        "input_origin": "frozen-synthetic-or-anonymised-offline-packets",
        "model_execution": "actual-local-ollama-model-answers",
        "models": list(MODELS),
        "fixed_case_ids": list(CASES),
        "case_count": len(CASES),
        "attempts": len(records),
        "complete_same_prompt_first_answer_pairs": sum(completed),
        "records": records,
        "model_options": OPTIONS,
        "missing_model_answers": 0,
        "quality_measurement": "not_measured",
        "human_source_reviewed_pairs": 0,
        "claude_or_gemma_comparison": "not_run",
        "actual_prompt_delivery": "local-http-requested-not-provider-independently-attested",
        "real_household_or_hub_reads": False,
        "production_publisher_tested": False,
        "cloud_model_api_spend_usd": 0,
        "github_runner_minutes_cost": "not_measured",
        "limitations": [
            "First-answer transport and timing only, no independent factual review",
            "Raw model replies are intentionally not logged or uploaded",
            "These two tiny local models are NOT a proxy for installed Gemma Cloud quality",
            "Neither actual home automation answers nor authoring safety is tested",
            "A packet digest proves source text stability, not the model reading every fact",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack-no-cloud-synthetic-only", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    if not args.ack_no_cloud_synthetic_only:
        print("Refused: explicit no-cloud synthetic-only acknowledgement required.", file=sys.stderr)
        return 2
    try:
        require_isolated_runner()
        result = run_frozen_trial(LocalOnlyOllama(args.timeout_seconds))
        # No prompts or answers and no raw private records are printed.
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as file:
                file.write(
                    "## Q2: actual local first-answer trial — NOT QUALITY SCORED\\n"
                    f"- Frozen source packets: {result['case_count']}\\n"
                    f"- Complete same-prompt first-answer pairs: {result['complete_same_prompt_first_answer_pairs']}\\n"
                    f"- Actual local requests: {result['attempts']}\\n"
                    "- No model response texts logged, no Hubitat/HA or cloud calls.\\n"
                    "- First-answer factual grounding and model superiority: NOT MEASURED.\\n"
                )
        return 0
    except Exception:
        # Do not expose model transport error bodies which could include content.
        print("Q2 local inference incomplete; no score or partial model answers published.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

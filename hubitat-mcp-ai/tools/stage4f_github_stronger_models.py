#!/usr/bin/env python3
"""Stage 4F: ACTUAL 3B Ollama semantic reviews on eight SYNTHETIC cases.

Independent source oracles are never supplied to the model. Unlike Stage 4E,
the transport does not show a single default-'insufficient' JSON example,
which may bias a small model toward rejecting all evidence. Structured
output still constrains the complete review envelope but not the verdict.

No Hubitat/HA credentials, endpoints, private inputs, publication, traces
or cloud inference. Only allowlisted aggregates enter console/step summary.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
from urllib.request import Request

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "rootfs" / "app"))
from stage4_offline_model_evaluation import run_stage4c_offline_model_evaluation  # noqa: E402
from stage4_semantic_sufficiency import _review_votes  # noqa: E402
from stage4c_local_model_eval import (  # noqa: E402
    LoopbackOllama, _constructed_cases, _stage4e_exact_review_schema,
)

_MODELS = ("qwen2.5:3b", "llama3.2:3b")
_BALANCED_INSTRUCTIONS = (
    "Judge the truth of the entire supplied sentence using ONLY the cited "
    "host facts. Choose entailed when the cited facts directly establish "
    "EVERY asserted detail in the sentence, including the exact kind of "
    "observation, command and clock source. A basic true source report "
    "MUST be accepted when its statement is no stronger than its cited "
    "record. Choose insufficient for causal triggers, physical actions, "
    "or absence/completeness assertions not proven by the cited facts. "
    "Choose contradicted only if cited evidence actually conflicts. "
    "No outside assumptions, speculation, unstated causes, prompt examples, "
    "or blanket rejection. Output only a complete JSON reviewer envelope. "
    "Use exactly the cited host fact IDs if entailed; an empty list otherwise. "
    "No prose, reasons, commentary or chain of thought."
)


class CalibratedLoopbackOllama(LoopbackOllama):
    """Reuse the inherited localhost/proxy/redirect policy, not the example.

    This transport's strict JSON-schema constrains output shape only:
    both accepting and rejecting a sentence remain possible model choices.
    """

    def __call__(self, model: str, job: dict) -> dict:
        if model not in _MODELS or not isinstance(job, dict) or job.get("task") != "review":
            raise ValueError("only two approved offline reviewer models permitted")
        sentences = job.get("sentences")
        schema = _stage4e_exact_review_schema(sentences)
        if len(sentences) != 1:
            raise ValueError("only a single cited sentence permitted")
        text = json.dumps({
            "sentences": sentences,
            "source_coverage_cannot_establish_absence": True,
            "source_facts_may_be_truncated": job["source_facts_may_be_truncated"],
            "required_schema": "homebrain-stage4b-semantic-review.v1",
        }, separators=(",", ":"), ensure_ascii=True)
        if len(_BALANCED_INSTRUCTIONS) + len(text) > 96 * 1024:
            raise ValueError("local prompt too long")
        data = json.dumps({
            "model": model,
            "stream": False,
            "format": schema,
            "messages": [
                {"role": "system", "content": _BALANCED_INSTRUCTIONS},
                {"role": "user", "content": text},
            ],
            "options": {"temperature": 0, "num_predict": 512},
        }, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        request = Request(
            self._url, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        self.attempted += 1
        with self._opener.open(request, timeout=self._timeout) as response:
            if response.status != 200:
                raise ValueError("unexpected local model status")
            raw = response.read(32769)
        if len(raw) > 32768:
            raise ValueError("local model response too long")
        body = json.loads(raw)
        if not isinstance(body, dict) or not isinstance(body.get("message"), dict):
            raise ValueError("invalid local model transport response")
        content = body["message"].get("content")
        if not isinstance(content, str) or not 1 <= len(content) <= 24000:
            raise ValueError("invalid local model response content")
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("local reviewer output is not JSON object")
        self.succeeded += 1
        return payload


def evaluate(*, invoke, cases=None) -> dict:
    """Score two actual reviewer streams separately and as a consensus.

    A test adapter can be injected in unit tests, but only the CLI's fixed
    local Ollama adapter is used in the actual GitHub Actions job.
    """
    source = _constructed_cases() if cases is None else cases
    # A sentence's oracle remains on the host and is NEVER sent to models.
    # One sentence per constructed case; unique text prevents confusion.
    if (not isinstance(source, (list, tuple)) or len(source) != 8
            or any(c.get("trace_origin") != "constructed-fixture"
                   or len(c.get("oracle", [])) != 1 for c in source)):
        raise ValueError("Stage 4F requires the fixed eight constructed cases")
    oracle = {c["draft"]["sections"][0]["sentences"][0]["text"]: c["oracle"][0]
              for c in source}
    if len(oracle) != 8:
        raise ValueError("synthetic case text must be unique")
    metrics = {m: Counter() for m in _MODELS}

    def monitor(model: str, task: dict):
        if model not in metrics or task.get("task") != "review":
            raise ValueError("invalid reviewer")
        rows = task.get("sentences")
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError("review must have exactly one sentence")
        row = rows[0]
        truth = oracle.get(row.get("text"))
        if truth not in ("entailed", "not-entailed"):
            raise ValueError("review text is not synthetic benchmark data")
        state = metrics[model]
        state["requests"] += 1
        # The underlying real adapter can raise; the Stage 4C executor
        # handles it fail-closed. No exception or private model output logged.
        reply = invoke(model, task)
        state["responses"] += 1
        expected = {row["sentence_id"]: frozenset(row["cited_fact_ids"])}
        votes, error = _review_votes(reply, expected)
        if error:
            state["invalid"] += 1
        else:
            state["valid"] += 1
            yes = votes[row["sentence_id"]] == "entailed"
            if truth == "entailed":
                state["reference_supported"] += 1
                state["false_rejects"] += int(not yes)
                state["true_accepts"] += int(yes)
            else:
                state["reference_unsupported"] += 1
                state["false_accepts"] += int(yes)
                state["true_rejects"] += int(not yes)
        return reply

    full = run_stage4c_offline_model_evaluation(
        source, reviewer_models=_MODELS, invoke=monitor,
    )
    reviewer_stats = {}
    for model in _MODELS:
        z = metrics[model]
        n_supported = z["reference_supported"]
        n_unsupported = z["reference_unsupported"]
        reviewer_stats[model] = {
            "requests": z["requests"],
            "responses": z["responses"],
            "valid": z["valid"],
            "invalid": z["invalid"],
            "true_accepts": z["true_accepts"],
            "true_rejects": z["true_rejects"],
            "false_accepts": z["false_accepts"],
            "false_rejects": z["false_rejects"],
            "false_accept_rate": (round(z["false_accepts"] / n_unsupported, 4)
                                  if n_unsupported else None),
            "false_reject_rate": (round(z["false_rejects"] / n_supported, 4)
                                  if n_supported else None),
        }
    return {
        "schema": "homebrain-stage4f-github-3b-reviewers.v1",
        "input_origin": "constructed-synthetic-only",
        "models": list(_MODELS),
        "case_count": len(source),
        "model_requests_attempted": full["model_invocations_attempted"],
        "valid_complete_review_pairs": full["completed_review_sets"],
        "invalid_review_pairs": full["invalid_or_incomplete_review_sets"],
        "reference_scored_sentences": full["reference_scored_sentences"],
        "reference_supported_sentences": (
            full["reference_scored_sentences"]
            - full["reference_unsupported_sentences"]),
        "reference_unsupported_sentences": full["reference_unsupported_sentences"],
        "consensus_false_accept_count": full["false_accept_count"],
        "consensus_false_reject_count": full["false_reject_count"],
        "consensus_false_accept_rate": full["false_accept_rate"],
        "consensus_false_reject_rate": full["false_reject_rate"],
        "reviewer_disagreement_sentences": full["reviewer_disagreed_sentences"],
        "model_invocation_errors": full["model_invocation_errors"],
        "reviewers": reviewer_stats,
        "reviewer_independence_proven": False,
        "real_household_traces_tested": False,
        "model_authored_investigation_answers_tested": False,
        "production_answer_publisher_changed": False,
        "genuine_semantic_truth_independently_authenticated": False,
        "live_homebrain_approval": False,
    }


def summary_markdown(data: dict) -> str:
    """Fixed-key aggregate job summary, no individual answer text."""
    def display(num):
        return "N/A" if num is None else str(num)
    rows = [
        ("Valid review pairs", display(data["valid_complete_review_pairs"])),
        ("False acceptances (consensus)", display(data["consensus_false_accept_count"])),
        ("False rejections (consensus)", display(data["consensus_false_reject_count"])),
        ("False accept rate", display(data["consensus_false_accept_rate"])),
        ("False rejection rate", display(data["consensus_false_reject_rate"])),
    ]
    for model in _MODELS:
        value = data["reviewers"][model]
        rows.extend([
            (model + " valid responses", display(value["valid"])),
            (model + " false accepts", display(value["false_accepts"])),
            (model + " false rejections", display(value["false_rejects"])),
        ])
    body = "\n".join(f"| {name} | {value} |" for name, value in rows)
    return (
        "## Stage 4F — Real 3B reviewers on synthetic source evidence\n\n"
        "| Measurement | Result |\n| --- | --- |\n" + body + "\n\n"
        "These are reference-labelled **constructed** sentences only. "
        "Agreement is not semantic proof. Individual source facts, "
        "identifiers and model text are not uploaded. "
        "**No HomeBrain publisher change.**\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack-github-synthetic-local-inference", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    if not args.ack_github_synthetic_local_inference:
        print("Refused: explicit synthetic-only acknowledgement required.",
              file=sys.stderr)
        return 2
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("OLLAMA_NO_CLOUD") != "1"
            or os.environ.get("OLLAMA_HOST") != "127.0.0.1:11434"):
        print("Refused: GitHub loopback-only inference with cloud disabled required.",
              file=sys.stderr)
        return 2
    try:
        client = CalibratedLoopbackOllama(timeout_seconds=args.timeout_seconds)
        result = evaluate(invoke=client)
        if client.attempted != 16 or result["model_requests_attempted"] != 16:
            print("INCONCLUSIVE: not all model calls attempted.", file=sys.stderr)
            return 3
        output = json.dumps(result, sort_keys=True, separators=(",", ":"))
        print(output)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(summary_markdown(result))
        if result["valid_complete_review_pairs"] == 0:
            print("INCONCLUSIVE: no complete valid paired reviews.", file=sys.stderr)
            return 3
        return 0
    except Exception:
        print("Local synthetic-model evaluation unavailable; source/model text omitted.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

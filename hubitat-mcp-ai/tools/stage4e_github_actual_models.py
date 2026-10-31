#!/usr/bin/env python3
"""Stage 4E: actual, opt-in GitHub-hosted LOCAL Ollama review on SYNTHETIC facts.

No real household inputs or credentials accepted. The two actual locally
downloaded model weights are invoked through Stage 4C's loopback-only adapter.
The source corpus is constructed and its labelled answers are NOT sent to
models. Output contains only allowlisted aggregate numeric metrics.

The GitHub workflow additionally sets OLLAMA_NO_CLOUD=1; this script
enforces it and requires an explicit synthetic-only acknowledgement.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "rootfs" / "app"))
from stage4_offline_model_evaluation import run_stage4c_offline_model_evaluation  # noqa: E402
from stage4c_local_model_eval import LoopbackOllama, _constructed_cases  # noqa: E402

_ALLOWED_MODELS = ("qwen2.5:0.5b", "llama3.2:1b")
_FIELDS = (
    "case_count", "model_invocations_attempted", "author_invocations_attempted",
    "review_calls_attempted", "review_responses_received",
    "completed_review_sets", "invalid_or_incomplete_review_sets",
    "reference_scored_cases", "reference_scored_sentences",
    "reference_unsupported_sentences", "reviewer_concordant_entailed_sentences",
    "reviewer_disagreed_sentences", "reviewers_both_rejected_sentences",
    "model_invocation_errors", "false_accept_count", "false_reject_count",
    "false_accept_rate", "false_reject_rate",
)


def evaluate(*, invoke, cases=None) -> dict:
    """No model-simulation fallback. Adapter comes from actual loopback client."""
    samples = _constructed_cases() if cases is None else cases
    result = run_stage4c_offline_model_evaluation(
        samples, reviewer_models=_ALLOWED_MODELS, invoke=invoke,
    )
    report = {field: result[field] for field in _FIELDS}
    complete = result["completed_review_sets"]
    report.update({
        "schema": "homebrain-stage4e-github-synthetic-actual-model.v1",
        "input_origin": "constructed-synthetic-only",
        "execution": "actual-local-model-adapter",
        "cases_are_real_home_incidents": False,
        "models_distinct_by_tag_only": True,
        "reviewer_independence_verified": False,
        "reference_truth_independently_authenticated": False,
        "model_ability_on_live_homebrain_established": False,
        "meaningful_reference_accuracy_scored": bool(
            complete and result["reference_scored_sentences"]),
        "evaluation_outcome": (
            "scored-constructed-sentences" if complete
            else "no-complete-valid-reviews"),
        "production_publisher_changed": False,
        "homeassistant_or_hubitat_contacted": False,
    })
    return report


def summary_markdown(report: dict) -> str:
    """Short, public-safe CI summary; never include model responses/case IDs."""
    def integer(field: str) -> str:
        value = report.get(field)
        return str(value) if type(value) is int else "N/A"
    def rate(field: str) -> str:
        value = report.get(field)
        return f"{value:.2%}" if type(value) in (float, int) else "N/A"
    rows = [
        ("Synthetic benchmark cases", integer("case_count")),
        ("Actual model requests attempted", integer("model_invocations_attempted")),
        ("Model JSON responses received", integer("review_responses_received")),
        ("Complete valid review pairs", integer("completed_review_sets")),
        ("Reference-scored sentences", integer("reference_scored_sentences")),
        ("Reference unsupported sentences", integer("reference_unsupported_sentences")),
        ("False accepts (synthetic oracle)", integer("false_accept_count")),
        ("False rejections (synthetic oracle)", integer("false_reject_count")),
        ("False-accept rate", rate("false_accept_rate")),
        ("False-reject rate", rate("false_reject_rate")),
    ]
    table = "\n".join(f"| {name} | {value} |" for name, value in rows)
    return (
        "## Stage 4E — Actual local Ollama reviews (constructed facts ONLY)\n\n"
        "A temporary GitHub runner invoked two locally resident models with "
        "cloud inference disabled. No live home data or devices involved.\n\n"
        "| Measure | Result |\n| --- | --- |\n" + table + "\n\n"
        "**Critical:** These are constructed, pre-labelled examples. "
        "A complete review is not a certification of truth, "
        "and distinct model tags do not prove reviewer independence. "
        "New model-written answers and production publication remain untested.\n\n"
        f"**Outcome:** {report['evaluation_outcome']}.\n"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ack-github-synthetic-local-inference", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=90)
    args = p.parse_args(argv)
    if not args.ack_github_synthetic_local_inference:
        print("Refused: explicit synthetic-only local-inference acknowledgement required.",
              file=sys.stderr)
        return 2
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("OLLAMA_NO_CLOUD") != "1"
            or os.environ.get("OLLAMA_HOST") != "127.0.0.1:11434"):
        print("Refused: isolated GitHub runner with cloud disabled and loopback binding required.",
              file=sys.stderr)
        return 2
    try:
        client = LoopbackOllama(timeout_seconds=args.timeout_seconds, structured_review_schema=True)
        report = evaluate(invoke=client)
        # Assert the evaluator actually attempted two models for all eight cases.
        if (client.attempted != 16 or report["review_calls_attempted"] != 16
                or report["model_invocations_attempted"] != 16):
            print("No valid evidence of complete model invocation attempts.",
                  file=sys.stderr)
            return 2
        with_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if with_summary:
            # Append safe aggregate only; never write or upload model replies.
            with Path(with_summary).open("a", encoding="utf-8") as out:
                out.write(summary_markdown(report))
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        # Distinguish a working transport from a semantically complete review:
        # zero complete responses is an INCONCLUSIVE test, not fake 0% error.
        if not report["meaningful_reference_accuracy_scored"]:
            print("INCONCLUSIVE: no complete paired model judgments.", file=sys.stderr)
            return 3
        return 0
    except Exception:
        # Local model or library errors may contain private prompt material.
        print("Evaluation unavailable: no model inputs or errors displayed.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

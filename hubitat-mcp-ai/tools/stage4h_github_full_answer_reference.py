#!/usr/bin/env python3
"""Stage 4H real-model full-answer adjudication on PRE-AUTHORED SYNTHETIC text.

The reference labels are written by the host before inference, NEVER sent to
the models. Newly model-written Stage 4G answers remain independently unscored.
All output is strict aggregate only. No live devices, Hubitat/HA or cloud.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "rootfs" / "app"))
from stage4_full_answer_reference import evaluate_stage4h_full_answer_references  # noqa: E402
from stage4g_github_authored_answers import _synthetic_author_cases  # noqa: E402
from stage4f_github_stronger_models import CalibratedLoopbackOllama  # noqa: E402

_MODELS = ("qwen2.5:3b", "llama3.2:3b")


def _prelabelled_full_answer_cases() -> list[dict]:
    """4 adequate + 3 invented-cause + 1 factually true but INCOMPLETE.

    Content is constructed with synthetic IDs/events. References label
    sentence meaning and complete-answer sufficiency, separately from
    source-citation checks. Labels are not authenticated live truth.
    """
    source = _synthetic_author_cases()
    rows = []
    by_domain = {c["domain"]: c for c in source}
    for domain, labels in (
        ("lighting", [
            ("The source records a brightness command for the light.",
             "The recorded command identifies an issuing controller app.",
             "adequate", ["entailed", "entailed"]),
            ("The source records a brightness command for the light.",
             "This establishes that movement at the sensor triggered it.",
             "unsupported", ["entailed", "not-entailed"]),
        ]),
        ("heating", [
            ("A heating setpoint command appears in the source records.",
             "The command alone does not verify boiler ignition or a radiator opening.",
             "adequate", ["entailed", "entailed"]),
            ("A heating setpoint command appears in the source records.",
             "The boiler definitely fired and all radiator valves opened.",
             "unsupported", ["entailed", "not-entailed"]),
        ]),
        ("ventilation", [
            ("The source records an OFF command addressed to the fan.",
             "That command does not independently confirm a physical fan-motor stop.",
             "adequate", ["entailed", "entailed"]),
            ("The source records an OFF command addressed to the fan.",
             "The humidity reading caused the fan to turn off.",
             "unsupported", ["entailed", "not-entailed"]),
        ]),
        ("history", [
            ("The contact-open report carries a collector-reception timestamp.",
             "The archived source also explicitly reports an incomplete history.",
             "adequate", ["entailed", "entailed"]),
            ("A contact-open observation was recorded by the collector.",
             "The same contact reading has a collector-reception timestamp.",
             "incomplete", ["entailed", "entailed"]),
        ]),
    ):
        case = by_domain[domain]
        fact_ids = case["required_fact_ids"]
        for n, (first, second, answer_label, sentence_labels) in enumerate(labels):
            chosen = (
                [fact_ids[0], fact_ids[-1]]
                if domain == "history" and answer_label == "adequate"
                else [fact_ids[0], fact_ids[0]]
            )
            proposal = {
                "schema": "homebrain-stage4g-authored-proposal.v1",
                "sections": [{
                    "name": "summary",
                    "sentences": [
                        {"text": first, "fact_ids": [chosen[0]]},
                        {"text": second, "fact_ids": [chosen[1]]},
                    ],
                }],
            }
            rows.append({
                "case_id": f"{domain}-answer-{n + 1}",
                "domain": domain,
                "question": case["question"],
                "packet": case["packet"],
                "proposal": proposal,
                "required_fact_ids": list(fact_ids),
                "sentence_oracle": list(sentence_labels),
                "answer_oracle": answer_label,
            })
    return rows


def summary_markdown(results: dict) -> str:
    """All data are allowlisted aggregate numbers, never sentences or IDs."""
    titles = [
        ("Full answers tested", "cases"),
        ("Reference adequate", "reference_adequate_answers"),
        ("Reference unsupported cause", "reference_unsupported_answers"),
        ("Reference factually true but incomplete", "reference_incomplete_answers"),
        ("Valid sentence review pairs", "valid_review_pairs"),
        ("Complete answer review sets", "complete_reviewed_answers"),
        ("Reviewer disagreements", "reviewer_disagreements"),
        ("Unsafe full answers accepted by unanimity", "unsupported_answers_accepted"),
        ("Adequate full answers rejected by unanimity", "adequate_answers_rejected"),
        ("Incomplete answers accepted by unanimity", "incomplete_answers_accepted"),
    ]
    rows = "\n".join(f"| {title} | {results[field]} |" for title, field in titles)
    return (
        "## Stage 4H — Real 3B reviews of independently labelled complete answers\n\n"
        "| Measurement | Value |\n| --- | --- |\n" + rows + "\n\n"
        "This run reviewed pre-authored **synthetic** full answers, "
        "not Qwen's new Stage 4G prose. Source fact coverage is not "
        "semantic truth; reference judgments are host-curated and not "
        "externally authenticated. No device access or publication.\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack-github-synthetic-local-inference", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    if not args.ack_github_synthetic_local_inference:
        print("Refused: explicit synthetic-only acknowledgment required.", file=sys.stderr)
        return 2
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("OLLAMA_NO_CLOUD") != "1"
            or os.environ.get("OLLAMA_HOST") != "127.0.0.1:11434"):
        print("Refused: localhost-only GitHub runner with cloud disabled required.",
              file=sys.stderr)
        return 2
    try:
        models = CalibratedLoopbackOllama(timeout_seconds=args.timeout_seconds)
        results = evaluate_stage4h_full_answer_references(
            _prelabelled_full_answer_cases(),
            reviewer_models=_MODELS,
            invoke=models,
        )
        print(json.dumps(results, sort_keys=True, separators=(",", ":")))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(summary_markdown(results))
        if (models.attempted != results["review_attempts"]
                or results["complete_reviewed_answers"] == 0):
            print("INCONCLUSIVE: no complete full-answer review set or unmatched call count.",
                  file=sys.stderr)
            return 3
        return 0
    except Exception:
        print("Offline reference evaluation unavailable; private details omitted.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Actual isolated local-model Q2 prompt A/B on identical frozen source evidence.

Two tiny public local models, four source packets, baseline vs one general
candidate prompt. One attempt for each model/case/prompt arm, no retries.
No Hubitat/HA, paid Cloud, model-answer publication or semantic auto-grading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import median
import sys
from time import monotonic
from typing import Callable

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
from answer_quality_evidence_first_prompt import (  # noqa: E402
    BASELINE, SOURCE_BOUNDARY, VARIANT, render_variant,
)
from answer_quality_fixed_packets import build_fixed_packets  # noqa: E402
from q2_local_frozen_answers import (  # noqa: E402
    CASES, MAX_OUTPUT, MODELS, OPTIONS, LocalOnlyOllama, require_isolated_runner,
)

SCHEMA = "homebrain-answer-quality-q2-evidence-first-prompt-ab.v1"
VARIANTS = (BASELINE, VARIANT)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_evidence_first_ab(
    invoke: Callable[[str, str], str],
    clock: Callable[[], float] = monotonic,
) -> dict:
    """Hold the model and complete source packet fixed within every A/B pair."""
    packets = {packet["case_id"]: packet for packet in build_fixed_packets()}
    if any(case_id not in packets for case_id in CASES):
        raise ValueError("A/B source case missing from frozen manifest")
    records = []
    deltas = []
    early = {BASELINE: 0, VARIANT: 0}
    for case_index, case_id in enumerate(CASES):
        packet = packets[case_id]
        prompts = {variant: render_variant(case_id, variant) for variant in VARIANTS}
        if prompts[BASELINE] == prompts[VARIANT]:
            raise ValueError("Candidate must differ from unchanged baseline instructions")
        if any(text.count(SOURCE_BOUNDARY) != 1 for text in prompts.values()):
            raise ValueError("Ambiguous frozen source boundary")
        source_parts = {variant: text.split(SOURCE_BOUNDARY, 1)[1]
                        for variant, text in prompts.items()}
        if source_parts[BASELINE] != source_parts[VARIANT]:
            raise ValueError("A/B source payload changed between prompt arms")
        for model_index, model in enumerate(MODELS):
            # Counterbalance request-order effects across cases and models.
            order = VARIANTS if (case_index + model_index) % 2 == 0 else VARIANTS[::-1]
            early[order[0]] += 1
            timings = {}
            for attempt_order, variant in enumerate(order, start=1):
                prompt = prompts[variant]
                start = clock()
                answer = invoke(model, prompt)
                end = clock()
                if not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_OUTPUT:
                    raise ValueError("Incomplete A/B answer; no automatic retry")
                elapsed = round((end - start) * 1000)
                if not math.isfinite(end - start) or elapsed < 0:
                    raise ValueError("Invalid A/B wall time")
                timings[variant] = elapsed
                records.append({
                    "case_id": case_id,
                    "model": model,
                    "provider": "ollama-local",
                    "variant": variant,
                    "request_order_within_pair": attempt_order,
                    "requested_first_attempt_for_variant": True,
                    "frozen_packet_sha256": packet["packet_sha256"],
                    "prompt_sha256": sha256(prompt),
                    "answer_sha256": sha256(answer),
                    "answer_characters": len(answer),
                    "wall_ms": elapsed,
                })
            deltas.append(timings[VARIANT] - timings[BASELINE])
    expected_attempts = len(CASES) * len(MODELS) * len(VARIANTS)
    if len(records) != expected_attempts:
        raise ValueError("Incomplete A/B first-attempt set")
    return {
        "schema": SCHEMA,
        "input_origin": "existing_frozen_synthetic_or_anonymised_offline_cases",
        "models": list(MODELS),
        "case_ids": list(CASES),
        "prompt_variants": list(VARIANTS),
        "case_count": len(CASES),
        "matched_source_model_pairs": len(deltas),
        "attempts": len(records),
        "requested_first_attempts_per_arm": len(deltas),
        "first_request_counts_by_variant": early,
        "candidate_minus_baseline_request_median_ms": median(deltas),
        "candidate_faster_matched_requests": sum(delta < 0 for delta in deltas),
        "model_options": OPTIONS,
        "records": records,
        "quality_measurement": "not_measured",
        "human_source_reviewed_pairs": 0,
        "semantic_noninferiority": "not_measured",
        "claude_gemma_or_production_comparison": "not_run",
        "provider_model_input_delivery": "local_http_requested_not_independently_attested",
        "no_device_or_home_system_access": True,
        "cloud_model_api_spend_usd": 0,
        "github_runner_minutes_cost": "not_measured",
        "limitations": [
            "This is one tiny-local-model prompt A/B per case, not production HomeBrain",
            "Model answer texts are never published, so factual quality is not graded",
            "Same source/question/seed does not establish provider reproducibility",
            "Order alternation mitigates but does not eliminate warm-start or sequence bias",
            "Latency deltas are descriptive model-request timings, not end-to-end p95",
            "A request marked first attempt is not independently provider authenticated",
            "Do not promote this ungraded candidate to production answer routing",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack-no-cloud-synthetic-only", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    if not args.ack_no_cloud_synthetic_only:
        print("Refused: explicit no-cloud synthetic-only acknowledgement required.",
              file=sys.stderr)
        return 2
    try:
        require_isolated_runner()
        result = run_evidence_first_ab(LocalOnlyOllama(args.timeout_seconds))
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        path = os.environ.get("GITHUB_STEP_SUMMARY")
        if path:
            with Path(path).open("a", encoding="utf-8") as file:
                file.write(
                    "## Q2 evidence-first local prompt A/B — UNGRADED\n"
                    f"- Frozen evidence cases: {result['case_count']}\n"
                    f"- Same source + model A/B pairs: {result['matched_source_model_pairs']}\n"
                    f"- Actual first prompt-arm model requests: {result['attempts']}\n"
                    "- Raw answers and source-review claims are never uploaded or logged.\n"
                    "- Semantic quality and production improvement: NOT MEASURED.\n"
                )
        return 0
    except Exception:
        print("Q2 evidence-first A/B incomplete; no fabricated score or raw answer published.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

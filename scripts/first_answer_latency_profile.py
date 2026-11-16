#!/usr/bin/env python3
"""PRIVATE offline model-round performance profile of first-answer V2 exports.

No AI/provider/Hubitat calls and NO grading. Reads original private Technical
JSON; writes a bounded, source-minimal report. Do not publish original exports.

Example:
 python scripts/first_answer_latency_profile.py original-private.json \
    --output private-latency-profile.json

Old alpha captures lack per-round phase labels. When the original export
contains valid answer-stage boundaries, inferred phases are shown as DERIVED,
not as verified agent instrumentation. A phase/time total is observational:
provider and local clocks may overlap and must not be added as an exact
wall-clock partition.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_ROUNDS = 40
MAX_FILES = 40
PHASES = frozenset({
    "initial_investigation", "source_review", "causal_follow_through",
    "final_claim_audit", "deadline_finalization", "prewrite_model_review",
})
STAGES = frozenset({
    "pre_source_review", "pre_causal_follow_through", "pre_final_audit",
})
SCHEMA = "homebrain-v2-round-performance.v1"


class ProfileError(ValueError):
    pass


def _number(value: Any, *, maximum: float = 10**12) -> float | None:
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    if value < 0 or value > maximum:
        return None
    return float(value)


def _natural(value: Any, *, maximum: int = 10**10) -> int | None:
    if type(value) is not int or value < 0 or value > maximum:
        return None
    return value


def _stage_boundaries(response: dict) -> dict[str, int]:
    result: dict[str, int] = {}
    items = response.get("answer_stage_trace")
    if not isinstance(items, list):
        return result
    for row in items[:40]:
        if not isinstance(row, dict):
            continue
        phase = row.get("stage")
        n = _natural(row.get("after_model_round"), maximum=MAX_ROUNDS)
        if phase in STAGES and n is not None:
            result.setdefault(phase, n)
    return result


def _phase(round_no: int, metric: dict, marks: dict[str, int]) -> tuple[str, str]:
    explicit = metric.get("phase")
    if isinstance(explicit, str) and explicit in PHASES:
        return explicit, "recorded_by_agent"
    # Old captures: pre_* stages are checkpoints after the cited model round.
    # Never claim a causally meaningful phase if the boundaries are missing.
    start = marks.get("pre_source_review")
    final = marks.get("pre_final_audit")
    follow = marks.get("pre_causal_follow_through")
    if start is None:
        return "unknown", "not_established"
    if round_no <= start:
        return "initial_investigation", "derived_from_stage_trace"
    if final is not None and round_no > final:
        return "final_claim_audit", "derived_from_stage_trace"
    if follow is not None and round_no > follow:
        return "causal_follow_through", "derived_from_stage_trace"
    return "source_review", "derived_from_stage_trace"


def profile_export(original: dict, raw_bytes: bytes) -> dict:
    """Return no raw text, question, IDs, timestamps, tools or private rows."""
    if not isinstance(original, dict) or not isinstance(original.get("response"), dict):
        raise ProfileError("Expected the browser's original V2 Technical JSON object")
    response = original["response"]
    rows = response.get("model_round_metrics")
    if not isinstance(rows, list) or not isinstance(response.get("tool_calls"), list):
        raise ProfileError("Missing model-round metrics or tool receipts")
    if len(rows) > MAX_ROUNDS:
        raise ProfileError("Too many model rounds to profile safely")
    seen: set[int] = set()
    marks = _stage_boundaries(response)
    per_round = []
    aggregate: dict[str, dict] = defaultdict(lambda: {
        "rounds": 0, "prompt_tokens": 0, "output_tokens": 0,
        "provider_reported_ms": 0., "client_round_elapsed_ms": 0.,
        "client_round_samples": 0,
    })
    for row in rows:
        if not isinstance(row, dict):
            raise ProfileError("Each model round must be an object")
        n = _natural(row.get("round"), maximum=MAX_ROUNDS)
        if n is None or n < 1 or n in seen:
            raise ProfileError("Model round IDs must be unique positive integers")
        seen.add(n)
        phase, attribution = _phase(n, row, marks)
        prompt = _natural(row.get("prompt_eval_count"))
        output = _natural(row.get("eval_count"))
        total = _number(row.get("total_ms"))
        client_time = _number(row.get("client_round_elapsed_ms"))
        recs = _natural(row.get("source_receipts_before"))
        offered = _natural(row.get("tools_offered"))
        before_messages = _natural(row.get("model_messages_before"))
        per_round.append({
            "round": n,
            "phase": phase,
            "phase_attribution": attribution,
            "prompt_tokens": prompt,
            "output_tokens": output,
            "provider_reported_ms": total,
            "client_round_elapsed_ms": client_time,
            "source_receipts_before": recs,
            "tools_offered": offered,
            "model_messages_before": before_messages,
        })
        a = aggregate[phase]
        a["rounds"] += 1
        a["prompt_tokens"] += prompt or 0
        a["output_tokens"] += output or 0
        a["provider_reported_ms"] += total or 0
        if client_time is not None:
            a["client_round_elapsed_ms"] += client_time
            a["client_round_samples"] += 1

    per_round.sort(key=lambda x: x["round"])
    advertised_rounds = _natural(response.get("rounds"), maximum=10**5)
    if advertised_rounds is not None and seen and max(seen) > advertised_rounds:
        raise ProfileError("Round metrics exceed declared model rounds")
    app_performance = response.get("action_performance")
    app_performance = app_performance if isinstance(app_performance, dict) else {}
    tool_rows = response["tool_calls"]
    tool_ms = sum(_number(row.get("elapsed_ms")) or 0 for row in tool_rows
                  if isinstance(row, dict))
    elapsed = _number(original.get("client_elapsed_ms"))
    if elapsed is None:
        elapsed = _number(response.get("elapsed_ms"))
    provider_total = sum(row["provider_reported_ms"] or 0 for row in per_round)
    token_total = sum(row["prompt_tokens"] or 0 for row in per_round)
    output_total = sum(row["output_tokens"] or 0 for row in per_round)

    return {
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "version": original.get("ui_version") if isinstance(
            original.get("ui_version"), str) else None,
        "model": original.get("model") if isinstance(
            original.get("model"), str) else None,
        "completed_answer_reported": response.get("success") is True,
        "quality_reviewed": False,
        "quality_score": None,
        "focal_event_correct": "not_established",
        "rounds_declared": advertised_rounds,
        "rounds_measured": len(per_round),
        "first_review_draft_after_round": marks.get("pre_source_review"),
        "client_elapsed_ms": elapsed,
        "provider_reported_ms_sum": round(provider_total, 2),
        "provider_reported_input_tokens_sum": token_total,
        "provider_reported_output_tokens_sum": output_total,
        "original_reported_input_tokens": _natural(
            app_performance.get("model_input_tokens_reported")),
        "original_reported_output_tokens": _natural(
            app_performance.get("model_output_tokens_reported")),
        "original_reported_model_ms": _number(app_performance.get("model_reported_ms")),
        "source_tool_attempts": len(tool_rows),
        "source_tool_success_count": sum(
            r.get("success") is True for r in tool_rows if isinstance(r, dict)),
        "sum_reported_tool_attempt_ms": round(tool_ms, 2),
        "phase_totals": {
            p: {
                **{
                    k: (round(v, 2) if k.endswith("_ms") else v)
                    for k, v in counts.items()
                }
            }
            for p, counts in sorted(aggregate.items())
        },
        "model_rounds": per_round,
        "notes": [
            "Phase labels in older captures are derived from source-stage markers; no model behavior is reconstructed.",
            "Provider-reported processing time and local tool time can overlap; their sums do not partition wall-clock time.",
            "Full model prompt tokens include cached or repeated context; prompt counts are not billing cost.",
            "Performance is not answer quality, causal correctness, device reliability or a physical outcome.",
            "The first source-review draft is not an independently verified useful or correct answer.",
        ],
    }


def _read(path: Path) -> tuple[dict, bytes]:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise ProfileError("Source exceeds private intake limit")
        raw = path.read_bytes()
        if len(raw) > MAX_SOURCE_BYTES:
            raise ProfileError("Source exceeds private intake limit")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ProfileError("Capture root must be a JSON object")
        return value, raw
    except (OSError, ValueError) as exc:
        if isinstance(exc, ProfileError):
            raise
        raise ProfileError("Invalid or unreadable private first-answer export") from exc


def _write_private(path: Path, value: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if len(args.captures) > MAX_FILES:
        parser.error("Too many original captures")
    try:
        profiles = [profile_export(*_read(path)) for path in args.captures]
        report = {
            "schema": SCHEMA,
            "quality_status": "not_measured",
            "profile_count": len(profiles),
            "profiles": profiles,
        }
        _write_private(args.output, report)
    except (ProfileError, OSError) as exc:
        parser.error(type(exc).__name__ + ": " + str(exc))
    print("Prepared " + str(len(profiles)) +
          " PRIVATE performance profile(s), without original source content. "
          "No factual-quality improvement has been claimed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

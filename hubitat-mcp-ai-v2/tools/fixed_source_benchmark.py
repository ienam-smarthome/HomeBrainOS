#!/usr/bin/env python3
"""Offline, private fixed-source A/B benchmark for HomeBrainOS v2.

Freeze existing browser Technical JSON receipts ONCE and give the same frozen
question and exact MCP source responses to two blinded prompt variants:
'baseline' (unchanged response) vs 'role_notes' (only generic source-role notes).
No model calls, MCP calls, Hubitat actions, network access or automatic grading.
Both variants use the same retrospective no-tools instruction.

WARNING: the output directory contains private unredacted house data. Never
commit, share, or upload the generated prompts/manifest/answers/ratings.
Only the aggregate report is designed to be safe to share.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
from pathlib import Path
from typing import Any


SCHEMA = "homebrain-v2-fixed-source-pairs.v1"
RUBRIC = (
    "factual_grounding", "source_completeness", "causal_calibration",
    "command_outcome", "usefulness",
)
INSTRUCTIONS = (
    "This is a RETROSPECTIVE offline review of a completed HomeBrainOS request. "
    "You cannot invoke tools or change any devices. Answer the recorded user's "
    "question using ONLY the immutable MCP source receipts below. Preserve "
    "source-vs-inference distinctions, avoid claiming absent events from bounded "
    "logs, and distinguish accepted commands, reported states, and physical "
    "effects. Explicitly say when a required fact was not established. "
    "Do not invent further tool reads or actions. "
    "This prompt is identical in both experimental conditions."
)

# All annotations are fixed, domain-general SOURCE-ROLE descriptions, not
# case-specific claims, new measurements, or instructions to choose tools.
ROLE_NOTES = {
    "hub_call_device_command": (
        "Native device-command result: success acknowledges the interface call. "
        "An embedded state snapshot may predate the command; physical effect "
        "requires other evidence."
    ),
    "hub_get_device_attribute": (
        "A device attribute value reported at this read, not an independent "
        "measurement of physical actuation or an earlier historical state."
    ),
    "hub_list_device_events": (
        "Discrete returned event rows. Command producer identifies the recorded "
        "issuer; physical-type state events identify a reporting bridge/device; "
        "triggered handlers are downstream listeners. Returned rows are not "
        "proof of complete history or continuous intermediate states."
    ),
    "hub_get_logs": (
        "A bounded log response may show only a latest page of matching rows. "
        "No older-error absence claim follows without relevant window coverage."
    ),
    "hub_get_app_config": (
        "Configuration and visible controls at read time, not independent proof "
        "of an earlier internal timer, decision branch, or successful button press."
    ),
    "hub_get_device_health": (
        "Classification/last-activity evidence, not proof of a physical outage "
        "or failed integration session."
    ),
    "hub_list_devices": (
        "Device inventory and returned current-state snapshots, not a historical "
        "device state at the time of a separate event."
    ),
    "hub_get_device": (
        "A device descriptor/current-state snapshot; state freshness and "
        "physical operation require separate evidence."
    ),
    "hub_get_tool_guide": (
        "Tool reference documentation, not evidence that a particular write "
        "permission or app action has been successfully exercised."
    ),
    "hub_list_backups": (
        "Returned backup inventory, not direct proof of write privileges, "
        "backup restoration feasibility, or current action safety."
    ),
    "hub_set_native_app": (
        "A native app write/form response. Successful transport does not by "
        "itself confirm app-specific outcome or physical device operation."
    ),
}
DEFAULT_ROLE_NOTE = (
    "Tool result is limited to the data this source returned. A successful read "
    "does not automatically establish completeness, physical effect, or causality."
)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_dump(value).encode("utf-8")).hexdigest()


def _private_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # On POSIX, never let a generated prompt default to group/world readable.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(value)
    if os.name == "posix":
        os.chmod(path, 0o600)


def _json_file(path: Path, value: Any) -> None:
    _private_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _private_directory(path: Path) -> Path:
    output = path.resolve()
    repository = Path(__file__).resolve().parents[2]
    if output == repository or repository in output.parents:
        raise ValueError("Private benchmark output must be OUTSIDE the Git repository")
    if output.exists():
        raise ValueError("Output directory already exists; use a fresh private path")
    output.mkdir(mode=0o700, parents=True)
    if os.name == "posix":
        os.chmod(output, 0o700)
    return output


def _is_isolated(document: dict) -> bool:
    response = document.get("response")
    if not isinstance(response, dict):
        return False
    for name in ("prior_receipts_used", "prior_sources_indexed"):
        if response.get(name) not in (0, None):
            return False
    calls = response.get("tool_calls")
    return isinstance(calls, list) and bool(calls) and not any(
        c.get("result_kind") == "prior_evidence_read"
        for c in calls if isinstance(c, dict)
    )


def _receipt_ledger(document: dict) -> list[dict]:
    response = document["response"]
    result = []
    for i, call in enumerate(response["tool_calls"]):
        if not isinstance(call, dict):
            raise ValueError("Invalid native receipt list")
        name = call.get("name")
        if not isinstance(name, str):
            raise ValueError("Missing native tool name")
        result.append({
            "call_order": i + 1,
            "tool": name,
            "arguments": call.get("arguments"),
            "success": call.get("success"),
            "result_kind": call.get("result_kind"),
            "operation_executed": call.get("operation_executed"),
            "response": call.get("response"),
            "error": call.get("error"),
        })
    return result


def _source_role(call: dict) -> str:
    name = call["tool"]
    args = call.get("arguments")
    if isinstance(args, dict) and isinstance(args.get("tool"), str):
        name = args["tool"]
    if call.get("success") is not True or call.get("operation_executed") is False:
        return "This call did not establish a successful newly executed source read."
    if call.get("result_kind") in ("tool_catalog", "prior_evidence_read", "contract_error"):
        return "Catalog/archived/contract metadata, not a fresh device state."
    return ROLE_NOTES.get(name, DEFAULT_ROLE_NOTE)


def _strip_note(calls: list[dict]) -> list[dict]:
    return [{k: v for k, v in item.items() if k != "generic_source_role_note"}
            for item in calls]


def _check_pair(baseline: dict, enhanced: dict, source_sha256: str) -> bool:
    if baseline.get("instructions") != enhanced.get("instructions"):
        return False
    if baseline.get("recorded_user_question") != enhanced.get("recorded_user_question"):
        return False
    a = baseline.get("native_tool_receipts")
    b = enhanced.get("native_tool_receipts")
    return (isinstance(a, list) and isinstance(b, list)
            and _hash(_strip_note(a)) == source_sha256
            and _hash(_strip_note(b)) == source_sha256)


def prepare(exports: list[Path], output_path: Path, seed: int) -> dict:
    if not exports:
        raise ValueError("At least one private export is required")
    eligible = []
    skipped_prior = 0
    skipped_invalid = 0
    for path in sorted(set(p.resolve() for p in exports)):
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("question"), str):
            skipped_invalid += 1
            continue
        if not _is_isolated(document):
            skipped_prior += 1
            continue
        try:
            ledger = _receipt_ledger(document)
        except ValueError:
            skipped_invalid += 1
            continue
        if not any(c.get("success") is True and c.get("operation_executed") is not False
                   and c.get("result_kind") not in ("tool_catalog", "prior_evidence_read")
                   for c in ledger):
            skipped_invalid += 1
            continue
        eligible.append((document["question"], ledger))
    if not eligible:
        raise ValueError("No eligible self-contained cases with native source receipts")
    output = _private_directory(output_path)
    (output / "answers").mkdir(mode=0o700)
    mapping = [True] * (len(eligible) // 2) + [False] * (
        len(eligible) - len(eligible) // 2
    )
    random.Random(seed).shuffle(mapping)
    manifests = []
    ratings = {"schema": SCHEMA, "rating_scale": "0=failed, 1=partial, 2=supported, n/a=not applicable",
               "categories": list(RUBRIC), "cases": {}}
    for index, ((question, calls), baseline_in_a) in enumerate(zip(eligible, mapping), 1):
        case_id = f"case-{index:03d}"
        source_sha = _hash(calls)
        baseline = {
            "instructions": INSTRUCTIONS,
            "recorded_user_question": question,
            "native_tool_receipts": calls,
        }
        annotated_calls = [
            {**call, "generic_source_role_note": _source_role(call)} for call in calls
        ]
        enhanced = {
            "instructions": INSTRUCTIONS,
            "recorded_user_question": question,
            "native_tool_receipts": annotated_calls,
        }
        if not _check_pair(baseline, enhanced, source_sha):
            raise ValueError("The paired conditions do not contain identical source receipts")
        variants = {"A": "baseline" if baseline_in_a else "role_notes",
                    "B": "role_notes" if baseline_in_a else "baseline"}
        for label in ("A", "B"):
            condition = variants[label]
            bundle = baseline if condition == "baseline" else enhanced
            _json_file(output / f"{case_id}-{label}.json", bundle)
        manifests.append({
            "case_id": case_id, "source_sha256": source_sha,
            "condition_map": variants,
            "source_tool_calls": len(calls),
        })
        ratings["cases"][case_id] = {
            label: {"ratings": {category: None for category in RUBRIC},
                    "elapsed_ms": None}
            for label in ("A", "B")
        }
    _json_file(output / "private_manifest.json", {
        "schema": SCHEMA, "seed": seed, "cases": manifests,
        "warning": "PRIVATE - reveals condition assignment and source hashes",
    })
    _json_file(output / "blind_ratings.json", ratings)
    _private_write(output / "README_PRIVATE.txt",
                   "PRIVATE: source bundles and answers contain raw home device data.\n"
                   "For each case, send A and B to the SAME model with independent "
                   "fresh contexts, randomised order, deterministic model settings, "
                   "and NO live MCP access. Store unedited answers in answers/case-XXX-A.txt "
                   "and -B.txt, plus model elapsed_ms and independent blind 0/1/2 "
                   "ratings in blind_ratings.json. Never copy these files into GitHub.\n"
                   "Then run 'report --directory PATH --output PRIVATE_REPORT'. "
                   "Do not review the condition mapping before blinded scoring.\n"
                   "This isolates SOURCE INTERPRETATION only, not autonomous tool choice.\n")
    return {"created_case_pairs": len(manifests), "skipped_prior_context": skipped_prior,
            "skipped_invalid": skipped_invalid, "raw_private_source_included": True,
            "live_actions_executed": 0, "model_calls_executed": 0}


def _valid_rating(value: Any) -> bool:
    return value == "n/a" or (type(value) is int and value in (0, 1, 2))


def report(directory: Path, output_path: Path) -> dict:
    directory = directory.resolve()
    if output_path.resolve() == directory / "private_manifest.json":
        raise ValueError("Cannot overwrite the private manifest")
    manifest = json.loads((directory / "private_manifest.json").read_text(encoding="utf-8"))
    ratings_file = json.loads((directory / "blind_ratings.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA or ratings_file.get("schema") != SCHEMA:
        raise ValueError("Benchmark schema mismatch")
    changes: dict[str, list[int]] = {name: [] for name in RUBRIC}
    timing = []
    matched_pairs = 0
    missing_answers = 0
    missing_ratings = 0
    for case in manifest["cases"]:
        key = case["case_id"]
        bundles = [json.loads((directory / f"{key}-{label}.json").read_text(encoding="utf-8"))
                   for label in ("A", "B")]
        baseline = bundles[0] if case["condition_map"]["A"] == "baseline" else bundles[1]
        enhanced = bundles[0] if case["condition_map"]["A"] == "role_notes" else bundles[1]
        if not _check_pair(baseline, enhanced, case["source_sha256"]):
            raise ValueError("Frozen source integrity mismatch: " + key)
        answers = [directory / "answers" / f"{key}-{label}.txt" for label in ("A", "B")]
        if not all(p.is_file() and p.stat().st_size > 0 for p in answers):
            missing_answers += 1
            continue
        scored = ratings_file.get("cases", {}).get(key, {})
        values = {}
        for label in ("A", "B"):
            record = scored.get(label, {})
            scores = record.get("ratings", {})
            if (not isinstance(scores, dict)
                    or not all(_valid_rating(scores.get(category)) for category in RUBRIC)):
                values = {}
                break
            values[label] = record
        if not values:
            missing_ratings += 1
            continue
        matched_pairs += 1
        base = values["A"] if case["condition_map"]["A"] == "baseline" else values["B"]
        note = values["A"] if case["condition_map"]["A"] == "role_notes" else values["B"]
        for category in RUBRIC:
            b, n = base["ratings"][category], note["ratings"][category]
            if b != "n/a" and n != "n/a":
                changes[category].append(n - b)
        bms, nms = base.get("elapsed_ms"), note.get("elapsed_ms")
        if (type(bms) in (int, float) and type(nms) in (int, float)
                and 0 <= bms < 3600000 and 0 <= nms < 3600000):
            timing.append(round(nms - bms, 3))
    summary = {
        "schema": "homebrain-v2-fixed-source-report.v1",
        "model_calls_executed_by_this_tool": 0,
        "live_hub_actions_executed": 0,
        "case_pairs_prepared": len(manifest["cases"]),
        "blind_reviewed_pairs": matched_pairs,
        "missing_pair_answers": missing_answers,
        "missing_pair_ratings": missing_ratings,
        "condition_effects": {
            name: {
                "rated_pairs": len(samples),
                "mean_role_notes_minus_baseline": (
                    round(statistics.mean(samples), 3) if samples else None
                ),
                "role_notes_better": sum(s > 0 for s in samples),
                "tied": sum(s == 0 for s in samples),
                "baseline_better": sum(s < 0 for s in samples),
            }
            for name, samples in changes.items()
        },
        "elapsed_ms_difference_role_notes_minus_baseline": {
            "paired_samples": len(timing),
            "median_difference": round(statistics.median(timing), 3) if timing else None,
        },
        "interpretation": (
            "Paired, blinded descriptive source-interpretation experiment only; "
            "scores require human review, cannot prove live autonomous tool choice, "
            "write safety, physical action effects, or population-level reliability."
        ),
        "private_values_exported": False,
    }
    if output_path.exists():
        raise ValueError("Report destination already exists; use a new private file")
    _json_file(output_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("prepare", help="Freeze private source-isolated export pairs")
    setup.add_argument("--out", type=Path, required=True, help="PRIVATE directory outside repo")
    setup.add_argument("--seed", type=int, default=42)
    setup.add_argument("exports", nargs="+", type=Path)
    grade = sub.add_parser("report", help="Evaluate blind paired ratings; no auto grading")
    grade.add_argument("--directory", type=Path, required=True)
    grade.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        outcome = (prepare(args.exports, args.out, args.seed)
                   if args.command == "prepare"
                   else report(args.directory, args.output))
    except (ValueError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        parser.error("Private benchmark could not be completed: "
                     + type(exc).__name__ + " (do not share raw input).")
    print(json.dumps(outcome, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

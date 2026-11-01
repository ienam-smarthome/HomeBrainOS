#!/usr/bin/env python3
"""Q1 fixed offline evidence packets and *metadata-only* paired-run preflight.

Exports the exact model-visible prompt/evidence from the curated manifest while
withholding reviewer obligations. Pair checks establish input-fingerprint and
first-attempt *metadata* compatibility, not source truth, model correctness,
actual prompt delivery, or Claude equivalence.

No network, cloud-model, Hubitat/HA, or live-device actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from answer_quality_scorecard import CURATED, ScorecardInputError

PACKET_SCHEMA = "homebrain-answer-quality-fixed-packet.v1"
RUN_SCHEMA = "homebrain-answer-quality-offline-run.v1"
PAIR_SCHEMA = "homebrain-answer-quality-pair-preflight.v1"
TOOL_POLICY = "offline-evidence-only-no-tools"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
SAFE_MODEL_RE = re.compile(r"^[a-zA-Z0-9_.:/-]{1,80}$")
PROVIDERS = {"ollama-cloud", "ollama-local", "openai", "anthropic", "other-disclosed"}
RUN_FIELDS = {
    "case_id", "packet_sha256", "answer_sha256", "model", "provider",
    "build_sha", "attempt_index", "elapsed_ms",
}


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_fixed_packets(manifest: Path = CURATED) -> list[dict[str, Any]]:
    """Only model-facing fields; no rubrics, verdicts, or private reviews."""
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("schema") != "homebrain-answer-quality-cases.v1":
        raise ScorecardInputError("Unexpected curated packet schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ScorecardInputError("Curated cases must be a nonempty list")
    seen: set[str] = set()
    packets = []
    for case in cases:
        if not isinstance(case, dict):
            raise ScorecardInputError("Curated case must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not SAFE_ID_RE.fullmatch(case_id):
            raise ScorecardInputError("Invalid curated case ID")
        if case_id in seen:
            raise ScorecardInputError("Duplicate curated case ID")
        seen.add(case_id)
        prompt = case.get("prompt")
        evidence = case.get("available_evidence")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ScorecardInputError(f"{case_id}: missing prompt")
        if (not isinstance(evidence, list) or not evidence
                or any(not isinstance(item, str) or not item.strip() for item in evidence)):
            raise ScorecardInputError(f"{case_id}: invalid source packet")
        if not case.get("required_findings") or not case.get("forbidden_claims"):
            raise ScorecardInputError(f"{case_id}: missing private reviewer rubric")
        if case.get("reference_type") != "curated_offline_packet" or case.get("read_only") is not True:
            raise ScorecardInputError(f"{case_id}: only read-only offline packets allowed")
        source = {
            "schema": PACKET_SCHEMA,
            "case_id": case_id,
            "question": prompt,
            "available_evidence": evidence,
            "tool_policy": TOOL_POLICY,
        }
        packets.append({**source, "packet_sha256": canonical_digest(source)})
    return packets


def _run_field(value: Any, regex: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not regex.fullmatch(value):
        raise ScorecardInputError(f"{label} has invalid format")
    return value


def validate_run_manifest(payload: Any, packets: list[dict[str, Any]]) -> dict[str, dict]:
    """Require exact SHA-compatible first-attempt metadata; reject raw answers."""
    if not isinstance(payload, dict) or payload.get("schema") != RUN_SCHEMA:
        raise ScorecardInputError("Unexpected offline-run metadata schema")
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise ScorecardInputError("runs must be an array")
    expected = {packet["case_id"]: packet["packet_sha256"] for packet in packets}
    out: dict[str, dict] = {}
    for run in runs:
        if not isinstance(run, dict) or set(run) != RUN_FIELDS:
            raise ScorecardInputError("Run fields must be metadata-only; raw answers are forbidden")
        case_id = _run_field(run["case_id"], SAFE_ID_RE, "case_id")
        if case_id not in expected:
            raise ScorecardInputError("Run references unknown curated case")
        if case_id in out:
            raise ScorecardInputError("Duplicate run for case")
        digest = _run_field(run["packet_sha256"], SHA256_RE, "packet_sha256")
        if digest != expected[case_id]:
            raise ScorecardInputError(f"{case_id}: source packet differs from frozen manifest")
        _run_field(run["answer_sha256"], SHA256_RE, "answer_sha256")
        _run_field(run["build_sha"], GIT_SHA_RE, "build_sha")
        _run_field(run["model"], SAFE_MODEL_RE, "model")
        if not isinstance(run["provider"], str) or run["provider"] not in PROVIDERS:
            raise ScorecardInputError("Unrecognized provider")
        if type(run["attempt_index"]) is not int or run["attempt_index"] != 1:
            raise ScorecardInputError("Only explicitly recorded first attempts may pair")
        ms = run["elapsed_ms"]
        if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not math.isfinite(ms) or ms < 0:
            raise ScorecardInputError("elapsed_ms must be actual nonnegative wall time")
        out[case_id] = run
    return out


def pair_metadata(
    baseline: Any,
    candidate: Any,
    packets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report comparability only. Do not infer factual correctness or improvements."""
    before = validate_run_manifest(baseline, packets)
    after = validate_run_manifest(candidate, packets)
    matched = sorted(set(before) & set(after))
    return {
        "schema": PAIR_SCHEMA,
        "quality_measurement_status": "not_measured",
        "comparison_status": (
            "metadata_pairs_ready_for_independent_review" if matched
            else "not_measured"
        ),
        "defined_offline_cases": len(packets),
        "baseline_runs": len(before),
        "candidate_runs": len(after),
        "paired_cases": len(matched),
        "paired_case_ids": matched,
        "baseline_only_case_ids": sorted(set(before) - set(after)),
        "candidate_only_case_ids": sorted(set(after) - set(before)),
        "limitations": [
            "This preflight verifies hashes and run metadata, not actual model input delivery",
            "A supplied Git SHA format does not independently authenticate the deployed code",
            "No automatic factual, safety, clarity, first-answer or causal judgement is made",
            "Curated offline source packets are not live HomeBrain production evidence",
            "Model responses, human source review, and cost disclosures are still required",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="Export frozen offline model-facing packets")
    export.add_argument("--case-id", action="append", default=[])
    export.add_argument("--output", type=Path)
    compare = sub.add_parser("compare", help="Compare metadata from two model runs")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    packets = build_fixed_packets()
    if args.command == "export":
        wanted = set(args.case_id)
        known = {item["case_id"] for item in packets}
        if wanted - known:
            raise ScorecardInputError("Unknown curated case ID selected")
        entries = [item for item in packets if not wanted or item["case_id"] in wanted]
        content = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in entries)
    else:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        content = json.dumps(pair_metadata(baseline, candidate, packets), indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare PRIVATE human-review drafts from genuine first-answer V2 exports.

This tool makes NO calls to Hubitat, Home Assistant, models, GitHub or MCP.
It does not grade answers or infer truth from successful tool calls.
It accepts only exact, read-only LIVE prompts from the frozen legacy catalog.
The curated 40-case catalog uses synthetic/anonymized source packets and must
be evaluated separately; a live prompt match is not a frozen-evidence match.

Usage (outside the repository, with private inputs/outputs):
  python scripts/first_answer_live_intake.py capture.json --output private-drafts.json
  python scripts/first_answer_live_intake.py first.json second.json \
      --build-sha ACTUAL_40_HEX_GIT_COMMIT --output private-drafts.json

The result is a scorecard-compatible DRAFT with null human scores. The scorecard
rejects it until an independent reviewer fills the required fields.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai-v2" / "tools"))

from first_answer_audit import AuditInputError, audit_export  # noqa: E402
from answer_quality_scorecard import (  # noqa: E402
    LEGACY, CURATED, REVIEW_KEYS, load_catalog,
)

SCHEMA = "homebrain-answer-quality-reviews.v1"
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
READ_PREFIXES = ("hub_get_", "hub_list_", "hub_read_", "hub_search_")
SOURCE_KINDS = frozenset(("tool_catalog", "local_clock_read", "local_catalog_read"))
REVIEW_NOTE = (
    "DRAFT ONLY: no factual grounding, causal calibration, usefulness or "
    "safety score has been assigned. Open and independently review the "
    "original PRIVATE answer and receipts; preserve read scopes, focal "
    "output, command versus report, decision evidence and unknowns. "
    "Fill reviewer, build SHA (if missing), all five review grades and "
    "all three claim counters before running the existing scorecard."
)


class IntakeError(ValueError):
    """Input cannot safely be counted as one frozen live first-answer case."""


def _catalog_prompts() -> tuple[dict[str, dict], dict[str, dict]]:
    catalog = load_catalog()
    old = json.loads(LEGACY.read_text(encoding="utf-8"))
    curated = json.loads(CURATED.read_text(encoding="utf-8"))
    live = {
        item["prompt"].strip(): item for item in old["tasks"]
        if isinstance(item.get("prompt"), str)
    }
    synthetic = {
        item["prompt"].strip(): item for item in curated["cases"]
        if isinstance(item.get("prompt"), str)
    }
    if (len(live) != 13 or len(synthetic) != 40 or len(catalog) != 53):
        raise IntakeError("Frozen benchmark catalog must be complete and unchanged")
    return live, synthetic


def _safe_read_only(receipt: dict) -> bool:
    """Reject uncertain native writes; never test the permission layer live."""
    name = receipt.get("name")
    if not isinstance(name, str) or receipt.get("read_only") is False:
        return False
    if receipt.get("result_kind") in SOURCE_KINDS:
        return receipt.get("operation_executed") is False
    if name.startswith(READ_PREFIXES):
        return True
    if name == "homebrain_read_device_monitor":
        args = receipt.get("arguments")
        return isinstance(args, dict) and args.get("mode") in ("status", "history")
    return False


def prepare_one(document: dict[str, Any], source_bytes: bytes, *,
                build_sha: str | None = None) -> tuple[dict, dict]:
    """Return source-minimal private provenance and a NOT-YET-SCORED review."""
    try:
        evidence = audit_export(document)
    except AuditInputError as exc:
        raise IntakeError("Input is not a compatible Technical JSON export") from exc

    live, synthetic = _catalog_prompts()
    exact = document["question"].strip()
    if exact in synthetic:
        raise IntakeError(
            "This is a curated offline source-packet prompt. Use the fixed-source "
            "evaluation with its matched original packet, not a live capture."
        )
    task = live.get(exact)
    if task is None:
        raise IntakeError(
            "Question does not exactly match an eligible frozen live task. "
            "Do not assign a case using approximate wording."
        )
    if task.get("read_only") is not True:
        raise IntakeError(
            "Frozen write-action tasks require a mocked executor; never "
            "run them as a live benchmark."
        )

    response = document["response"]
    for field in ("prior_receipts_used", "prior_sources_indexed"):
        prior = response.get(field)
        if prior is not None and (type(prior) is not int or prior < 0):
            raise IntakeError("Prior-context metadata must be a nonnegative integer")
        if prior:
            raise IntakeError(
                "Source receipts include earlier conversation context; "
                "not an isolated first-answer benchmark."
            )
    if any(not _safe_read_only(row) for row in response["tool_calls"]):
        raise IntakeError(
            "The capture contains a write, an unknown tool category, or an "
            "unverified read-only operation; exclude it from this live cohort."
        )
    if build_sha is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", build_sha):
        raise IntakeError("An explicit build SHA must be 40 hexadecimal characters")

    case_id = task["key"]
    digest = hashlib.sha256(source_bytes).hexdigest()
    # Hashes link source files without copying names, answers, raw logs,
    # device IDs, timestamps or request arguments to review drafts.
    meta = {
        "case_id": case_id,
        "catalog_origin": "legacy_golden_tasks",
        "source_kind": "read_only_live_technical_export",
        "prompt_match": "exact_frozen_live_prompt",
        "question_sha256": hashlib.sha256(exact.encode("utf-8")).hexdigest(),
        "source_file_sha256": digest,
        "first_attempt": "reported_zero_prior_context_not_independently_proven",
        "human_review_required": True,
        "quality_status": "not_measured",
        "build_sha_from_export": "not_verified",
        "source_summary": {
            "version": evidence["build"]["version"],
            "native_attempts": evidence["native_tools"]["attempted"],
            "successful_attempts": evidence["native_tools"]["successful"],
            "failed_attempts": evidence["native_tools"]["failed"],
            "event_source_receipts": evidence["history_receipts"]["event_scope_receipts"],
            "event_rows_returned_total": evidence["history_receipts"]["event_rows_returned_total"],
            "app_log_source_receipts": evidence["log_receipts"]["source_receipts"],
            "app_log_rows_returned_total": evidence["log_receipts"]["rows_returned_total"],
            "any_history_limit_reached": evidence["history_receipts"]["any_request_limit_reached"],
            "source_windows_complete": "not_established",
            "controller_or_physical_cause_verified": "human_review_required",
            "model_rounds": evidence["performance"]["model_rounds"],
        },
    }
    latency_ms = evidence["performance"]["browser_elapsed_ms"]
    draft = {
        "case_id": case_id,
        "model": document["model"],  # Private only; NEVER publish these drafts.
        "build_sha": build_sha.lower() if build_sha is not None else None,
        "reviewer": None,
        "evidence_reference": "sha256:" + digest,
        "review": {
            **{key: None for key in REVIEW_KEYS},
            "factual_conclusions_evaluated": None,
            "grounded_factual_conclusions": None,
            "unsupported_definitive_causal_claims": None,
        },
        "metrics": {
            "latency_seconds": round(latency_ms / 1000, 3) if latency_ms is not None else None,
            "tool_calls": evidence["native_tools"]["attempted"],
        },
    }
    return meta, draft


def prepare_many(sources: list[tuple[bytes, dict]], *,
                 build_sha: str | None = None) -> dict:
    metadata, drafts = [], []
    seen = set()
    for raw, document in sources:
        meta, review = prepare_one(document, raw, build_sha=build_sha)
        key = (review["case_id"], review["model"], review["build_sha"])
        if key in seen:
            raise IntakeError(
                "Duplicate frozen case/model/build capture. Do not silently "
                "select a better attempt or replace the first failed answer."
            )
        seen.add(key)
        metadata.append(meta)
        drafts.append(review)
    return {
        "schema": SCHEMA,
        "intake_version": "homebrain-v2-live-intake.v1",
        "intake_status": "pending_independent_source_review",
        "quality_status": "not_measured",
        "scorecard_ready": False,
        "note": REVIEW_NOTE,
        "intake_metadata": metadata,
        "reviews": drafts,
    }


def _read_private_capture(path: Path) -> tuple[bytes, dict]:
    try:
        if path.stat().st_size > MAX_CAPTURE_BYTES:
            raise IntakeError("Technical JSON exceeds private intake size limit")
        raw = path.read_bytes()
        if len(raw) > MAX_CAPTURE_BYTES:
            raise IntakeError("Technical JSON exceeds private intake size limit")
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise IntakeError("Technical JSON root must be an object")
        return raw, decoded
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, IntakeError):
            raise
        raise IntakeError("Cannot read the private Technical JSON export") from exc


def _write_private_new_file(path: Path, report: dict) -> None:
    """Atomic create-only private file; never overwrite an existing review."""
    content = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="+", type=Path,
                        help="PRIVATE original V2 Technical JSON first answers")
    parser.add_argument("--build-sha",
                        help="Exact deployed Git commit; omit rather than guessing")
    parser.add_argument("--output", required=True, type=Path,
                        help="New PRIVATE draft file (cannot overwrite)")
    args = parser.parse_args(argv)
    try:
        sources = [_read_private_capture(path) for path in args.captures]
        result = prepare_many(sources, build_sha=args.build_sha)
        _write_private_new_file(args.output, result)
    except (IntakeError, OSError) as exc:
        parser.error(type(exc).__name__ + ": " + str(exc))
    print("Prepared " + str(len(result["reviews"])) +
          " private, UNGRADED frozen-case review draft(s). "
          "No scorecard accuracy or safety result is claimed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

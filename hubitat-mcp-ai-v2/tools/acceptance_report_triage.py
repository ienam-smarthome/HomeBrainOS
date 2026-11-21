#!/usr/bin/env python3
"""Offline, privacy-safe triage of redacted HomeBrain V2 acceptance reports.

This does NOT grade model answers, attest original source integrity, verify
MCP token enforcement or modify frozen captures.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "homebrain-v2-source-real-acceptance-report.v1"
TRIAGE_SCHEMA = "homebrain-v2-acceptance-report-triage.v1"


class InvalidReport(ValueError):
    """The redacted report is structurally inconsistent."""


def _object(value: Any) -> dict:
    if not isinstance(value, dict):
        raise InvalidReport("Expected object")
    return value


def _safe_identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", value):
        raise InvalidReport("Invalid " + name)
    return value


def _int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidReport("Invalid " + name)
    return value


def triage_report(report: dict) -> dict:
    """Derive ungraded, per-case review priorities from whitelisted fields."""
    report = _object(report)
    if report.get("schema") != REPORT_SCHEMA:
        raise InvalidReport("Unsupported report schema")
    ids = report.get("captured_case_ids_in_review_order")
    summary = _object(report.get("summary"))
    details = summary.get("details")
    if not isinstance(ids, list) or not isinstance(details, list) or len(ids) != len(details):
        raise InvalidReport("Case IDs/details mismatch")
    if (any(not isinstance(i, str) or not i or len(i) > 100 for i in ids)
            or len(ids) != len(set(ids))):
        raise InvalidReport("Invalid case IDs")
    for ident in ids:
        _safe_identifier(ident, "case ID")
    if len(ids) != _int(report.get("cases_captured"), "cases_captured"):
        raise InvalidReport("Captured case count mismatch")
    if len(ids) > _int(report.get("cases_expected"), "cases_expected"):
        raise InvalidReport("Captured cases exceed expected")
    failures = report.get("failed_first_answer_case_ids")
    if not isinstance(failures, list) or any(i not in ids for i in failures):
        raise InvalidReport("Invalid failure IDs")
    permission = _object(report.get("permission_evidence"))
    cases = []
    for ident, detail in zip(ids, details):
        item = _object(detail)
        tools = _object(item.get("native_tools"))
        history = _object(item.get("history_receipts"))
        logs = _object(item.get("log_receipts"))
        perf = _object(item.get("performance"))
        elapsed = perf.get("server_elapsed_ms")
        if elapsed is not None:
            elapsed = _int(elapsed, "server_elapsed_ms")
        attempted = _int(tools.get("attempted"), "tool attempts")
        failed = _int(tools.get("failed"), "tool failures")
        if failed > attempted:
            raise InvalidReport("Tool failures exceed attempts")
        log_mismatch = _int(
            logs.get("receipts_where_reported_matches_exceed_returned"),
            "log count mismatch",
        )
        flags = []
        if ident in failures:
            flags.append("first_answer_failed")
        if failed:
            flags.append("native_tool_attempt_failed")
        if history.get("any_request_limit_reached") is True:
            flags.append("event_history_row_limit_reached")
        if logs.get("any_log_request_limit_reached") is True:
            flags.append("past_log_row_limit_reached")
        if log_mismatch:
            flags.append("past_log_matches_exceed_returned_rows")
        cases.append({
            "case_id": ident,
            "server_elapsed_ms": elapsed,
            "native_tool_attempts": attempted,
            "native_tool_failures": failed,
            "review_flags": flags,
            "human_answer_quality": "not_measured",
        })
    severity = {
        "first_answer_failed": 5,
        "native_tool_attempt_failed": 4,
        "event_history_row_limit_reached": 3,
        "past_log_row_limit_reached": 3,
        "past_log_matches_exceed_returned_rows": 2,
    }
    prioritized = sorted(cases, key=lambda c: (
        -max((severity[x] for x in c["review_flags"]), default=0),
        -len(c["review_flags"]),
        -(c["server_elapsed_ms"] or 0),
        c["case_id"],
    ))
    read_only_source_report = (
        permission.get("per_client_read_enabled_reported") is True
        and permission.get("per_client_write_enabled_reported") is False
    )
    return {
        "schema": TRIAGE_SCHEMA,
        "benchmark_pack": _safe_identifier(report.get("benchmark_pack"), "benchmark pack"),
        "expected_addon_version": _safe_identifier(report.get("expected_addon_version"), "version"),
        "captured_case_count": len(ids),
        "unscored": True,
        "promotion_ready": False,
        "source_reported_read_only_client": read_only_source_report,
        # A redacted report cannot independently establish any of these.
        "independent_permission_enforcement_verified": False,
        "original_source_independently_verified": False,
        "first_attempt_independently_verified": False,
        "case_review_order": prioritized,
        "required_next_evidence": [
            "Original unmodified per-case first-answer JSON with native receipts",
            "Independent operator source and first-attempt attestation",
            "Independent verification of dedicated MCP client write prohibition",
            "Independent atomic-claim and useful-complete scoring",
        ],
        "warning": "Tool success and row limits do NOT grade answer accuracy. "
                   "Missing rows do NOT prove historical absence.",
        "privacy": "Whitelisted report fields only; no raw labels, answers, logs or arguments.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        rendered = json.dumps(triage_report(report), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, TypeError):
        parser.error("Invalid or unreadable redacted acceptance report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline, private V1↔V2 first-answer review ledger.

This is NOT a model grader, an MCP client, a Home Assistant integration or a
claim of historical truth. The operator supplies manual source-led ratings.
Raw first-answer captures stay on the operator's local machine. This script
only checks their existence, size and SHA-256, then reports supplied scores
and basic provenance/comparability flags; it never copies raw source data
into the report, contacts a device or interprets a model's untrusted reply.

Usage:
  python hubitat-mcp-ai-v2/evaluation/v1_v2_pairs.py \
    private/paired_manifest.json --output private/paired_summary.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "homebrain-v1-v2-first-answer-pairs.v1"
CRITERIA = ("factual_grounding", "source_completeness",
            "causal_calibration", "usefulness")
DOMAINS = frozenset({
    "current_state", "historical_measurement", "comparison",
    "threshold_timing", "causal_transition", "system_health",
    "rule_machine", "read_only_safety",
})
MAX_CASES = 32
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
PAIR_ID = re.compile(r"^pair-[0-9]{2}$")


class PairReviewError(ValueError):
    pass


def _date(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PairReviewError("UTC timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PairReviewError("Timestamp must be ISO 8601 with offset") from None
    if parsed.tzinfo is None:
        raise PairReviewError("Timestamp requires an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _capture(path: Path, root: Path) -> dict:
    if not isinstance(path, Path) or path.is_absolute():
        raise PairReviewError("Capture path must be relative to the private manifest")
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise PairReviewError("Capture path must stay within the private folder") from None
    if not target.is_file():
        raise PairReviewError("A referenced first-answer capture is missing")
    size = target.stat().st_size
    if size > MAX_ARTIFACT_BYTES or size == 0:
        raise PairReviewError("First-answer capture has an invalid or oversized length")
    digest = hashlib.sha256()
    with target.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    # Never return the file path or contents in the report.
    return {"sha256": digest.hexdigest(), "bytes": size}


def _rating(scores: Any) -> dict | None:
    if scores is None:
        return None
    if not isinstance(scores, dict) or set(scores) != set(CRITERIA):
        raise PairReviewError("Scores must contain exactly the four documented criteria")
    for name, value in scores.items():
        if name == "causal_calibration" and value is None:
            continue
        if type(value) is not int or value not in (0, 1, 2):
            raise PairReviewError("Each applicable score must be 0, 1 or 2")
    applicable = [v for v in scores.values() if v is not None]
    return {
        "scores": dict(scores), "points": sum(applicable),
        "maximum": len(applicable) * 2,
    }


def _review(value: Any) -> dict:
    if not isinstance(value, dict):
        raise PairReviewError("An arm needs an explicit human evidence review")
    fields = ("supported_facts", "unsupported_definite_causes",
              "unknowns", "tool_errors", "missing_sources")
    if any(key not in value for key in fields):
        raise PairReviewError("Human review requires all five evidence categories")
    for field in fields:
        v = value[field]
        if (not isinstance(v, list) or len(v) > 60
                or any(not isinstance(x, str) or not x.strip() for x in v)):
            raise PairReviewError("Human review fields must contain string lists")
    return {key + "_count": len(value[key]) for key in fields}


def _arm(arm: Any, root: Path) -> dict:
    if not isinstance(arm, dict):
        raise PairReviewError("Each arm must be an object")
    for name in ("installed_version", "model", "provider"):
        if not isinstance(arm.get(name), str) or not arm[name].strip():
            raise PairReviewError("Installed version, model and provider must be supplied, not inferred")
        if len(arm[name]) > 120:
            raise PairReviewError("Arm metadata is too long")
    stamp = _date(arm.get("captured_at_utc"))
    relative = arm.get("first_answer_capture")
    if not isinstance(relative, str):
        raise PairReviewError("First-answer capture filename is required")
    evidence = _capture(Path(relative), root)
    reviewer = _review(arm.get("human_review"))
    ratings = _rating(arm.get("scores"))
    writes = arm.get("unexpected_mutations")
    if not isinstance(writes, list) or any(not isinstance(x, str) for x in writes):
        raise PairReviewError("Unexpected mutations must be explicitly recorded as a list")
    errors = arm.get("tool_attempt_errors", [])
    if not isinstance(errors, list) or any(not isinstance(x, str) for x in errors):
        raise PairReviewError("Tool error list is invalid")
    elapsed = arm.get("elapsed_ms")
    if elapsed is not None and (type(elapsed) not in (int, float) or elapsed < 0):
        raise PairReviewError("Elapsed time must be a non-negative numeric reading")
    return {
        "installed_version": arm["installed_version"],
        "model": arm["model"],
        "provider": arm["provider"],
        "captured_at_utc": stamp.isoformat(),
        "capture": evidence,
        "score": ratings,
        "review_counts": reviewer,
        "unexpected_mutations_count": len(writes),
        "tool_attempt_error_count": len(errors),
        "elapsed_ms": elapsed,
    }


def validate(payload: Any, root: Path) -> dict:
    """Validate manually captured pairs without inspecting untrusted answer text."""
    root = root.resolve()
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise PairReviewError("Unknown V1/V2 paired-review schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise PairReviewError("Provide between 1 and 32 cases")
    seen: set[str] = set()
    result = []
    for case in cases:
        if not isinstance(case, dict):
            raise PairReviewError("Each case must be an object")
        key = case.get("id")
        if not isinstance(key, str) or not PAIR_ID.fullmatch(key) or key in seen:
            raise PairReviewError("Each pair needs a unique pair-NN ID")
        seen.add(key)
        domain = case.get("domain")
        if not isinstance(domain, str) or domain not in DOMAINS:
            raise PairReviewError("Unknown evidence domain")
        question = case.get("question")
        if not isinstance(question, str) or not 8 <= len(question.strip()) <= 2000:
            raise PairReviewError("The exact shared user question must be recorded")
        if case.get("read_only") is not True:
            raise PairReviewError("Paired live acceptance is read-only; reject write requests")
        window = case.get("window_utc")
        if window is not None:
            if not isinstance(window, dict) or set(window) != {"start", "end"}:
                raise PairReviewError("History window requires start/end UTC")
            if _date(window["end"]) <= _date(window["start"]):
                raise PairReviewError("History end must exceed start")
        arms = case.get("arms")
        if not isinstance(arms, dict) or not arms:
            raise PairReviewError("Record at least one initial arm")
        if not set(arms).issubset({"v1", "v2"}):
            raise PairReviewError("Only V1/V2 arms are accepted")
        reports = {name: _arm(arm, root) for name, arm in arms.items()}
        paired = set(reports) == {"v1", "v2"}
        delta = None
        provider_equal = None
        model_equal = None
        if paired:
            a, b = reports["v1"], reports["v2"]
            delta = abs((_date(a["captured_at_utc"]) -
                         _date(b["captured_at_utc"])).total_seconds())
            provider_equal = a["provider"] == b["provider"]
            model_equal = a["model"] == b["model"]
        result.append({
            "id": key, "domain": domain, "paired": paired,
            "window_recorded": window is not None,
            "capture_delta_seconds": delta,
            "live_state_comparable_within_5m": (
                delta <= 300 if paired and domain in
                {"current_state", "system_health", "read_only_safety"} else None
            ),
            "same_provider": provider_equal, "same_model": model_equal,
            "arms": reports,
        })
    return {
        "schema": SCHEMA, "cases": result,
        "counts": {
            "cases": len(result),
            "paired": sum(item["paired"] for item in result),
            "fully_rated": sum(
                item["paired"] and all(a["score"] is not None
                                       for a in item["arms"].values())
                for item in result
            ),
            "read_only_mutation_flags": sum(
                a["unexpected_mutations_count"]
                for item in result for a in item["arms"].values()
            ),
        },
        "note": (
            "Review scores are HUMAN supplied and unverified by this tool. "
            "A hash only identifies a local capture; it does not prove source "
            "coverage, physical state, correctness or absence of unseen events. "
            "This report deliberately contains no raw questions, device names, "
            "MCP receipts, answers, tokens or first-answer file paths."
        ),
    }


def render_markdown(report: dict) -> str:
    def rating(a):
        if a is None or a.get("score") is None:
            return "—"
        score = a["score"]
        return f"{score['points']}/{score['maximum']}"
    lines = [
        "# V1 versus V2 — private paired first-answer review",
        "",
        "Human ratings; not automated truth judgments or independent verification.",
        "",
        "| Pair | Domain | V1 | V2 | Captures | Matching model/provider |",
        "|---|---|---:|---:|---|---|",
    ]
    for c in report["cases"]:
        arms = c["arms"]
        model_equivalence = (
            "Both" if c["same_model"] is True and c["same_provider"] is True
            else "Different" if c["paired"] else "Not paired"
        )
        captures = "Both" if c["paired"] else "Incomplete"
        lines.append(
            f"| {c['id']} | {c['domain']} | {rating(arms.get('v1'))} | "
            f"{rating(arms.get('v2'))} | {captures} | {model_equivalence} |"
        )
    lines.extend(["", "## Capture fingerprints (local files only)", "",
                  "| Pair | System | SHA-256 | Bytes |",
                  "|---|---|---|---:|"])
    for item in report["cases"]:
        for arm in ("v1", "v2"):
            entry = item["arms"].get(arm)
            if entry:
                capture = entry["capture"]
                lines.append(
                    f"| {item['id']} | {arm.upper()} | "
                    f"`{capture['sha256']}` | {capture['bytes']} |"
                )
    lines.extend([
        "",
        f"Pairs captured: **{report['counts']['paired']}/{report['counts']['cases']}**. "
        f"Pairs fully rated: **{report['counts']['fully_rated']}**.",
        "",
        f"Reported unexpected mutation flags: **{report['counts']['read_only_mutation_flags']}**. "
        "This is a reviewer-supplied count, not independent safety confirmation.",
        "",
        "A five-minute capture separation for current state/system health is "
        "a comparability warning, not evidence of false data.",
        "",
        report["note"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Local private manifest JSON")
    parser.add_argument("--output", type=Path, help="Optional private Markdown output")
    args = parser.parse_args()
    try:
        source = args.manifest.resolve()
        if not source.is_file() or source.stat().st_size > MAX_ARTIFACT_BYTES:
            raise PairReviewError("Private manifest missing or oversized")
        payload = json.loads(source.read_text(encoding="utf-8"))
        report = validate(payload, source.parent)
        result = render_markdown(report)
        if args.output:
            # Intentional local operator output only; no repository writes.
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result, encoding="utf-8")
            print("Paired review complete; private Markdown written locally.")
        else:
            print(result)
        return 0
    except (PairReviewError, ValueError, OSError) as exc:
        # Never echo private manifest content, raw tool replies or paths.
        parser.exit(2, f"Review rejected: {type(exc).__name__}\n")


if __name__ == "__main__":
    raise SystemExit(main())

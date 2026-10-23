"""Offline, paired audit-answer diagnostic. Not an AI judge or a live Hubitat tool.

Compare only MODEL-WRITTEN advisory text against the same benchmark evidence.
A deterministic host audit appended to a HomeBrain response must not earn
credit for words the model never wrote. All matches are lexical diagnostics,
not a claim that a model reasoned correctly.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_ADVISORY = re.compile(
    r"(?ms)^### Reasoned answer[^\n]*\n(.*?)(?=^### |\Z)"
)


def extract_answer(entry: Any) -> tuple[str, str]:
    """Keep the model advisory, never the host's deterministic audit body."""
    if isinstance(entry, str):
        return entry.strip(), "available" if entry.strip() else "empty"
    if not isinstance(entry, dict):
        return "", "missing"
    ai = entry.get("ai_analysis") or {}
    status = ai.get("status") if isinstance(ai, dict) else None
    if status and status != "completed":
        return "", str(status)
    answer = entry.get("answer")
    if isinstance(answer, str):
        return answer.strip(), "available" if answer.strip() else "empty"
    report = entry.get("message")
    if not isinstance(report, str):
        return "", "missing"
    match = _ADVISORY.search(report)
    if match:
        answer = match.group(1).strip()
        return answer, "available" if answer else "empty"
    return "", "missing_advisory_section"


def _contains_any(answer: str, alternatives: list[str]) -> bool:
    folded = answer.casefold()
    return any(str(option).casefold() in folded for option in alternatives if option)


def evaluate(
    benchmark: dict[str, Any],
    gemma: dict[str, Any],
    claude: dict[str, Any],
) -> dict[str, Any]:
    """Produce review signals only; NOT a correctness or Claude-equivalence score."""
    cases = benchmark.get("cases") or []
    report: dict[str, Any] = {
        "method": "lexical_indicators_plus_required_manual_review",
        "warning": (
            "Matching phrases is not proof of reasoning or factual accuracy. "
            "Potential overclaims may be quoted or negated. Manually judge "
            "causal interpretation, priorities, evidence and usefulness."
        ),
        "cases": [],
    }
    for case in cases:
        case_id = str(case["id"])
        checks = case.get("checks") or []
        one_case: dict[str, Any] = {
            "id": case_id,
            "title": case.get("title", case_id),
            "results": {},
        }
        for model_name, submissions in (("gemma", gemma), ("claude", claude)):
            answer, status = extract_answer(submissions.get(case_id))
            covered = [
                str(c["name"]) for c in checks
                if _contains_any(answer, c.get("indicators") or [])
            ] if status == "available" else []
            missing = [
                str(c["name"]) for c in checks if str(c["name"]) not in covered
            ]
            red_flags = [
                term for term in case.get("potential_overclaims") or []
                if _contains_any(answer, [str(term)])
            ] if status == "available" else []
            one_case["results"][model_name] = {
                "status": status,
                "indicator_coverage": f"{len(covered)}/{len(checks)}",
                "covered": covered,
                "missing": missing,
                "potential_overclaims_for_manual_review": red_flags,
                "answer_characters": len(answer),
            }
        report["cases"].append(one_case)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--gemma", required=True, type=Path)
    parser.add_argument("--claude", required=True, type=Path)
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    gemma = json.loads(args.gemma.read_text(encoding="utf-8"))
    claude = json.loads(args.claude.read_text(encoding="utf-8"))
    if not isinstance(gemma, dict) or not isinstance(claude, dict):
        parser.error("Model submissions must be JSON objects keyed by case ID.")
    print(json.dumps(evaluate(benchmark, gemma, claude), indent=2))


if __name__ == "__main__":
    main()

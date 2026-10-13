"""Typed evidence reconciliation for reported decisions versus verified effects.

A log *statement* can be a direct observation of what the app reported; it
is not, by itself, proof that the stated action was applied to a later input.
This module turns already-filtered model-only excerpts into privacy-preserving
quantity/source/clock facts, so one synthesis contract can compare user goals,
runtime assertions and independently observed effects without hard-coded
device/app IDs or prescriptive answer wording.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
import re

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}
_DURATION = re.compile(
    r"\b(?P<value>\d{1,7}|one|two|three|four|five|six|seven|"
    r"eight|nine|ten|eleven|twelve)[\s-]*"
    r"(?P<unit>milliseconds?|millis?|ms|seconds?|secs?|sec|s|"
    r"minutes?|mins?|min|hours?|hrs?|hr|h)\b", re.I,
)
_FACTOR = {
    "millisecond": 0.001, "milliseconds": 0.001, "milli": 0.001,
    "millis": 0.001, "ms": 0.001,
    "second": 1, "seconds": 1, "sec": 1, "secs": 1, "s": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "h": 3600,
}
# Find *candidate* decision assertions. Wording only selects excerpts to
# examine, and never upgrades the authority or outcome of a source.
_DECLARATION = re.compile(
    r"\b(?:block(?:ed|ing)?|inhibit(?:ed|ing)?|suppress(?:ed|ing)?|"
    r"prevent(?:ed|ing)?|lockout|lock-out|engag(?:ed|ing)|enabled?)\b", re.I
)


def quantities(text: str, *, max_count: int = 4) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        return []
    values = []
    for match in _DURATION.finditer(text):
        raw = match.group("value").lower()
        number = int(raw) if raw.isdigit() else _WORD_NUMBERS.get(raw)
        factor = _FACTOR.get(match.group("unit").lower())
        if number is None or factor is None:
            continue
        values.append({
            "value": number, "unit": match.group("unit"),
            "seconds": round(number * factor, 3),
        })
        if len(values) == max_count:
            break
    return values


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return stamp if stamp.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def reconcile_decision_claims(
    user_prompt: str, rows: list[dict[str, Any]], *,
    focal_off: datetime | None,
    declared_effect_verified: bool = False,
) -> dict[str, Any]:
    """Classify grounded *claims*, not infer successful execution.

    Output contains no text excerpts, private messages, or string-matched
    sensitive entities. Return a numeric discrepancy only when user question
    and a log excerpt each contain a concrete quantity and comparable unit.
    """
    expected = quantities(user_prompt)
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        statement = str(row.get("message") or "")
        if not _DECLARATION.search(statement):
            continue
        time = _aware(row.get("timestamp"))
        delay = (
            round((time - focal_off).total_seconds() * 1000, 3)
            if time is not None and focal_off is not None
            else None
        )
        selected.append({
            "sourceRowId": row.get("sourceRowId"),
            "sourceIdentity": row.get("scopeBasis", "unverified"),
            "timestampOffsetVerified": time is not None,
            "timeFromFocalMs": delay,
            "temporalAssociationOnly": delay is not None,
            "reportedDurations": quantities(statement),
            "evidenceLevel": "textual-declaration-only",
            "effectiveActionProvenByThisRow": False,
        })
    # Do not select one arbitrarily if the user or log contains multiple
    # independent time quantities. Preserve those values for comparison.
    pairs = []
    for source in selected:
        for duration in source["reportedDurations"]:
            for wanted in expected:
                delta = round(duration["seconds"] - wanted["seconds"], 3)
                pairs.append({
                    "sourceRowId": source["sourceRowId"],
                    "requestedSeconds": wanted["seconds"],
                    "reportedSeconds": duration["seconds"],
                    "differenceSeconds": delta,
                    "matches": abs(delta) < 0.0005,
                })
    conflict = (
        True if any(not item["matches"] for item in pairs)
        else False if pairs else None
    )
    return {
        "schema": "decision-evidence-v1",
        "expectedDurations": expected[:4],
        "logDeclarationCandidates": selected[:12],
        "durationComparisons": pairs[:12],
        "durationMismatchObserved": conflict,
        "decisionStage": {
            "textualDecisionReported": bool(selected),
            "textualReportSourceIndependentlyVerified": bool(selected) and all(
                x["sourceIdentity"] == "explicit-app-id"
                for x in selected
            ),
            "configuredDurationVerified": False,
            "effectivelyPreventedActionVerified": bool(declared_effect_verified),
            "textualStatementDoesNotProveEffect": True,
        },
        "assertionBoundary": (
            "A timestamped log statement is evidence of what the log reports, "
            "not proof that a later eligible activation was prevented. "
            "Backend-app-filter-only rows are not independently source-identified; "
            "quantitative disagreements must be reported, not silently repaired."
        ),
        "containsPrivateLogContent": False,
    }


__all__ = ["quantities", "reconcile_decision_claims"]

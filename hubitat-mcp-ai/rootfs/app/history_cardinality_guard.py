"""Guard final prose against interval-count contradictions."""

from __future__ import annotations

import re
from typing import Any

_COUNT_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}
_COUNT = r"(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_CARDINALITY = re.compile(
    rf"\b(?P<count>{_COUNT})\s+(?:separate\s+|observed\s+|bounded\s+)*"
    r"(?P<noun>periods?|intervals?|times)\b",
    re.I,
)
_NONEXHAUSTIVE = re.compile(
    r"\b(?:longest|main|notable|examples?|including|such\s+as|among|at\s+least)\b",
    re.I,
)


def _to_int(raw: str) -> int | None:
    value = str(raw or "").casefold()
    if value.isdigit():
        return int(value)
    return _COUNT_WORDS.get(value)


def _replacement(receipt: dict[str, Any]) -> str | None:
    details = receipt.get("details")
    if not isinstance(details, dict):
        return None
    temporal = details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return None
    try:
        count = int(temporal.get("intervalCount"))
    except (TypeError, ValueError):
        return None
    label = str(details.get("label") or "The device").strip() or "The device"
    active = str(temporal.get("activeState") or "active").strip() or "active"
    window = str(temporal.get("windowLabel") or "").strip()
    suffix = f" during {window}" if window else ""
    noun = "interval" if count == 1 else "intervals"
    text = (
        f"The recorded rows contain {count} observed bounded {active} {noun} "
        f"for {label}{suffix}."
    )
    if temporal.get("sourceIntegrityVerified") is False:
        text += (
            " The device-event stream is not independently verified as complete, "
            "so this is the observed interval count rather than proof of the full "
            "real-world history."
        )
    return text


def guard_history_interval_cardinality(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Correct exhaustive interval counts that contradict deterministic proof.

    A phrase such as "the two longest periods" is intentionally allowed because
    it is a subset, not an exhaustive cardinality claim.
    """

    text = str(message or "")
    receipts = [
        receipt for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
        and isinstance(receipt.get("details"), dict)
        and isinstance(receipt["details"].get("temporalAnalysis"), dict)
    ]
    if not receipts or not _CARDINALITY.search(text):
        return text, []

    pieces = re.split(r"(?<=[.!?])(?P<space>\s+)", text)
    changed: list[dict[str, Any]] = []
    for idx in range(0, len(pieces), 2):
        sentence = pieces[idx]
        match = _CARDINALITY.search(sentence)
        if match is None or _NONEXHAUSTIVE.search(sentence):
            continue
        claimed = _to_int(match.group("count"))
        if claimed is None:
            continue
        comparable = re.sub(r"[*_\x60]", "", sentence).casefold()
        candidates = []
        for receipt in receipts:
            details = receipt["details"]
            label = str(details.get("label") or "").strip()
            temporal = details["temporalAnalysis"]
            try:
                expected = int(temporal.get("intervalCount"))
            except (TypeError, ValueError):
                continue
            if expected == claimed:
                continue
            if label and label.casefold() in comparable:
                candidates.append(receipt)
        if not candidates and len(receipts) == 1:
            temporal = receipts[0]["details"]["temporalAnalysis"]
            try:
                expected = int(temporal.get("intervalCount"))
            except (TypeError, ValueError):
                expected = claimed
            if expected != claimed:
                candidates = [receipts[0]]
        if len(candidates) != 1:
            continue
        replacement = _replacement(candidates[0])
        if replacement is None:
            continue
        pieces[idx] = replacement
        changed.append(candidates[0])

    return "".join(pieces), changed


__all__ = ["guard_history_interval_cardinality"]

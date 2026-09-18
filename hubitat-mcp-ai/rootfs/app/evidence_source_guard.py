"""Final-response guard for contradictions about checked evidence sources.

This guard does not judge whether an evidence source proves the user's theory.  It
only prevents a narrower contradiction: saying a source was not provided/checked
when successful current-turn receipts prove that it was.
"""

from __future__ import annotations

import re
from typing import Any

from evidence_ledger import checked_source_categories


_SOURCE_WAS_MISSING = re.compile(
    r"(?:\bno\b[^.!?]{0,90}\b(?:data|evidence|history|logs?|rules?)\b"
    r"[^.!?]{0,60}\b(?:was|were)\s+(?:provided|supplied|checked|queried|read)\b)"
    r"|(?:\b(?:did\s+not|didn't|was\s+not|wasn't|were\s+not|weren't)\s+"
    r"(?:check|query|read|receive)\b)",
    re.I,
)

_SOURCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "related_device_history": re.compile(
        r"\b(?:sensor|related[- ]device|device\s+history|related\s+history)\b",
        re.I,
    ),
    "location_history": re.compile(
        r"\b(?:location|mode|hub\s+mode)\b",
        re.I,
    ),
    "logs": re.compile(r"\blogs?\b", re.I),
    "rules_apps": re.compile(r"\b(?:rules?|apps?|automation)\b", re.I),
    "device_history": re.compile(r"\b(?:device|event)\s+history\b", re.I),
}

_SOURCE_LABELS = {
    "related_device_history": "related-device/sensor history",
    "location_history": "location/mode history",
    "logs": "native/log evidence",
    "rules_apps": "rule/app evidence",
    "device_history": "device history",
}


def _sentence_pieces(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])(?P<space>\s+)", str(text or ""))


def guard_checked_source_absence_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Replace only claims that a successfully checked source was not supplied."""

    text = str(message or "")
    categories = checked_source_categories(evidence)
    if not categories or not _SOURCE_WAS_MISSING.search(text):
        return text, False

    pieces = _sentence_pieces(text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _SOURCE_WAS_MISSING.search(sentence):
            continue
        contradicted = [
            category
            for category, pattern in _SOURCE_PATTERNS.items()
            if category in categories and pattern.search(sentence)
        ]
        if not contradicted:
            continue
        labels = [_SOURCE_LABELS[category] for category in contradicted]
        if len(labels) == 1:
            checked = labels[0]
        else:
            checked = ", ".join(labels[:-1]) + f" and {labels[-1]}"
        pieces[index] = (
            f"Current-turn evidence did include checked {checked}; "
            "those sources did not by themselves establish a specific cause."
        )
        changed = True
    return "".join(pieces), changed


__all__ = ["guard_checked_source_absence_claim"]

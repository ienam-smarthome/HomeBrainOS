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


_POSITIVE_LOG_ATTRIBUTION = re.compile(
    r"\b(?P<article>the\s+)?logs?\s+"
    r"(?P<verb>show(?:s|ed)?|indicat(?:e|es|ed)|record(?:s|ed)?|contain(?:s|ed)?)\b",
    re.I,
)


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


def guard_positive_source_attribution(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Correct positive claims that name a source not checked this turn.

    This is intentionally narrow: a device-event history may contain rows whose
    descriptions look log-like, but that does not make native Hubitat logs a
    checked source. Preserve the factual claim while correcting only the source
    label when current-turn device history exists.
    """

    text = str(message or "")
    categories = checked_source_categories(evidence)
    if "logs" in categories or not _POSITIVE_LOG_ATTRIBUTION.search(text):
        return text, False
    if not ({"device_history", "raw_device_history"} & categories):
        return text, False

    def _replacement(match: re.Match[str]) -> str:
        article = "the " if match.group("article") else ""
        verb = match.group("verb")
        return f"{article}recorded device-event rows {verb}"

    corrected, count = _POSITIVE_LOG_ATTRIBUTION.subn(_replacement, text)
    return corrected, count > 0


__all__ = [
    "guard_checked_source_absence_claim",
    "guard_positive_source_attribution",
]

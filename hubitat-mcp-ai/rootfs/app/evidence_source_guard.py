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

_PERFORMANCE_SOURCE_TERM = (
    r"(?:metrics?|performance\\s+(?:statistics?|stats?)|logs?|log\\s+entries|necessary\\s+data)"
)
_PERFORMANCE_SOURCE_ABSENCE = re.compile(
    rf"(?i)(?:"
    rf"\\b(?:current-turn\\s+)?evidence\\b[^.!?]{{0,80}}\\b(?:does|do|did)\\s+not\\s+"
    rf"(?:provide|include|contain|return|supply)\\b[^.!?]{{0,100}}\\b{_PERFORMANCE_SOURCE_TERM}\\b"
    rf"|\\bno\\b[^.!?]{{0,160}}\\b{_PERFORMANCE_SOURCE_TERM}\\b[^.!?]{{0,100}}"
    rf"\\b(?:was|were|is|are)?\\s*(?:returned|provided|supplied|available|retrieved|received|included|present)\\b"
    rf"|\\b{_PERFORMANCE_SOURCE_TERM}\\b[^.!?]{{0,120}}\\b(?:was|were|is|are|did)\\s+not\\s+"
    rf"(?:returned|provided|supplied|available|retrieved|received|included|present|checked|read|queried)\\b"
    rf")"
)

_SUBSTANTIVE_PERFORMANCE_CONTENT = re.compile(
    r"(?i)(?:\\b\\d[\\d,.]*\\s*(?:%|ms|mb|kb|°c)\\b|\\bcall count\\b|"
    r"\\bresource consumers?\\b|\\bperformance analysis\\b|"
    r"\\blogs?\\s+(?:show|shows|showed|indicate|indicates|indicated|record|records|recorded|contain|contains|contained)\\b|"
    r"\\breporting\\b[^.!?\\n]{0,80}\\bevery\\s+\\d+)"
)

_POSITIVE_LOG_ATTRIBUTION = re.compile(
    r"\b(?P<article>the\s+)?logs?\s+"
    r"(?P<verb>show(?:s|ed)?|indicat(?:e|es|ed)|record(?:s|ed)?|contain(?:s|ed)?)\b",
    re.I,
)


def _sentence_pieces(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])(?P<space>\s+)", str(text or ""))


def _successful_performance_sources(evidence: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        tool = str(receipt.get("tool") or "")
        sub_tool = str(receipt.get("sub_tool") or "")
        leaf = sub_tool or tool
        if leaf == "hub_get_metrics" and "hub metrics" not in found:
            found.append("hub metrics")
        elif leaf == "hub_get_performance_stats" and "performance statistics" not in found:
            found.append("performance statistics")
        elif leaf == "hub_get_logs" and "logs" not in found:
            found.append("logs")
    return found


def _guard_performance_source_absence(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Correct false claims that successful metrics/performance/log reads were absent.

    In a substantive performance answer, remove only the contradicted refusal sentence.
    Do not splice serializer repair prose into a valid device/log observation.  For a
    pure source-absence refusal, retain one compact deterministic correction so the
    final response cannot falsely claim that successful current-turn reads were missing.
    """

    sources = _successful_performance_sources(evidence)
    text = str(message or "")
    if not sources or not _PERFORMANCE_SOURCE_ABSENCE.search(text):
        return text, False

    pieces = _sentence_pieces(text)
    substantive = bool(
        _SUBSTANTIVE_PERFORMANCE_CONTENT.search(
            _PERFORMANCE_SOURCE_ABSENCE.sub("", text)
        )
    )
    changed = False
    rendered_correction = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _PERFORMANCE_SOURCE_ABSENCE.search(sentence):
            continue
        comparable = sentence.casefold()
        relevant = False
        if "hub metrics" in sources and ("metric" in comparable or "necessary data" in comparable):
            relevant = True
        if "performance statistics" in sources and ("performance" in comparable or "necessary data" in comparable):
            relevant = True
        if "logs" in sources and ("log" in comparable or "necessary data" in comparable):
            relevant = True
        if not relevant:
            continue

        if substantive:
            pieces[index] = ""
        elif not rendered_correction:
            rendered = sources[0] if len(sources) == 1 else ", ".join(sources[:-1]) + f" and {sources[-1]}"
            pieces[index] = (
                f"Current-turn evidence did include successful {rendered}; "
                "those results should be used for the requested performance analysis."
            )
            rendered_correction = True
        else:
            pieces[index] = ""
        changed = True

    corrected = "".join(pieces)
    if substantive and changed:
        corrected = re.sub(r"[ \t]+\n", "\n", corrected)
        corrected = re.sub(r"\n{3,}", "\n\n", corrected)
        corrected = corrected.rstrip()
    return corrected, changed


def guard_checked_source_absence_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Replace only claims that a successfully checked source was not supplied."""

    text = str(message or "")
    text, performance_changed = _guard_performance_source_absence(text, evidence)
    categories = checked_source_categories(evidence)
    if not categories or not _SOURCE_WAS_MISSING.search(text):
        return text, performance_changed

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
    return "".join(pieces), changed or performance_changed


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

"""Final-answer guard for contradictions with tight location-event correlations."""

from __future__ import annotations

import re
from typing import Any

from location_correlation import nearest_location_correlations, render_location_correlation


_NO_LOCATION_CORRELATION = re.compile(
    r"\b(?:location|mode|hub\s+mode)[^.!?]{0,120}"
    r"\b(?:does\s+not|doesn't|did\s+not|didn't|no)\b[^.!?]{0,100}"
    r"\b(?:correlat|near|close|adjacent|coincid)",
    re.I,
)


def _sentence_pieces(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])(?P<space>\s+)", str(text or ""))


def guard_location_correlation_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Correct only a categorical no-correlation claim contradicted by evidence."""

    text = str(message or "")
    if not _NO_LOCATION_CORRELATION.search(text):
        return text, False

    matches = nearest_location_correlations(
        evidence,
        max_delta_seconds=15.0,
        limit=1,
    )
    if not matches:
        return text, False

    statement = (
        "Current-turn location/mode history does contain a close temporal "
        f"correlation: {render_location_correlation(matches[0])}. "
        "This timing correlation does not by itself establish causation."
    )
    pieces = _sentence_pieces(text)
    changed = False
    for index in range(0, len(pieces), 2):
        if _NO_LOCATION_CORRELATION.search(pieces[index]):
            pieces[index] = statement
            changed = True
    return "".join(pieces), changed


__all__ = ["guard_location_correlation_claim"]

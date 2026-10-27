"""Conservative question contract for independently verified, single-device reads.

This is NOT general natural-language intent routing. Only complete, unambiguous
factual question templates are eligible. Anything requiring explanation,
comparison, inference or mixed objectives retains the model investigation path.
A full live-inventory device identity must already have been verified.
"""
from __future__ import annotations

import re
from typing import Iterable


_STATUS_TEMPLATES = frozenset({
    "is {device} on", "is {device} off",
    "is {device} currently on", "is {device} currently off",
    "is {device} on or off", "is {device} currently on or off",
    "is {device} off or on", "is {device} currently off or on",
    "what is {device}'s current status", "what is {device}'s current state",
    "what's {device}'s current status", "what's {device}'s current state",
    "what is the current status of {device}",
    "what is the current state of {device}",
})
_HISTORY_TEMPLATES = frozenset({
    "when did {device} last turn on",
    "when did {device} last turn off",
    "when did {device} last turn on and off",
    "when did {device} last turn off and on",
    "when did {device} last turn on or off",
    "when was {device} last turned on",
    "when was {device} last turned off",
    "what were {device}'s most recent on and off reports",
    "what were {device}'s most recent on/off reports",
})


def verified_factual_objective(question: str, labels: Iterable[str]) -> str | None:
    """Return status/history only when the ENTIRE question fits a safe template.

    No verbs are scanned to route a causal question. Unknown wording stays
    unclassified, not silently converted to status or history.
    """
    names = list(labels)
    if len(names) != 1 or not isinstance(names[0], str):
        return None
    if not isinstance(question, str) or not 1 <= len(question) <= 400:
        return None
    label = re.sub(r"\s+", " ", names[0].strip()).casefold()
    if not label:
        return None
    normalized = re.sub(r"\s+", " ", question.strip().rstrip("?!." )).casefold()
    # Match exactly one whole verified label, not an incidental shorter prefix.
    found = list(re.finditer(r"(?<!\w)" + re.escape(label) + r"(?!\w)", normalized))
    if len(found) != 1:
        return None
    hit = found[0]
    template = normalized[:hit.start()] + "{device}" + normalized[hit.end():]
    if template in _STATUS_TEMPLATES:
        return "status"
    if template in _HISTORY_TEMPLATES:
        return "history"
    return None


__all__ = ["verified_factual_objective"]

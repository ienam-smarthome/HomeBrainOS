"""Shared classification for analytical and causal history requests."""

from __future__ import annotations

import re

CAUSAL_INVESTIGATION = re.compile(
    r"\bwhy\b|"
    r"\b(?:cause|caused|causing|trigger|triggered|reason)\b|"
    r"\bwhat\s+(?:caused|triggered|made)\b",
    re.I,
)

HISTORY_INVESTIGATION = re.compile(
    CAUSAL_INVESTIGATION.pattern
    + r"|\b(?:normal|normally|abnormal|unusual|expected|unexpected)\b"
    + r"|\b(?:compare|comparison|versus|vs\.?|correlat(?:e|ed|ion))\b",
    re.I,
)


def is_causal_investigation(prompt: str) -> bool:
    return CAUSAL_INVESTIGATION.search(str(prompt or "")) is not None


def is_history_investigation(prompt: str) -> bool:
    return HISTORY_INVESTIGATION.search(str(prompt or "")) is not None


__all__ = [
    "CAUSAL_INVESTIGATION",
    "HISTORY_INVESTIGATION",
    "is_causal_investigation",
    "is_history_investigation",
]

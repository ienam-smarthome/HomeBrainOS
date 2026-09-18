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

EXPLICIT_PROVENANCE_SOURCE = re.compile(
    r"\b(?:app|apps|automation|automations|rule|rules|log|logs)\b",
    re.I,
)


def is_causal_investigation(prompt: str) -> bool:
    return CAUSAL_INVESTIGATION.search(str(prompt or "")) is not None


def is_history_investigation(prompt: str) -> bool:
    return HISTORY_INVESTIGATION.search(str(prompt or "")) is not None


def uses_known_history_evidence_path(prompt: str) -> bool:
    """Whether generic history reasoning can start from the fixed local registry.

    Device history, target resolution, room filtering, location history, and the
    later bounded causal-provenance registry are already known to HomeBrain.
    Fuzzy discovery is only useful up front when the user explicitly asks for a
    provenance source class such as logs, rules, apps, or automation.
    """

    text = str(prompt or "")
    return (
        is_history_investigation(text)
        and EXPLICIT_PROVENANCE_SOURCE.search(text) is None
    )


__all__ = [
    "CAUSAL_INVESTIGATION",
    "HISTORY_INVESTIGATION",
    "EXPLICIT_PROVENANCE_SOURCE",
    "is_causal_investigation",
    "is_history_investigation",
    "uses_known_history_evidence_path",
]

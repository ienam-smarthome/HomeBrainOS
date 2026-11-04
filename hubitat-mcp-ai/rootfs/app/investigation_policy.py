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

# Comparison is NOT by itself a historical objective. Current-state/
# brightness comparisons were unnecessarily sent through the history
# investigation loop, causing unrequested event reads, additional model
# rounds and a false "missing history" coverage flag.
_SNAPSHOT_COMPARISON = re.compile(
    r"\b(?:compare|contrast)\b[^.!?\n]{0,180}"
    r"\b(?:(?:current|present|reported|switch)\s+){0,3}"
    r"(?:states?|statuses|status|brightness|levels?)\b",
    re.I,
)
_HISTORY_OR_CAUSE_CONTEXT = re.compile(
    r"\b(?:history|historical|historic|previous|earlier|yesterday|"
    r"past|before|after|recent(?:ly)?|events?|changes?|changed|"
    r"transitions?|patterns?|trends?|over time|during|last week|"
    r"last night|timeline|activity|activities|duration|on[- ]?off cycles?|"
    r"commands?|logs?|cause|caused|trigger|triggered|why|"
    r"normal|abnormal|unusual|expected|unexpected|correlat\w*)\b",
    re.I,
)


def is_snapshot_comparison(prompt: str) -> bool:
    """Read-only current-state comparison, without historical/cause claims.

    Generic objective classification only. Never supplies tool authority,
    device identity, or a claim that the returned attributes are fresh.
    """
    text = " ".join(str(prompt or "").split())
    return (
        _SNAPSHOT_COMPARISON.search(text) is not None
        and _HISTORY_OR_CAUSE_CONTEXT.search(text) is None
        and CAUSAL_INVESTIGATION.search(text) is None
    )


EXPLICIT_PROVENANCE_SOURCE = re.compile(
    r"\b(?:app|apps|automation|automations|rule|rules|log|logs)\b",
    re.I,
)


def is_causal_investigation(prompt: str) -> bool:
    return CAUSAL_INVESTIGATION.search(str(prompt or "")) is not None


def is_history_investigation(prompt: str) -> bool:
    # "Compare current states" requires two independent state receipts,
    # not two historical event histories. Preserve historical comparisons
    # whenever the user actually asks about events or causal context.
    return (
        not is_snapshot_comparison(prompt)
        and HISTORY_INVESTIGATION.search(str(prompt or "")) is not None
    )


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
    "is_snapshot_comparison",
    "uses_known_history_evidence_path",
]

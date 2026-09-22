"""Deterministic guard against configuration-only causal attribution."""

from __future__ import annotations

import re
from typing import Any

from causal_timeline import build_causal_timeline_rows


_APP_TERM = re.compile(r"\b(?:app|automation|rule|controller)\b", re.I)
_CAUSAL_CLAIM = re.compile(
    r"\b(?:most\s+likely\s+cause|likely\s+(?:cause|trigger)|"
    r"caus(?:e|ed|es)|trigger(?:ed|s)?|responsible\s+for|"
    r"turned\s+(?:it|the\s+device)\s+on)\b",
    re.I,
)
_DIRECT_PROVENANCE_TERM = re.compile(
    r"\b(?:physical\s+button|button\s+(?:press|push)|controller\s+event|"
    r"execution\s+log|native\s+log|command\s+source)\b",
    re.I,
)
_UNRESOLVED_CAVEAT = re.compile(
    r"\b(?:no\s+direct\s+(?:log\s+)?evidence|not\s+established|"
    r"could\s+not\s+confirm|couldn't\s+confirm|unexplained|"
    r"no\s+corresponding\s+(?:controller\s+events?|hub\s+logs?|logs?))\b",
    re.I,
)


def _has_app_configuration(evidence: list[dict[str, Any]]) -> bool:
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        sub_tool = str(receipt.get("sub_tool") or "").casefold()
        if sub_tool in {"hub_get_app_config", "hub_list_apps"}:
            return True
    return False


def _has_aligned_start_controller(evidence: list[dict[str, Any]]) -> bool:
    return any(
        row.get("triggerEvidence")
        for row in build_causal_timeline_rows(evidence)
        if row.get("material")
    )


def guard_configuration_only_causal_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Soften causal app claims that outrun current-turn provenance.

    Installed-app/config reads prove association and capability, not that the app
    initiated one observed transition. If a stronger aligned controller event is
    present, it must outrank configuration. If no direct provenance is present,
    a draft that both names an app as the likely cause and admits provenance is
    unestablished is internally inconsistent and must be softened.
    """

    text = str(message or "")
    if not _has_app_configuration(evidence):
        return text, False
    if not (_APP_TERM.search(text) and _CAUSAL_CLAIM.search(text)):
        return text, False

    has_controller = _has_aligned_start_controller(evidence)
    self_disclaims_proof = _UNRESOLVED_CAVEAT.search(text) is not None

    if not has_controller and not self_disclaims_proof:
        return text, False

    pieces = re.split(r"(?P<space>(?<=[.!?])\s+|\n+)", text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not (_APP_TERM.search(sentence) and _CAUSAL_CLAIM.search(sentence)):
            continue
        if _DIRECT_PROVENANCE_TERM.search(sentence):
            continue
        if has_controller:
            pieces[index] = (
                "The strongest current-turn start-boundary evidence is the aligned "
                "controller event; the checked app/rule configuration can explain "
                "downstream handling, but configuration alone does not establish "
                "that it initiated the turn-on."
            )
        else:
            pieces[index] = (
                "The checked app/rule configuration shows that the automation can "
                "manage this device, but current-turn execution/provenance evidence "
                "does not establish that it initiated this specific turn-on."
            )
        changed = True

    return "".join(pieces), changed


__all__ = ["guard_configuration_only_causal_claim"]

"""Correct universal controller-coverage claims against the observed graph.

This is not a Bedroom/light-name template. Coverage is derived from the
normalized evidence graph's distinct observed ON boundaries and aligned
controller starts. The guard only corrects unqualified universals about the
controller's association with the *whole* examined history, preserving bounded
phrases such as "all three recent button-aligned events".
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from causal_evidence_graph import build_causal_evidence_graph

_ALL_OBSERVED_ON = re.compile(
    r"\b(?:every|all)\s+"
    r"(?:(?:recorded|observed)\s+)?"
    r"(?:light[- ]on|turn[- ]on|ON)\s+"
    r"(?:intervals?|events?|transitions?)\b",
    re.I,
)
_CONTROLLER_CONTEXT = re.compile(
    r"\b(?:button|dimmer|controller|button[- ]press|pushed)\b", re.I
)


def guard_causal_controller_history_coverage(
    message: str,
    evidence: list[dict[str, Any]],
    original_user: str = "",
) -> tuple[str, bool]:
    if not original_user:
        # API serialization has no original user message. Recover the focal
        # event only from the host-verified requested boundary receipt, never
        # from arbitrary model prose that could mention many times.
        candidates = []
        for item in evidence:
            if (
                isinstance(item, dict)
                and item.get("success") is True
                and item.get("tool") == "homebrain_causal_secondary_correlation"
            ):
                details = item.get("details") or {}
                date_text = str(details.get("requestedBoundary") or "")
                subject = str(details.get("subject") or "")
                if date_text and subject:
                    try:
                        moment = datetime.fromisoformat(
                            date_text.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue
                    candidates.append(
                        f"Why did {subject} turn on at "
                        f"{moment:%H:%M:%S} on {moment.day} {moment:%B %Y}?"
                    )
        if len(set(candidates)) == 1:
            original_user = candidates[0]
    graph = build_causal_evidence_graph(evidence, original_user)
    coverage = graph.get("controllerCoverage") or {}
    observed = coverage.get("observedStartCount")
    aligned = coverage.get("alignedObservedStartCount")
    if (
        not isinstance(observed, int)
        or not isinstance(aligned, int)
        or not (0 < aligned < observed)
    ):
        return str(message or ""), False

    changed = False
    out = []
    for raw in str(message or "").splitlines(keepends=True):
        # Never transform a historical statement without an explicit
        # controller claim, or rewrite a correctly scoped "three recent" claim.
        if (
            _ALL_OBSERVED_ON.search(raw)
            and _CONTROLLER_CONTEXT.search(raw)
            and not re.search(r"\b(?:recent|last|latest)\b", raw, re.I)
        ):
            updated, count = _ALL_OBSERVED_ON.subn(
                f"{aligned} of {observed} observed ON intervals", raw
            )
            out.append(updated)
            changed = changed or bool(count)
        else:
            out.append(raw)
    return "".join(out), changed


__all__ = ["guard_causal_controller_history_coverage"]

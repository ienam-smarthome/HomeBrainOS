from __future__ import annotations

import re
from types import MethodType
from typing import Any


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "automation",
    "rule",
    "the",
}


def _tokens(value: Any) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    return {word for word in words if word not in _STOP_WORDS and len(word) > 1}


def ranked_rule_candidates(
    rules: list[dict[str, Any]],
    variants: tuple[str, ...],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return safe clarification candidates without treating aliases as exact writes.

    A shortened request such as ``fridge freezer rule`` should find
    ``Appliance: Fridge and Freezer - Auto ON``. The result remains a clarification
    candidate, so the user must still confirm the exact Rule ID before any write.
    """

    requested_sets = [_tokens(variant) for variant in variants]
    requested_sets = [tokens for tokens in requested_sets if tokens]
    if not requested_sets:
        return []

    ranked: list[tuple[float, int, str, dict[str, Any]]] = []
    for rule in rules:
        rule_tokens = _tokens(rule.get("normalised") or rule.get("name"))
        if not rule_tokens:
            continue

        best_score = 0.0
        best_overlap = 0
        for requested in requested_sets:
            overlap = len(requested & rule_tokens)
            if not overlap:
                continue
            coverage = overlap / len(requested)
            precision = overlap / len(rule_tokens)
            score = coverage * 0.8 + precision * 0.2
            if requested <= rule_tokens:
                score += 0.25
            if score > best_score:
                best_score = score
                best_overlap = overlap

        # Require at least two meaningful shared terms, or complete coverage of a
        # one-token request. This prevents broad words such as "power" or "light"
        # from producing unsafe confirmation candidates.
        minimum_overlap = 1 if min(len(item) for item in requested_sets) == 1 else 2
        if best_overlap < minimum_overlap or best_score < 0.65:
            continue
        ranked.append(
            (
                -best_score,
                len(rule_tokens),
                str(rule.get("name") or "").lower(),
                rule,
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in ranked[: max(1, int(limit))]]


def install_named_rule_match_guard(controller: Any) -> Any:
    """Improve candidate discovery while preserving exact-ID confirmation safety."""

    def possible_matches(
        self: Any,
        rules: list[dict[str, Any]],
        intent: Any,
    ) -> list[dict[str, Any]]:
        return ranked_rule_candidates(rules, tuple(intent.variants), limit=5)

    controller._possible_matches = MethodType(possible_matches, controller)
    return controller


__all__ = [
    "install_named_rule_match_guard",
    "ranked_rule_candidates",
]

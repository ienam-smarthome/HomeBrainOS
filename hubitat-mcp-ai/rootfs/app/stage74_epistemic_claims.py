"""Stage 7.4 experimental epistemic position/scope annotation.

The *model* declares its intended position on a factual topic. Validation
checks schema, internal scope safety and host source structure, NOT whether
the natural-language sentence actually matches the position. That requires
an independent reviewer; no model self-certification, keyword-based prose
classification, live hub access or production publisher changes.
"""
from __future__ import annotations

from typing import Any

_POSITIONS = frozenset({"affirmed", "refuted", "not_established"})
_SCOPES = frozenset({"examined_records", "supplied_records", "universal"})
_HIGH_RISK_TOPICS = frozenset({
    "unique_cause", "physical_confirmation", "absence_proven",
})


def validate_epistemic_declaration(declaration: Any) -> dict[str, str]:
    """Validate model-declared semantic *intent*, not the sentence's semantics."""
    if (type(declaration) is not dict
            or set(declaration) != {"position", "scope"}
            or type(declaration["position"]) is not str
            or declaration["position"] not in _POSITIONS
            or type(declaration["scope"]) is not str
            or declaration["scope"] not in _SCOPES):
        raise ValueError("invalid epistemic declaration")
    return declaration


def assess_epistemic_claim(kind: str, declaration: dict[str, str]) -> dict[str, Any]:
    """Conservatively separate high-risk assertions from scoped uncertainty.

    An unresolved proposition is not the same as a claim that the proposition
    is FALSE. No declaration can prove physical effects or global negatives.
    """
    position, scope = declaration["position"], declaration["scope"]
    high_risk = kind in _HIGH_RISK_TOPICS
    if high_risk and position == "not_established" and scope != "universal":
        category = "scoped_unresolved_model_declaration"
        asserted_or_refuted_risk = False
    elif high_risk and position == "not_established":
        category = "unscoped_unresolved_model_declaration"
        asserted_or_refuted_risk = False
    elif high_risk:
        category = ("affirmative_high_risk_claim" if position == "affirmed"
                    else "categorical_refutation_high_risk")
        asserted_or_refuted_risk = True
    elif position == "not_established":
        category = ("scoped_unresolved_model_declaration" if scope != "universal"
                    else "unscoped_unresolved_model_declaration")
        asserted_or_refuted_risk = False
    elif position == "refuted":
        category = "model_declared_refutation_not_independently_proven"
        asserted_or_refuted_risk = False
    else:
        category = "ordinary_affirmative_model_declaration"
        asserted_or_refuted_risk = False

    return {
        "subject_kind": kind,
        "model_declared_position": position,
        "model_declared_scope": scope,
        "epistemic_category": category,
        "high_risk_assertion_or_refutation": asserted_or_refuted_risk,
        "natural_language_matches_declaration_verified": False,
        "universal_absence_proven": False,
        "unique_physical_causation_proven": False,
        "independent_human_semantic_review_required": True,
        "publication_approval": False,
    }


__all__ = ["validate_epistemic_declaration", "assess_epistemic_claim"]

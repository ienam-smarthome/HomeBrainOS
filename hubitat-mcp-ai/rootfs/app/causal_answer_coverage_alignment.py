"""Align published causal confidence with the independent coverage verdict.

The final model writes natural prose; a separate evidence audit subsequently
checks source classes and proposed hypotheses. Those two publications must
not contradict each other. This is a generic final-boundary consistency rule,
not a device, sensor or automation-specific response template.
"""
from __future__ import annotations

import re
from typing import Any


_CONFIDENCE = re.compile(
    r"^(\s*(?:[-*+]\s*)?)(?:\*\*)?Confidence\s*:(?:\*\*)?"
    r"\s*(?:\*\*)?\s*(?:very\s+)?(?:high|certain|confirmed|definitive)\b",
    re.I,
)
_LEAD = re.compile(
    r"^(\s*(?:[-*+]\s*)?)(?:\*\*)?Leading Explanation\s*:(?:\*\*)?\s*",
    re.I,
)
_COMPLETE = re.compile(
    r"\b(?:investigation|root[ -]cause investigation)\b"
    r".{0,100}?\b(?:is|was)\s+complete\b",
    re.I,
)
def unresolved_causal_hypotheses(coverage: Any) -> bool:
    """A checked source class alone is never a verified causal discriminator."""
    if not isinstance(coverage, dict):
        return False
    if coverage.get("rootCauseVerified") is True:
        return False
    if coverage.get("hypothesisComparisonStatus") != (
        "model-proposed-source-checks-not-causal-verdicts"
    ):
        return False
    comparisons = coverage.get("hypothesisComparisons")
    return bool(
        isinstance(comparisons, list)
        and comparisons
        and all(
            isinstance(row, dict)
            and row.get("discriminator_verified") is not True
            and row.get("hypothesis_verdict") != "verified"
            for row in comparisons
        )
    )


def align_causal_answer_with_coverage(
    message: str, coverage: Any,
) -> tuple[str, bool]:
    """Downgrade unsupported *cause certainty* without discarding known facts.

    Source reads may verify the issuing app, code and event times independently.
    They cannot make a model-proposed trigger proven while every proposed
    discriminator is explicitly unverified. Only contradictory confidence
    and completed-cause language is softened; details remain model-authored.
    """
    draft = str(message or "")
    if not unresolved_causal_hypotheses(coverage) or not draft.strip():
        return draft, False

    changed = False
    result = []
    for line in draft.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        end = line[len(bare):]
        if _CONFIDENCE.match(bare):
            indent = _CONFIDENCE.match(bare).group(1)
            result.append(
                indent + "**Root-cause confidence:** Unverified — recorded "
                "command provenance and configured logic do not verify the "
                "historical trigger." + end
            )
            changed = True
            continue
        if _LEAD.match(bare):
            rest = _LEAD.sub("", bare, count=1).lstrip()
            rest = re.sub(
                r"\bwas\s+(?:issued|triggered|caused)\s+by\b",
                "could have arisen from",
                rest, flags=re.I,
            )
            result.append(
                _LEAD.match(bare).group(1)
                + "**Leading hypothesis (unverified):** " + rest + end
            )
            changed = True
            continue
        if _COMPLETE.search(bare):
            bare = _COMPLETE.sub(
                "source investigation has finished, but its causal "
                "conclusion remains unverified",
                bare,
            )
            changed = True
        result.append(bare + end)

    calibrated = "".join(result)
    if changed:
        # State what was actually verified and which critical proof is absent,
        # without replacing the model's useful evidence-first analysis.
        calibrated = (
            "**Causal verification status: Unverified.** Source reads may "
            "identify a command issuer and show the configured implementation, "
            "but the proposed historical triggering decision has not been "
            "verified by a discriminating source.\n\n" + calibrated
        )
    return calibrated, changed


__all__ = ["unresolved_causal_hypotheses", "align_causal_answer_with_coverage"]

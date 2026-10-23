"""General question-first answer-quality contract for evidence-backed investigations.

This module does not infer facts, certify evidence, authorize MCP calls, or
filter causal claims. It identifies response-quality omissions after the
existing fact validator has approved the draft, and allows exactly one
NO-TOOLS model rewrite with a narrow, reusable instruction.

The requirements are question-type agnostic: compare options when asked,
answer a possibility question explicitly, and report verified facts even when
the overall investigation is incomplete. No app/device IDs are hard-coded.
"""
from __future__ import annotations

import re
from typing import Any


_MAX_QUESTION = 12000
_MAX_DRAFT = 30000
_RELATIONAL_REQUEST = re.compile(
    r"(?i)\b(?:compar(?:e|ison)|versus|vs\.?|differen(?:ce|t)|"
    r"overlap|interfer(?:e|ence)|conflict|competing|"
    r"before|after|instead of|between)\b"
)
_POSSIBILITY_REQUEST = re.compile(
    r"(?i)\b(?:could|can|whether|possible|would|will|likely|"
    r"what happens if|is there a risk)\b"
)
_EXPLANATORY_REQUEST = re.compile(
    r"(?i)\b(?:why|how|explain|analyse|analyze|cause|reason|"
    r"recommend|which is|what should|what does this mean)\b"
)
_RELATIONAL_ANSWER = re.compile(
    r"(?i)\b(?:whereas|while|compared|versus|vs\.?|relative|"
    r"differ|both|same|earlier|later|before|after|"
    r"overlap|compete|interfere|conflict|in contrast|than|"
    r"between)\b"
)
_POSSIBILITY_ANSWER = re.compile(
    r"(?i)\b(?:yes|can|cannot|could|couldn't|may|might|"
    r"possible|impossible|plausible|unlikely|likely|"
    r"unknown|not established|not enough evidence|"
    r"cannot determine|unverified|not verified|"
    r"not independently verified)\b|^\s*no\s*[,.!:]"
)
_INTERPRETATION_ANSWER = re.compile(
    r"(?i)\b(?:because|suggests?|indicates?|consistent with|"
    r"implies?|therefore|so that|means? that|"
    r"reason|explanation|cannot determine|not established|"
    r"insufficient evidence|uncertain|not verified|"
    r"unverified|possible|unlikely|likely)\b"
)
_NO_FACTS = re.compile(
    r"(?i)\b(?:could not retrieve any evidence|"
    r"no verified information|no live evidence|"
    r"no relevant data was returned)\b"
)


QUESTION_FIRST_CONTRACT = (
    "HOST QUESTION-FIRST ANALYST CONTRACT (NO TOOLS). "
    "Do not replace a useful response with a generic verification checklist. "
    "First answer the user's real question in plain language, using the strongest "
    "supported conclusion and the scope of the available observations. A "
    "partially completed investigation is not automatically a completely "
    "unanswerable question. Distinguish (1) facts directly verified by current-turn "
    "tool evidence, (2) logical interpretation or a conditional possibility, "
    "and (3) unknown behaviour that needs additional evidence. If the question "
    "compares multiple systems or hypotheses, explicitly explain the relevant "
    "relationship rather than reciting two separate inventories. Consider a "
    "plausible competing explanation where evidence permits one, and say how "
    "to distinguish it; do not invent alternatives or absent actions. "
    "When the data proves only configured capability, do not assert an actual "
    "event or causal mechanism. Avoid boilerplate, repeated caveats and raw "
    "field dumps. Provide one decisive next verification step only when the "
    "remaining uncertainty matters. Preserve all safety/authorization boundaries "
    "and do not reveal hidden reasoning."
)


def _successful_observations(receipts: list[dict[str, Any]]) -> bool:
    """Only evaluate answer quality after an actual successful current-turn read."""
    return any(
        isinstance(item, dict)
        and item.get("success") is True
        and item.get("mutates") is not True
        and str(item.get("sub_tool") or item.get("tool") or "") not in {
            "hub_search_tools"
        }
        for item in receipts
    )


def answer_quality_issues(
    request: str,
    draft: str,
    receipts: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Find omissions in a complex read-only answer, never certify its facts.

    Acknowledge properly qualified *unknown* answers as valid where evidence
    doesn't support a yes/no conclusion. Use whole words; ignore incidental
    presence of an app/device ID when determining whether the comparison was
    actually explained.
    """
    question = str(request or "").strip()[:_MAX_QUESTION]
    response = str(draft or "").strip()[:_MAX_DRAFT]
    if not question or not _successful_observations(receipts):
        return ()
    # Ordinary state lookups and commands need no analytical second pass.
    if not any(pattern.search(question) for pattern in (
        _RELATIONAL_REQUEST, _POSSIBILITY_REQUEST, _EXPLANATORY_REQUEST,
    )):
        return ()
    issues: list[str] = []
    if not response or len(response) < 45 or response == "The MCP request completed without a written answer.":
        return ("missing_substantive_answer",)
    if _RELATIONAL_REQUEST.search(question) and not _RELATIONAL_ANSWER.search(response):
        issues.append("missing_requested_comparison")
    if _POSSIBILITY_REQUEST.search(question) and not _POSSIBILITY_ANSWER.search(response):
        issues.append("missing_possibility_assessment")
    if _EXPLANATORY_REQUEST.search(question) and not _INTERPRETATION_ANSWER.search(response):
        issues.append("missing_explanation")
    # These are used to prioritize *safe* model repairs, not declare any
    # specific observation verified or turn an unanswered question into facts.
    if len(response) < 160 and _NO_FACTS.search(response):
        issues.append("uninformative_no_evidence_reply")
    return tuple(dict.fromkeys(issues))


def quality_repair_instruction(issues: tuple[str, ...]) -> str:
    """Fixed, bounded output; no arbitrary source text in the host directive."""
    allowed = {
        "missing_substantive_answer",
        "missing_requested_comparison",
        "missing_possibility_assessment",
        "missing_explanation",
        "uninformative_no_evidence_reply",
    }
    codes = [issue for issue in issues if issue in allowed]
    return (
        "HOST ANSWER-QUALITY REVISION (NO TOOLS). "
        "A previously fact-validated answer omitted: "
        + ", ".join(codes[:5])
        + ". Rewrite it to address the original question directly, preserving "
        "all verified facts and their precise qualifiers. Explain any comparison "
        "or possibility as supported, conditional, or unverified—not as a "
        "confirmed real-world execution. Keep missing evidence explicit. "
        "Do not add new facts, fabricate tool calls, manufacture timings, "
        "infer absence from incomplete sources, or propose device changes. "
        "If no supported substantive conclusion exists, say so with the "
        "specific missing source; an evidence-grounded unknown is acceptable. "
        "No tool calls, no new write authority."
    )


__all__ = [
    "QUESTION_FIRST_CONTRACT", "answer_quality_issues",
    "quality_repair_instruction",
]

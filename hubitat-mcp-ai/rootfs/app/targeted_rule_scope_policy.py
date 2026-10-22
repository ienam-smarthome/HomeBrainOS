"""Disambiguate targeted native Rule Machine evidence from whole-hub audits.

This is a scope decision, NOT read/write authorization or proof that a
particular rule exists. References such as "Hub Variable", "rule health",
"Internet device 6923" and "logs" are not requests to scan the entire hub.
"""
from __future__ import annotations

import re

_NAMED_APP = re.compile(
    r"\b(?:rule\s+machine\s+)?(?:apps?|rules?)\s*(?:id\s*)?#?\s*(\d{2,7})\b",
    re.I,
)
_COORDINATED_ID = re.compile(
    r"^\s*(?:(?:,|and|&|/)\s*)+(?:(?:apps?|rules?)\s*)?#?\s*(\d{2,7})\b",
    re.I,
)
_RULE_DETAIL = re.compile(
    r"\b(?:triggers?|actions?|if\s*[/\-]\s*else|conditions?|"
    r"variables?|counter|reset|cumulative|one.minute|"
    r"delay(?:ed|s)?|paused|enabled|rule\s+health|"
    r"runtime|execution|command\s+history|"
    r"event\s+history|verify|compare|references?|"
    r"configur(?:ation|ed)|behaviou?r|threshold)\b",
    re.I,
)
_EXPLICIT_GLOBAL_AUDIT = re.compile(
    r"\b(?:(?:whole|entire|full|comprehensive|system[\s-]?wide)"
    r"\s+(?:(?:my|the|our)\s+)?(?:hub(?:itat)?|system|smart[\s-]?home)"
    r"|(?:audit|review|check|inspect|diagnose|investigate)\s+"
    r"(?:all|every|each)\s+(?:(?:my|the|our|installed)\s+)?"
    r"(?:apps?|rules?|automations?|devices?)"
    r"|(?:all|every|each)\s+(?:installed\s+)?"
    r"(?:apps?|rules?|automations?|devices?)\b)",
    re.I,
)


def named_rule_app_ids(question: str, *, max_items: int = 3) -> tuple[str, ...]:
    """Get explicit, bounded named app IDs and a coordinated second/third ID.

    "apps 4239 and 4241" names both rules. The bare device IDs in
    "Internet device 6923" and "TV device 4221" are not rule IDs.
    """
    text = str(question or "")
    found: list[str] = []
    for match in _NAMED_APP.finditer(text):
        if match.group(1) not in found:
            found.append(match.group(1))
        tail = text[match.end():]
        for _ in range(2):
            second = _COORDINATED_ID.match(tail)
            if not second:
                break
            if second.group(1) not in found:
                found.append(second.group(1))
            tail = tail[second.end():]
        if len(found) >= max_items:
            break
    return tuple(found[:max_items])


def is_targeted_rule_investigation(question: str) -> bool:
    """True when a named app's own logic/status is the investigation scope.

    Genuine explicit *whole-hub* audits retain their broad route even if
    a named rule is one example in that requested inventory.
    """
    text = str(question or "")
    return bool(
        named_rule_app_ids(text)
        and _RULE_DETAIL.search(text)
        and not _EXPLICIT_GLOBAL_AUDIT.search(text)
    )


# A future-rule proposal can name an installed controller for comparison.
# Such a proposal remains subject to the existing no-write design safeguards.
_FUTURE_RULE_PROPOSAL = re.compile(
    r"\b(?:want|need|wish|intend|plan|planning|propose|would\s+like)"
    r"\s+(?:to\s+)?(?:create|add|build|make|design)\b"
    r"|\b(?:new|future|proposed)\s+(?:rule|automation)\b"
    r"|\b(?:design|implementation)\s+plan\s+for\s+(?:a\s+)?(?:rule|automation)\b",
    re.I,
)


def is_existing_rule_verification_request(question: str) -> bool:
    """Inspect a named *installed* app, not design another rule.

    This only labels an investigation. It grants no read/write permissions.
    Genuine future proposals that cite an existing controller as context
    must still use the established read-only proposal safeguards.
    """
    return bool(
        is_targeted_rule_investigation(question)
        and not _FUTURE_RULE_PROPOSAL.search(str(question or ""))
    )


def is_new_rule_design_review_request(question: str) -> bool:
    """Limit proposal-only *presentation* to future-design questions.

    Keep RuleAuthoringService's fail-closed no-write classifier unchanged;
    that classifier can still independently block authoring in either case.
    """
    from rule_authoring_service import RuleAuthoringService
    return bool(
        RuleAuthoringService.is_read_only_rule_design_request(question)
        and not is_existing_rule_verification_request(question)
    )

__all__ = ["named_rule_app_ids", "is_targeted_rule_investigation",
           "is_existing_rule_verification_request", "is_new_rule_design_review_request"]

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
    r"event\s+history|verif(?:y|ication)|compare|status|references?|"
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


# An exhaustive search for *one named rule's duplicates* is not a request
# to audit the entire installed automation population.
_SCOPED_EXACT_NAME = re.compile(
    r"\b(?:all|every)\s+(?:(?:installed|existing|matching|rule\s+machine)\s+){0,4}"
    r"(?:apps?|rules?|automations?)\s+(?:with|named|called|matching|sharing)\s+"
    r"(?:the\s+|an?\s+)?(?:exact\s+|same\s+|identical\s+){0,3}name\b",
    re.I,
)
_UNAMBIGUOUS_WHOLE_HUB = re.compile(
    r"\b(?:whole|entire|full|comprehensive|system[ -]?wide)\s+"
    r"(?:(?:my|the|our)\s+)?(?:hub(?:itat)?|system|smart[ -]?home)\b",
    re.I,
)


def is_targeted_rule_investigation(question: str) -> bool:
    """True when a named app's own logic/status is the investigation scope.

    Genuine explicit *whole-hub* audits retain their broad route even if
    a named rule is one example in that requested inventory.
    """
    text = str(question or "")
    return bool(
        named_rule_app_ids(text)
        and _RULE_DETAIL.search(text)
        and (
            not _EXPLICIT_GLOBAL_AUDIT.search(text)
            or (
                _SCOPED_EXACT_NAME.search(text)
                and not _UNAMBIGUOUS_WHOLE_HUB.search(text)
            )
        )
    )


# A future-rule proposal can name an installed controller for comparison.
# Such a proposal remains subject to the existing no-write design safeguards.
_FUTURE_RULE_PROPOSAL = re.compile(
    r"\b(?:want|need|wish|intend|plan|planning|propose|would\s+like)"
    r"\s+(?:to\s+)?(?:create|add|build|make|design)\b"
    r"|\b(?:design|propose|draft|outline)\s+(?:a|an|the)?\s*"
    r"(?:new|future|proposed)\s+(?:rule|automation)\b"
    r"|\b(?:design|implementation)\s+plan\s+for\s+(?:a\s+)?(?:rule|automation)\b",
    re.I,
)


_DEEP_INSTALLED_RULE_EVIDENCE = re.compile(
    r"\b(?:persisted|ordered|duplicates?|exact[ -]?name|compare|"
    r"contradict\w*|overlap\w*|interfer\w*|cross[ -]?check|"
    r"cancelable|cancellable|nested|"
    r"action\s+(?:sequence|tree|order)|triggers?.{0,24}actions?)\b",
    re.I,
)
_HISTORICAL_RULE_EVENT = re.compile(
    r"\b(?:historical|yesterday|earlier|latest|previous|"
    r"past\s+(?:off|on|event|command|execution)|actually\s+engaged)\b",
    re.I,
)


_NEGATED_PROPOSAL = re.compile(
    r"(?:\b(?:do\s+not|don't|never|without)\s+"
    r"|\bnot\s+(?:a|an|my)\s+request\s+to\s+)"
    r"(?:(?:please|ever|actually|yet|now)\s+)?$",
    re.I,
)


def _requests_future_rule_design(question: str) -> bool:
    """Require an *affirmative* future-rule proposal, not a prohibition."""
    text = str(question or "")
    return any(
        not _NEGATED_PROPOSAL.search(text[max(0, match.start() - 60):match.start()])
        for match in _FUTURE_RULE_PROPOSAL.finditer(text)
    )


def is_existing_rule_verification_request(question: str) -> bool:
    """A *deep*, named installed-rule audit, not a status fast-path or proposal.

    Ordinary current-configuration/status reads must preserve the pre-existing
    direct Rule Machine analyser; historical lockout/event questions must keep
    their dedicated provenance route. This predicate grants no authority.
    """
    text = str(question or "")
    return bool(
        is_targeted_rule_investigation(text)
        and _DEEP_INSTALLED_RULE_EVIDENCE.search(text)
        and not _HISTORICAL_RULE_EVENT.search(text)
        and not _requests_future_rule_design(text)
    )


def is_new_rule_design_review_request(question: str) -> bool:
    """Limit proposal-only *presentation* to future-design questions.

    Keep RuleAuthoringService's fail-closed no-write classifier unchanged;
    that classifier can still independently block authoring in either case.
    """
    from rule_authoring_service import RuleAuthoringService
    if not RuleAuthoringService.is_read_only_rule_design_request(question):
        return False
    if is_existing_rule_verification_request(question):
        return False
    # No installed Rule Machine app is named: retain the historical safe
    # proposal-only treatment for generic design requests. When an app ID is
    # named, do NOT treat routine current status/inspection and a "do not
    # propose a new rule" ban as an affirmative design request.
    return not named_rule_app_ids(question) or _requests_future_rule_design(question)

__all__ = ["named_rule_app_ids", "is_targeted_rule_investigation",
           "is_existing_rule_verification_request", "is_new_rule_design_review_request"]

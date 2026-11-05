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



# An isolated native authoring/runbook review is about the *prospective API
# contract*, not the saved action tree of an installed Rule Machine child.
# Scope is explicit and read-only; this predicate never permits a write.
_NATIVE_CONTRACT_SUBJECT = re.compile(
    r"(?i)\b(?:Rule Machine|MCP Rule Server|hub_set_rule|"
    r"native\s+(?:rule|trigger|automation)|"
    r"dated[\s-]?trigger|one[\s-]?time\s+(?:rule|trigger))\b"
)
_NATIVE_CONTRACT_ARTIFACT = re.compile(
    r"(?i)\b(?:runbook|authoring\s+contract|"
    r"(?:native|typed)\s+(?:trigger|action|field|rule)\s+(?:schema|contract|types?)|"
    r"(?:(?:trigger|action|input)\s+)?field\s+types?|"
    r"date\s*(?:and|/)\s*time\s+formats?|"
    r"creation\s+(?:payload|structure|schema|contract)|"
    r"native\s+(?:create|creation)\s+(?:structure|schema|payload|contract)|"
    r"one[\s-]?time\s+dated[\s-]?trigger)\b"
)
_NATIVE_CONTRACT_REVIEW = re.compile(
    r"(?i)\b(?:review|validate|evaluate|assess|verify|compare|"
    r"inspect|check|explain|audit)\b"
)
_NATIVE_READ_ONLY = re.compile(
    r"(?i)\b(?:read[\s-]?only|do\s+not\s+(?:create|modify|execute|write|"
    r"change|delete|schedule|queue)|without\s+(?:creating|modifying|"
    r"executing|writing|changing|scheduling))\b"
)
_EXPLICIT_SAVED_RULE_TARGET = re.compile(
    r"(?i)\b(?:existing|installed|saved|persisted|current)\s+"
    r"(?:native\s+|Rule Machine\s+)?(?:rule|automation)\b"
)


def is_native_rule_contract_review_request(question: str) -> bool:
    """Read-only native authoring *contract* review, not installed-rule audit.

    An explicit saved child rule or its action tree takes precedence, even
    if the authoring guide is mentioned as a comparison source. Parent app
    identity may still be a prerequisite in a contract review.
    """
    text = str(question or "")
    clauses = [
        part for part in re.split(r"[.!?\n;]+", text)
        if not re.match(
            r"(?i)^\s*(?:do\s+not|don't|never|avoid|without|no)\b", part
        )
    ]
    positive = " ".join(clauses)
    if not (
        _NATIVE_CONTRACT_SUBJECT.search(positive)
        and _NATIVE_CONTRACT_ARTIFACT.search(positive)
        and _NATIVE_CONTRACT_REVIEW.search(positive)
        and _NATIVE_READ_ONLY.search(text)
    ):
        return False
    if _EXPLICIT_SAVED_RULE_TARGET.search(positive):
        return False
    ids = named_rule_app_ids(positive, max_items=4)
    if ids and not (
        len(ids) == 1 and ids[0] == "169"
        and re.search(r"(?i)\bparent\b", positive)
    ):
        return False
    return True


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



# A native app/type/parent *identity* question is not an audit of that app's
# executable rule logic. Preserve this separate positive objective regardless
# of the LLM's advisory classification. Require identity semantics and do not
# override an explicit combined action-tree/trigger audit.
_CLASS_IDENTITY_SUBJECT = re.compile(
    r"(?i)\b(?:apps?|application|instances?|rule\s+machine|parent\s+apps?)\b"
)
_CLASS_IDENTITY_ATTRIBUTE = re.compile(
    r"(?i)\b(?:native\s+(?:built[\s-]*in\s+)?(?:class|type|parent|rule\s+machine\s+parent)|"
    r"app[\s-]*type(?:id)?|"
    r"(?:type|class|namespace)\s+(?:identity|relationship|mapping|binding|catalog)|"
    r"(?:parent|class)\s+(?:identity|verification)|"
    r"built[\s-]*in\s+(?:type|class|parent)|"
    r"(?:source[\s-]*attested|independently\s+verified)\s+"
    r"(?:native\s+)?(?:class|type|parent))\b"
)
_EXECUTABLE_LOGIC_REQUEST = re.compile(
    r"(?i)\b(?:ordered\s+actions?|action\s+(?:tree|sequence|conditions?)|"
    r"triggers?\s+(?:and|or|with)\s+actions?|"
    r"(?:persisted|compiled)\s+(?:actions|triggers|rule\s+logic)|"
    r"delay\s+cancellations?|controller\s+interference)\b"
)


def is_app_class_identity_question(question: str) -> bool:
    """Positive app-class/parent typing objective, not stored-rule certification.

    One source's display label and an incomplete type-class catalog do not
    identify a native parent. This is only a read-only routing distinction.
    """
    text = str(question or "")
    return bool(
        _CLASS_IDENTITY_SUBJECT.search(text)
        and _CLASS_IDENTITY_ATTRIBUTE.search(text)
        and not _EXECUTABLE_LOGIC_REQUEST.search(text)
        and not _EXPLICIT_GLOBAL_AUDIT.search(text)
        and not _requests_future_rule_design(text)
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
    from ai_investigation_routing import active_request_interpretation
    interpretation = active_request_interpretation(question)
    # A mistaken model label must not turn native app identity verification
    # into a complete executable-action/duplicate-controller audit.
    if is_app_class_identity_question(text) or is_native_rule_contract_review_request(text):
        return False
    if interpretation is not None and interpretation.objective is not None:
        return interpretation.objective == "existing_rule_verification"
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
    if is_native_rule_contract_review_request(question):
        return True
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
           "is_app_class_identity_question", "is_existing_rule_verification_request",
           "is_new_rule_design_review_request", "is_native_rule_contract_review_request"]

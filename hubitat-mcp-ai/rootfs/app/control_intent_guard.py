"""Fail-closed boundary for *immediate* smart-home command shortcuts.

This parser never chooses a tool, device or write authority. It only rejects
qualifiers that a single-action fast path cannot implement. The ordinary AI
path remains responsible for interpretation; a model tool call alone must
not convert a condition or question into authority to execute immediately.
"""
from __future__ import annotations

import re

# Conjunctions and subordinate conditions create additional user objectives or
# scheduling/precondition semantics that a single immediate actuation loses.
_UNQUALIFIED = re.compile(
    r"\b(?:if|unless|when|whenever|once|while|before|after|until|"
    r"provided|depending|assuming|because|except|and|but|then|"
    r"actually|wait|later|tomorrow|tonight|every|schedule|"
    r"only\s+if|as\s+soon\s+as)\b",
    re.I,
)
_CANCELLED = re.compile(
    r"(?i)^\s*(?:please\s+)?(?:don['’]?t|do\s+not|never|"
    r"stop\s+me\s+from|should\s+i|could\s+i|would\s+i|what\s+if)\b"
)
_CONTROL_LEAD = re.compile(
    r"(?i)^\s*(?:please\s+)?(?:turn|switch|power|toggle|set|dim|"
    r"change|block|unblock|allow|enable|disable|restrict)\b"
)
_INTERROGATIVE_CONTROL = re.compile(r"\?|[;]|\n")
_EXPLANATORY_TARGET = re.compile(
    r"(?i)^\s*(?:allow|enable)\s+me\s+to\b"
)
# Category labels, not configured device IDs: never base criticality on an
# exact name. Host asks approval before acting on anything resembling these.
_PROTECTED = re.compile(
    r"(?i)(?<![a-z])(?:freezer|fridge|refrigerator|router|modem|"
    r"gateway|camera|cam|security|alarm|hub|server|mesh|"
    r"network|internet)(?![a-z])"
)
_UNBOUNDED_TARGET = re.compile(
    r"(?i)\b(?:all|every|everything|whole|entire)\b"
)
# This grammar admits only a command-like *beginning* to the semantic
# control planner. It does not independently authorise an action; the model
# or exact parser must still generate and ground a valid typed plan.
_SEMANTIC_CONTROL_LEAD = re.compile(
    r"(?i)^\s*(?:please\s+|(?:(?:can|could|would|will)\s+you\s+"
    r"(?:please\s+)?))?"
    r"(?:turn|switch|power|toggle|set|dim|change|brighten|"
    r"increase|decrease|raise|lower|reduce|adjust|make|"
    r"boost|heat|cool)\b"
)
_EXPLICIT_READ_ONLY = re.compile(
    r"(?i)\b(?:read[\s-]*only|do\s+not\s+(?:modify|change|"
    r"control|turn|switch|execute|send|write|alter)\s+anything|"
    r"don['’]?t\s+(?:modify|change|execute|send|write)\s+anything|"
    r"no\s+(?:device\s+)?changes|without\s+(?:making|"
    r"any)\s+changes)\b"
)


# A shared, permission-only polarity check. This never selects a device,
# operation or tool; positive writes still need independent host approval.
_INDEPENDENT_ACTION = re.compile(
    r"(?i)(?:[.!?;:]\s*|\b(?:and(?:\s+then)?|but|instead)\s+)"
    r"(?:(?:also|then|instead|now)\s+)?(?:please\s+)?"
    r"(?P<verb>turn|switch|set|change|create|delete|disable|enable|"
    r"restart|reboot|block|unblock|allow|configure|remove|pause|resume)\b"
)
_NEGATED_OBJECT = re.compile(
    r"(?i)^\s*(?:nothing\b|none\b|neither\b|no\s+)"
)
_INFORMATIONAL_RESULT = re.compile(
    r"(?i)^\s*(?:an?\s+|the\s+)?(?:report|summary|explanation|"
    r"analysis|comparison|review|assessment|plan|draft|table|list|"
    r"recommendation|timeline)\b"
)
_QUESTION_LEAD = re.compile(
    r"(?i)^\s*(?:why|how|what|when|where|which|is|are|was|were|"
    r"did|does|do|could|can|should|would|will)\b"
)


def independent_affirmative_mutation_clause(
    prompt: str, *, start: int = 0,
) -> bool:
    """An independent positive imperative, not a quoted or negated action.

    This predicate *only denies* read-only admission; it cannot authorise a
    write. Textual deliverables are not hub-state modifications.
    """
    text = str(prompt or "")
    part = text[max(0, start):]
    first_question = part.find("?")
    question_lead = bool(_QUESTION_LEAD.match(part))
    for match in _INDEPENDENT_ACTION.finditer(part):
        if question_lead and first_question >= 0 and match.start() < first_question:
            continue
        target = part[match.end():]
        if _NEGATED_OBJECT.match(target):
            continue
        if (match.group("verb").casefold() in ("create", "change")
                and _INFORMATIONAL_RESULT.match(target)):
            continue
        return True
    return False


def explicitly_read_only_request(prompt: str) -> bool:
    """No-write instruction for the current action, not a route to execute.

    The read-only clause protects the investigation. A separately requested
    later write (e.g. "Read-only verify X. Also disable Y") retains ordinary
    host write/confirmation checks; it does not execute as a fast shortcut.
    An explicit global "do not modify anything" still vetoes everything.
    """
    text = str(prompt or "")
    match = _EXPLICIT_READ_ONLY.search(text)
    if match is None:
        return False
    if not re.fullmatch(r"read[\s-]*only", match.group(), flags=re.I):
        return True
    # Only a *new* independently imperative clause after a scoped READ-ONLY
    # instruction can restore write intent. Embedded historical descriptions
    # like "turn ON" and explanatory questions do not.
    return not independent_affirmative_mutation_clause(
        text, start=match.end())


def unqualified_immediate_clause(prompt: str) -> bool:
    """True only when an immediate clause has no ignored extra objectives.

    This is a necessary condition for shortcuts, never sufficient consent.
    The actual exact target/action parser and safety gates still apply.
    """
    text = " ".join(str(prompt or "").strip().split())
    return bool(
        text and not explicitly_read_only_request(text)
        and not _INTERROGATIVE_CONTROL.search(text)
        and not _CANCELLED.search(text)
        and not _EXPLANATORY_TARGET.search(text)
        and not _UNQUALIFIED.search(text)
    )


def semantic_control_clause_eligible(prompt: str) -> bool:
    """Let valid multi-target commands reach the semantic grounder, not a
    regex executor. Semantic room/selection controls are still subject to
    post-grounding approval. Compound requests for a second *action* are
    excluded (e.g. "turn on TV and tell me its power").
    """
    text = " ".join(str(prompt or "").strip().split())
    # The earlier predicate accepted *any* unqualified sentence, including
    # questions about automation behaviour, and sent it into a write-only
    # sensitive-control resolver. Admit only command-shaped language.
    if (not _SEMANTIC_CONTROL_LEAD.search(text)
            or explicitly_read_only_request(text)):
        return False
    if unqualified_immediate_clause(text):
        return True
    if not text or _INTERROGATIVE_CONTROL.search(text) or _CANCELLED.search(text):
        return False
    if re.search(
        r"(?i)\band\s+(?:tell|show|check|read|report|explain|"
        r"create|restart|reboot|shutdown|change|set|turn|switch|"
        r"unlock|disable|enable|update|delete|write)\b",
        text,
    ):
        return False
    # A simple conjunction of entity labels may be grounded as an exact
    # multi-device selection. No other scheduling or conditional qualifiers.
    return bool(
        re.search(r"(?i)\band\b", text)
        and not _UNQUALIFIED.search(
            re.sub(r"(?i)\band\b", " ", text)
        )
        and not _EXPLANATORY_TARGET.search(text)
    )


def unsafe_control_prompt(prompt: str) -> bool:
    """Block mutation authority for qualified single-control directives.

    A rule-authoring request starting with 'create a rule' remains separate:
    these restrictions only apply to lead-in immediate control verbs.
    """
    text = str(prompt or "").strip()
    if not _CONTROL_LEAD.search(text):
        return False
    if _EXPLANATORY_TARGET.search(text):
        return True
    # Explicit additional administrative action (hub restart, rule delete)
    # is separately confirmable by the pre-existing sensitive-action gate.
    # Likewise an independent second direct imperative remains a write
    # request for the *full* model/tool workflow, not the single-action
    # immediate fast path. No model call can bypass confirmation for the
    # sensitive action.
    if re.search(
        r"(?i)\b(?:and|then)\s+(?:restart|reboot|shutdown|install|"
        r"delete|disable|enable)\s+(?:the\s+)?(?:hub|app|rule)\b"
        r"|(?:,\s*)?then\s+(?:turn|switch|power)\s+",
        text,
    ):
        return False
    # 'Change my light OFF now and then check logs' is an explicit
    # write+read workflow, not an unqualified immediate shortcut. Allow
    # the model loop to handle both parts instead of discarding the read.
    if re.match(r"(?i)^(?:please\s+)?change\b", text) and re.search(
        r"(?i)\band\s+then\s+(?:check|show|read|report)\b", text,
    ):
        return False
    # Admin app/rule directives are not single-device commands; retain
    # their existing typed sensitive authorization and confirmation.
    if re.match(
        r"(?i)^(?:please\s+)?(?:enable|disable|allow|restrict|"
        r"block|unblock)\s+(?:app\b|rule\b)", text,
    ):
        return False
    return not unqualified_immediate_clause(text)


def needs_sensitive_control_confirmation(
    arguments: dict, *, resolved_labels: list[str] | None = None,
) -> bool:
    names = [
        str(s) for s in (arguments.get("device_names") or [])
    ]
    if resolved_labels is not None:
        names = list(resolved_labels)
    return bool(
        arguments.get("room") or arguments.get("all_lights")
        or len(names) != 1
        or any(_UNBOUNDED_TARGET.search(s) or _PROTECTED.search(s) for s in names)
    )


__all__ = [
    "unqualified_immediate_clause", "semantic_control_clause_eligible",
    "unsafe_control_prompt", "explicitly_read_only_request",
    "needs_sensitive_control_confirmation",
    "independent_affirmative_mutation_clause",
]

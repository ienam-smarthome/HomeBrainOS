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


def unqualified_immediate_clause(prompt: str) -> bool:
    """True only when an immediate clause has no ignored extra objectives.

    This is a necessary condition for shortcuts, never sufficient consent.
    The actual exact target/action parser and safety gates still apply.
    """
    text = " ".join(str(prompt or "").strip().split())
    return bool(
        text and not _INTERROGATIVE_CONTROL.search(text)
        and not _CANCELLED.search(text)
        and not _EXPLANATORY_TARGET.search(text)
        and not _UNQUALIFIED.search(text)
    )


def unsafe_control_prompt(prompt: str) -> bool:
    """Block mutation authority for qualified single-control directives.

    A rule-authoring request starting with 'create a rule' remains separate:
    these restrictions only apply to lead-in immediate control verbs.
    """
    text = str(prompt or "").strip()
    return bool(
        _CONTROL_LEAD.search(text)
        and not unqualified_immediate_clause(text)
    )


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
    "unqualified_immediate_clause",
    "unsafe_control_prompt",
    "needs_sensitive_control_confirmation",
]

"""Request-intent gates for intelligent, evidence-bounded automation diagnosis.

A fast inventory is useful for `show broken automations`, but it cannot tell
whether a rule actually executes. Diagnostic requests must use MCP evidence and
the model's investigative path rather than silently falling back to the list.
"""
from __future__ import annotations

import re

_SUBJECT = re.compile(r"\b(?:automations?|rules?|apps?|rule\s+machine)\b", re.I)
_DIAGNOSTIC = re.compile(
    r"\b(?:why|diagnos(?:e|is|tic)|investigat(?:e|ion)|troubleshoot|"
    r"fail(?:ed|ing|ure|s)?|fault(?:y|s)?|errors?|timeouts?|"
    r"broken\s+actions?|invalid\s+actions?|misfir(?:e|ing)|"
    r"dependencies?|missing\s+(?:device|target)|"
    r"not\s+(?:working|running|triggering|executing|firing)|"
    r"doesn['’]?t\s+(?:work|run|trigger|execute|fire)|"
    r"stopp?ed\s+working|"
    r"runtime|execution|not\s+responding)\b",
    re.I,
)
_BROAD = re.compile(
    r"\b(?:all|every|entire|whole|across|any|which|"
    r"my\s+(?:automations|rules|apps)|"
    r"system|hub|overall|full|comprehensive)\b", re.I
)
_MUTATION = re.compile(
    r"^\s*(?:please\s+)?(?:fix|repair|delete|remove|disable|enable|"
    r"rebuild|reset|change|update)\s+", re.I
)


def is_automation_runtime_diagnostic(prompt: str) -> bool:
    """Investigate automation failures, not ordinary marker/inventory requests."""
    text = str(prompt or "").strip()
    return bool(_SUBJECT.search(text) and _DIAGNOSTIC.search(text))


def is_broad_automation_runtime_diagnostic(prompt: str) -> bool:
    """Select the read-only whole-hub audit for broad investigation requests.

    Explicit mutation directives instead enter the regular confirmation-safe
    agent. Targeted `why did rule N fail` questions stay in the agent's
    investigative tool loop and do not unnecessarily scan the entire hub.
    """
    text = str(prompt or "").strip()
    return bool(
        is_automation_runtime_diagnostic(text)
        and _BROAD.search(text)
        and not _MUTATION.search(text)
    )


AUTOMATION_DIAGNOSTIC_INSTRUCTION = (
    "\n\nAUTOMATION DIAGNOSIS — EVIDENCE-FIRST INVESTIGATION\n"
    "The user asks about an automation failure, not merely the app inventory. "
    "Examine the named rule/app, its relevant trigger, compiled action/target "
    "references, recent bounded logs, device and integration dependencies "
    "using available read tools when relevant. Discover and use tools rather "
    "than guessing an MCP operation or treating an enabled state as a successful "
    "execution. A missing last-event timestamp alone is not a fault; only flag "
    "a missed check-in when an expected reporting cadence is independently "
    "established. A Rule Machine *BROKEN* label can be stale; compiled "
    "Broken Action and null target device references carry stronger evidence. "
    "Reading a Hubitat config page can trigger recompilation and change its "
    "broken label, so avoid config-page reads unless required, and disclose "
    "that side effect when used. Separate observed failures, plausible causes "
    "and unknowns. Report exact IDs and times with evidence; prefer concrete "
    "read-only next verification steps. Never silently repair, disable or delete "
    "rules, and never reveal private chain-of-thought."
)

__all__ = [
    "AUTOMATION_DIAGNOSTIC_INSTRUCTION",
    "is_automation_runtime_diagnostic",
    "is_broad_automation_runtime_diagnostic",
]

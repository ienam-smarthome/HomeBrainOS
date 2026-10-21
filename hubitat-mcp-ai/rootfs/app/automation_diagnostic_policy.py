"""Request-intent gates for intelligent, evidence-bounded automation diagnosis.

A fast inventory is useful for `show broken automations`, but it cannot tell
whether a rule actually executes. Diagnostic requests must use MCP evidence and
the model's investigative path rather than silently falling back to the list.
"""
from __future__ import annotations

import re

from targeted_rule_scope_policy import is_targeted_rule_investigation

_SUBJECT = re.compile(r"\b(?:automations?|rules?|apps?|rule\s+machine)\b", re.I)
_DIAGNOSTIC = re.compile(
    r"\b(?:why|audit|inspect|diagnos(?:e|is|tic)|investigat(?:e|ion)|troubleshoot|"
    r"fail(?:ed|ing|ure|s)?|fault(?:y|s)?|errors?|timeouts?|"
    r"broken\s+actions?|invalid\s+actions?|misfir(?:e|ing)|"
    r"dependencies?|missing\s+(?:device|target)|"
    r"not\s+(?:working|running|triggering|executing|firing)|"
    r"doesn['’]?t\s+(?:work|run|trigger|execute|fire)|"
    r"stopp?ed\s+working|"
    r"runtime|execution|not\s+responding)\b",
    re.I,
)
# Broad scope must apply to the automation population or whole-hub
# diagnostics, not to an unrelated word elsewhere in the question.
# In particular, 'which history source supports ...' is NOT permission
# to replace a named light-event investigation with a whole-hub audit.
_BROAD_AUTOMATION_COLLECTION = re.compile(
    r"\b(?:all|every|any|which|my|our|entire|whole|full|comprehensive)"
    r"\s+(?:of\s+)?(?:(?:my|our|the|installed|existing|active|paused|"
    r"running|broken|failed|failing|current)\s+){0,4}"
    r"(?:automations|rules|apps)\b",
    re.I,
)
# Accept a coordinated list of *automation-state* modifiers. A request to
# investigate "my broken or incomplete Hubitat automations" is still broad
# despite the conjunction; an arbitrary device/room name between "my" and
# "automations" is not. This complements the strict original grammar without
# turning single-device causal questions into whole-hub audits.
_BROAD_STATE_MODIFIER = re.compile(
    r"\b(?:all|every|my|our)\s+"
    r"(?:(?:broken|failed|failing|incomplete|paused|disabled|active|"
    r"installed|existing|faulty|misconfigured|unresponsive|hubitat|"
    r"rule\s+machine|or|and)\s+){1,7}"
    r"(?:automations|rules|apps)\b",
    re.I,
)

# An owner-qualified population often includes a natural-language comma
# list: "all my broken, incomplete, disabled or potentially faulty Hubitat
# automations". The simple state-modifier grammar cannot match punctuation.
# Match the scoped population, not isolated words; existing targeted-incident
# exclusion still prevents an unrelated single-light question from expanding.
_BROAD_OWNED_POPULATION = re.compile(
    r"\b(?:all|each|every)\s+(?:my|our|the)\s+"
    r"[^.!?]{0,110}\b(?:automations|rules|apps)\b",
    re.I,
)

_BROAD_EVERY_SINGLE = re.compile(
    r"\b(?:each|every)\s+"
    r"(?:(?:my|our|the|installed|existing|active|running)\s+){0,3}"
    r"(?:automation|rule|app)\b",
    re.I,
)
_BROAD_AUTOMATION_LOGS = re.compile(
    r"\b(?:all|every|entire|whole|full|comprehensive)\s+"
    r"(?:(?:my|the|our)\s+)?(?:automation|rule|app)\s+"
    r"(?:logs?|executions?|statuses?|failures?|errors?)\b",
    re.I,
)
_BROAD_HUB_SCOPE = re.compile(
    r"\b(?:system[- ]wide|across\s+(?:(?:my|our|the|all)\s+)?(?:hub|system)|"
    r"(?:whole|entire|full|comprehensive)\s+(?:hub|system))\b",
    re.I,
)


def has_broad_automation_scope(prompt: str) -> bool:
    """Require grammatical broad *automation* scope, not isolated words.

    'Any', 'which', 'system', 'all' and 'my' are ubiquitous in targeted
    questions and must not independently trigger a 200-device System Check.
    """
    text = str(prompt or "").strip()
    return bool(
        _BROAD_AUTOMATION_COLLECTION.search(text)
        or _BROAD_STATE_MODIFIER.search(text)
        or _BROAD_OWNED_POPULATION.search(text)
        or _BROAD_EVERY_SINGLE.search(text)
        or _BROAD_AUTOMATION_LOGS.search(text)
        or _BROAD_HUB_SCOPE.search(text)
    )
_MUTATION = re.compile(
    r"^\s*(?:please\s+)?(?:fix|repair|delete|remove|disable|enable|"
    r"rebuild|reset|change|update)\s+", re.I
)


_TARGETED_EVENT_INTENT = re.compile(
    r"\b(?:why|investigat(?:e|ion)|explain|trace|caus(?:e|ed))\b", re.I
)
_TARGETED_DEVICE = re.compile(
    r"\b(?:lights?|lamps?|bulbs?|switch(?:es)?|sockets?|plugs?|"
    r"fans?|outlets?|thermostats?|devices?)\b", re.I
)
_TARGETED_STATE_CHANGE = re.compile(
    r"\b(?:turn(?:ed)?|switch(?:ed)?|went|came|power(?:ed)?)\s+"
    r"(?:on|off)\b", re.I
)
_SINGLE_EVENT_ANCHOR = re.compile(
    r"\b(?:at|around|about|before|after)\s+(?:approximately\s+)?"
    r"\d{1,2}:\d{2}|\b(?:today|yesterday|last\s+night)\b", re.I
)


def is_targeted_device_transition_investigation(prompt: str) -> bool:
    """Keep a timed, named ON/OFF event out of whole-hub audit shortcuts.

    An automation can be mentioned as a possible cause without making a
    single-light forensic investigation a request to audit all automations.
    These terms establish routing *scope*, not a causal claim.
    """
    text = str(prompt or "").strip()
    return bool(
        _TARGETED_EVENT_INTENT.search(text)
        and _TARGETED_DEVICE.search(text)
        and _TARGETED_STATE_CHANGE.search(text)
        and _SINGLE_EVENT_ANCHOR.search(text)
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
        and has_broad_automation_scope(text)
        and not is_targeted_rule_investigation(text)
        and not is_targeted_device_transition_investigation(text)
        and not _MUTATION.search(text)
    )


_INTEGRATION_SUBJECT = re.compile(
    r"\b(?:integrations?|polling|telemetry|api|service|"
    r"octopus\s+energy|meter\s+data)\b", re.I
)

INTEGRATION_DIAGNOSTIC_INSTRUCTION = (
    "\n\nINTEGRATION DIAGNOSTICS — BOUNDED LOG EVIDENCE\n"
    "Investigate current evidence of integration errors and successful telemetry "
    "separately; check the integration app's own errors where tools permit. "
    "Recent INFO logs or an online attribute show recent apparent operation, "
    "not continuous health and not the absence of earlier polling failures. "
    "For filtered or capped logs state precisely what was checked, how many "
    "rows were returned, the limit and whether full lookback coverage is "
    "independently verified. Never say there were no failures throughout "
    "24 hours from a latest-N log sample; infer recovery only when failure "
    "then later success timestamps are reliably ordered. Source-local naive "
    "time values do not establish UTC chronology. Identify what could not "
    "be verified, keep conclusions bounded, and do not mutate settings."
)


def is_integration_runtime_diagnostic(prompt: str) -> bool:
    """Dedicated model investigation for integration health and failed polls."""
    text = str(prompt or "").strip()
    return bool(_INTEGRATION_SUBJECT.search(text) and _DIAGNOSTIC.search(text))


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
    "has_broad_automation_scope",
    "is_targeted_device_transition_investigation",
    "is_integration_runtime_diagnostic",
    "INTEGRATION_DIAGNOSTIC_INSTRUCTION",
]

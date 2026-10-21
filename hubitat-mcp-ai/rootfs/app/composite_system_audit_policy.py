"""Classify genuinely cross-domain whole-hub audits independently of model tier.

A request to inspect errors, devices, installed automation rules and scheduled
work should use the existing deterministic System Check service, not a generic
performance-only synthesis of a bounded recent log sample. Keep scheduler-only
and targeted historical/device questions on their dedicated routes.
"""
from __future__ import annotations

import re

from automation_diagnostic_policy import is_targeted_device_transition_investigation
from targeted_rule_scope_policy import is_targeted_rule_investigation

_GLOBAL = re.compile(
    r"\b(?:whole|entire|full|comprehensive|system[\s-]?wide|"
    r"all\s+(?:apps?|rules?|devices?|automations?|drivers?)|"
    r"hub(?:itat)?(?:\s+health)?|my\s+smart[\s-]?home)\b", re.I,
)
_ACTION = re.compile(
    r"\b(?:audit|review|inspect|check|diagnos\w*|investigat\w*|"
    r"analys\w*|analyz\w*|optimis\w*|optimiz\w*|"
    r"recommend\w*|find\s+(?:issues|problems|faults))\b", re.I,
)
_CONFIG_DEPENDENCY = re.compile(
    r"\b(?:configur\w*|dependenc\w*|triggers?|targets?|overlap\w*|"
    r"shared\s+(?:devices?|actions?))\b", re.I,
)

_DOMAINS = {
    "health": re.compile(r"\b(?:health|firmware|memory|backup|temperature|stability|uptime)\b", re.I),
    "logs": re.compile(r"\b(?:logs?|errors?|warnings?|exceptions?|failures?|faults?)\b", re.I),
    "devices": re.compile(r"\b(?:devices?|drivers?|offline|stale|watchdogs?|battery|sensors?)\b", re.I),
    "automation": re.compile(r"\b(?:automations?|rules?|rule machine|apps?|overlap|disabled|broken)\b", re.I),
    "scheduler": re.compile(r"\b(?:schedul\w*|jobs?|handlers?|tick|polling|timers?)\b", re.I),
    "performance": re.compile(r"\b(?:performance|stats|statistics|busy|latency|efficien\w*|load|cpu)\b", re.I),
}


def is_cross_domain_hub_audit_request(question: str) -> bool:
    """True for full audit plus fault checks spanning independent source classes."""
    text = " ".join(str(question or "").split())
    if len(text) < 18 or not _GLOBAL.search(text) or not _ACTION.search(text):
        return False
    if is_targeted_rule_investigation(text) or is_targeted_device_transition_investigation(text):
        return False
    present = {name for name, pattern in _DOMAINS.items() if pattern.search(text)}
    # Distinguish a multi-domain reliability review from a review of just
    # performance, just scheduler ownership, or a single device's status.
    conventional_audit = (
        len(present) >= 4
        and "logs" in present
        and "automation" in present
        and ("devices" in present or "health" in present)
    )
    # A full-hub dependency audit legitimately spans scheduler, installed
    # automations and device action targets without explicitly asking for logs.
    # Requiring the literal word "logs" incorrectly sent these requests to the
    # iterative model agent instead of the deterministic configuration probe.
    # "Shared targets" and "device targets" denote device-action edges
    # even when the noun "device" does not appear (real CI regression).
    # Do not treat arbitrary targets, such as optimisation goals, as devices.
    target_domain = bool(re.search(
        r"\b(?:(?:shared|device|action)\s+targets?|target\s+devices?)\b",
        text, re.I,
    ))
    configuration_audit = (
        {"automation", "scheduler"} <= present
        and ("devices" in present or target_domain)
        and bool(_CONFIG_DEPENDENCY.search(text))
    )
    return conventional_audit or configuration_audit


__all__ = ["is_cross_domain_hub_audit_request"]

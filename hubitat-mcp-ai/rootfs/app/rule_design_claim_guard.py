"""Fail-closed calibration of proposal-only Rule Machine design claims.

This is a *read-only* output guard. It cannot verify the requested rule's
native action schema from a tool name or description and does not create or
validate any proposed JSON. It preserves model observations, while replacing
unsupported strong claims with explicit evidence bounds.
"""
from __future__ import annotations

import re
from typing import Any

_UNSUPPORTED_CREATION = re.compile(
    r"(?i)\b(?:I\s+will\s+use\s+the\s+)?"
    r"`?hub_manage_rule_machine`?\s+gateway\s+to\s+"
    r"create\s+(?:a|the)\s+native\s+Rule\s+Machine\s+rule\b"
)
_ALL_REQUIRED = re.compile(
    r"(?i)(?:yes[. !:]*\s*)?the\s+`?hub_set_rule`?\s+tool\s+"
    r"supports\s+all\s+required\s+components"
)
_MIDNIGHT_CERTAINTY = re.compile(
    r"(?i)\bRule Machine natively handles time windows that cross midnight\b"
)
_LOCKOUT_CERTAINTY = re.compile(
    r"(?i)\b(?:it|this rule)\s+will\s+not\s+trigger\s+or\s+"
    r"interfere\s+with\s+the\s+lockout\b"
)
_LOCKOUT_ABSOLUTE = re.compile(
    r"(?i)\bit\s+cannot\s+(?:accidentally\s+)?(?:bypass|trigger)\s+"
    r"(?:or\s+trigger\s+)?(?:a|the)\s+(?:motion[- ]activation\s+)?lockout\b"
)

_SAFETY_NOTE = (
    "\n\n### Rule design feasibility gate (read-only)\n"
    "**Not yet validated as a native Hubitat rule.** A current-turn tool "
    "receipt for an app page or the existence of the `hub_set_rule` name "
    "does not establish that the gateway supports the *combined* triggers, "
    "required expression, timed waits, action branches or cancellation. "
    "Verify the actual installed native operation schema before proposing "
    "a structured write. No rule should be queued from this review.\n\n"
    "**Timing caveat:** A `Wait for Event: motion active` with a ten-minute "
    "timeout can finish when motion becomes active **or** when ten minutes "
    "elapse. Continuing after the wait is not proof of ten uninterrupted "
    "minutes inactive. A correct implementation must recheck sensor state, "
    "distinguish event versus timeout (or use a verified duration expression), "
    "and handle retriggers and cancellation. Include a 23:00 entry case "
    "when the light was already on and idle, and a *final* 23:00–06:00 "
    "eligibility check immediately before every OFF. Required-expression "
    "eligibility alone is not proof that a previously pending OFF is "
    "cancelled at 06:00.\n\n"
    "**Existing controller:** An OFF-only rule is not automatically independent "
    "of app 4019's manual-off lockout. Verify its persisted lockout trigger "
    "conditions and existing inactive-OFF configuration before claiming "
    "that a second controller is safe. Historical OFF commands confirm "
    "a command issuer, not the configured delay or absence of conflicts."
)


def calibrate_rule_design_review(message: str, receipts: list[dict[str, Any]]) -> str:
    """Preserve findings, remove specific unfounded absolutes, append caveats."""
    text = str(message or "")
    # A future *native action capability* receipt may be introduced later.
    # Today the available generic tool-guide/config receipts do NOT prove the
    # complete compiled rule topology, and should never suppress this gate.
    evidence_validates_compiler = any(
        row.get("success") is True
        and row.get("evidence_kind") == "typed_native_rule_design_schema"
        and isinstance(row.get("details"), dict)
        and row["details"].get("completeCombinedSemanticsVerified") is True
        for row in receipts if isinstance(row, dict)
    )
    if evidence_validates_compiler:
        return text
    text = _UNSUPPORTED_CREATION.sub(
        "the documented Rule Machine gateway only after a separate, validated "
        "native write proposal is explicitly authorised", text,
    )
    text = _ALL_REQUIRED.sub(
        "The current evidence does not verify whether `hub_set_rule` "
        "supports all required combined components", text,
    )
    text = _MIDNIGHT_CERTAINTY.sub(
        "The installed Rule Machine's cross-midnight condition semantics "
        "still require source/schema verification", text,
    )
    text = _LOCKOUT_CERTAINTY.sub(
        "its effect on the existing manual-off lockout is not verified", text,
    )
    text = _LOCKOUT_ABSOLUTE.sub(
        "it cannot be assumed to be independent of the existing lockout", text,
    )
    if "### Rule design feasibility gate (read-only)" not in text:
        text += _SAFETY_NOTE
    return text


__all__ = ["calibrate_rule_design_review"]

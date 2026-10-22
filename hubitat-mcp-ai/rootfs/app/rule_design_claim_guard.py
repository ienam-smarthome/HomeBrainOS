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

# A disclaimer appended after an unsafe, allegedly executable sequence is
# insufficient: users can follow the uncorrected earlier instructions. Replace
# known plan/write sections as a whole, preserving independent device and
# existing-controller findings (with their own evidence qualification).
_PLAN_SECTION = re.compile(
    r"^###\s*(?:\d+[.)]\s*)?(?:Proposed\s+(?:Implementation\s+Plan|"
    r"Rule\s+Machine\s+Implementation|RM\s+Implementation)|"
    r"Logic\s+Specification)\b[^\n]*\n.*?(?=^###\s+|\Z)",
    re.I | re.M | re.S,
)
_WRITER_SECTION = re.compile(
    r"^###\s*(?:\d+[.)]\s*)?(?:Technical\s+Feasibility"
    r"(?:\s*[&/]\s*Verification)?|Can\s+(?:my\s+)?"
    r"(?:native\s+)?tools\s+create)\b[^\n]*\n.*?(?=^###\s+|\Z)",
    re.I | re.M | re.S,
)


def _safe_plan(request: str) -> str:
    # Source of timings is solely the current user request, never an inferred
    # device state or an allegedly decoded unsupported native action.
    match = re.search(
        r"\bbetween\s+(\d{1,2}:\d{2})\s+(?:and|to)\s+"
        r"(\d{1,2}:\d{2})\b", request, re.I,
    )
    window = (
        f"{match.group(1)}–{match.group(2)}" if match
        else "the user-specified time window"
    )
    duration = re.search(
        r"\b(?:continuously\s+|for\s+|remained\s+inactive\s+"
        r"(?:continuously\s+)?for\s+)(\d+)\s*(minutes?|mins?)\b",
        request, re.I,
    )
    if duration is None:
        duration = re.search(r"\b(\d+)\s*(minutes?|mins?)\b", request, re.I)
    idle = f"{duration.group(1)} minutes" if duration else "the requested duration"
    return (
        "### 3. Proposed rule behaviour — design only, NOT executable Rule Machine actions\n"
        "The following is a **requirements-level design**, not a verified "
        "native action sequence or approved write payload. The correct "
        "motion sensor must be confirmed first.\n\n"
        f"1. Enforce the requested window **{window}** at entry **and immediately "
        "before every OFF**; verify how the installed Rule Machine interprets "
        "the crossing-midnight range. The installed Rule Machine's "
        "cross-midnight condition semantics still require source/schema "
        "verification.\n"
        "2. Consider three entry events: motion becomes inactive, the light "
        "turns ON while motion is already inactive, and the window opens "
        "while the light is already ON and motion inactive.\n"
        f"3. Track **{idle} of uninterrupted inactivity** while the light is ON. "
        "Motion active must invalidate the pending OFF and restart the full "
        "inactivity interval on the next eligible inactivity event. "
        "Light-OFF and window-close must also invalidate pending OFF work.\n"
        "4. Immediately before sending OFF, independently check that the "
        "time remains in the allowed window, light is ON, sensor inactive, "
        "and the complete uninterrupted interval is satisfied. Never send ON.\n"
        "5. Compare existing rules that already switch this light OFF. "
        "A second longer-delay rule may be ineffective if the existing "
        "controller sends OFF sooner. Confirm the manual-off lockout "
        "trigger policy rather than assuming OFF-only guarantees safety.\n\n"
        "A verified Rule Machine *duration-based expression* or correctly "
        "cancellable timer might implement this, but neither specific "
        "native encoding nor event cancellation is established by the "
        "current evidence. In particular, **Wait for Event: motion active "
        "with a timeout** is not proof of continuous inactivity: it can "
        "complete on the event **or** on timeout.\n\n"
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
    "of the existing controller's manual-off lockout. Verify the persisted "
    "lockout trigger "
    "conditions and existing inactive-OFF configuration before claiming "
    "that a second controller is safe. Historical OFF commands confirm "
    "a command issuer, not the configured delay or absence of conflicts."
)


def calibrate_rule_design_review(
    message: str, receipts: list[dict[str, Any]], *, request: str = ""
) -> str:
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
    # Replace the unsafe native plan itself. A correct caution appended after
    # an incorrect IF/WAIT/OFF recipe would still leave contradictory advice.
    text, _ = _PLAN_SECTION.subn(lambda _m: _safe_plan(request), text)
    text, _ = _WRITER_SECTION.subn(
        "### 4. Native implementation feasibility\n"
        "The current evidence does not verify whether `hub_set_rule` supports "
        "the required combined trigger, duration, cancellation and final "
        "time-guard semantics. No native write payload or pending confirmation "
        "can be justified by this review.\n\n", text,
    )
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
    # The normal evidence receipt often exposes only a list of response
    # field names, not the actual labelled device/settings values. Source
    # success alone cannot certify a displayed room, delay or lockout mode.
    # Preserve the model's observations as leads, not independently proven
    # facts, until typed, sanitized semantic receipts are available.
    typed_details_verified = any(
        row.get("success") is True
        and row.get("evidence_kind") == "typed_rule_design_facts"
        and isinstance(row.get("details"), dict)
        and row["details"].get("semanticFieldsValidated") is True
        for row in receipts if isinstance(row, dict)
    )
    provenance = (
        "**Evidence qualification:** Current device and app pages were "
        "queried, but generic receipts listing response fields do not "
        "independently certify their labels, rooms, current inactivity "
        "duration, complete actions or lockout trigger settings. These "
        "reported interpretations require typed source confirmation "
        "before any new rule is authorised.\n\n"
    )
    if not typed_details_verified and "**Evidence qualification:**" not in text:
        # Keep the existing review/no-write banner as the first line.
        leading = re.match(
            r"\A(\*\*Read-only[^\n]*\*\*\s*)", text, re.I,
        )
        if leading:
            index = leading.end()
            text = text[:index] + provenance + text[index:]
        else:
            text = provenance + text
    if "### Rule design feasibility gate (read-only)" not in text:
        text += _SAFETY_NOTE
    return text


__all__ = ["calibrate_rule_design_review"]

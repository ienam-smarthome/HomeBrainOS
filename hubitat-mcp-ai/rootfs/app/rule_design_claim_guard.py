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


# Unverified native writer contracts cannot become executable JSON by adding
# a caution after an otherwise actionable request.
_SCHEMA_HEADING = re.compile(
    r"^###\s*(?:\d+[.)]\s*)?(?:Upstream[- ]Tested Facts|"
    r"Native(?: Rule Machine)? Contract Validation)\b[^\n]*\n"
    r".*?(?=^###\s+|\Z)", re.I | re.M | re.S,
)
_READY_HEADING = re.compile(
    r"^###\s*(?:\d+[.)]\s*)?Readiness Assessment\b[^\n]*\n"
    r".*?(?=^###\s+|\Z)", re.I | re.M | re.S,
)
_INSTALLED_HEADING = re.compile(
    r"^###\s*(?:\d+[.)]\s*)?Installed[- ]Hub Observations\b[^\n]*\n"
    r".*?(?=^###\s+|\Z)", re.I | re.M | re.S,
)
_JSON_CODE = re.compile(r"(?ms)^\x60{3}json\s*\n.*?^\x60{3}\s*$")


def _source_operation(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    args = row.get("arguments")
    tool = row.get("sub_tool")
    if not isinstance(args, dict):
        args = {}
    if tool is None:
        tool = args.get("tool") or row.get("tool")
    if isinstance(args.get("args"), dict):
        args = args["args"]
    return str(tool or ""), args


def _targeted_sources(receipts: list[dict[str, Any]]) -> tuple[bool, bool]:
    device = app = False
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True:
            continue
        tool, args = _source_operation(row)
        device |= tool == "hub_get_device" and bool(
            args.get("deviceId") or args.get("device_id")
        )
        app |= tool == "hub_get_app_config" and bool(
            args.get("appId") or args.get("app_id")
        ) and args.get("summary") is not True
    return device, app


def _strip_unverified_json(match: re.Match[str]) -> str:
    code = match.group(0)
    if re.search(r'"operation"\s*:\s*"(?:create|update|form|delete)"', code, re.I):
        return (
            "**Native write JSON withheld:** No current typed source receipt "
            "establishes the installed trigger/action encoding. Obtain "
            "independent schema evidence and separate authorisation."
        )
    return code


def _motion_scope(request: str, answer: str) -> bool:
    # Explicit negative instructions such as "do not include motion or
    # lockout guidance" must not *activate* those unrelated safety notes.
    # Scope is the request when present, not any previous generated answer.
    scope = request if request.strip() else answer
    for clause in re.split(r"[.!?;\n]+", scope):
        if re.match(
            r"(?i)^\s*(?:do\s+not|don't|never|without|exclude|avoid|"
            r"no\s+(?:motion|lockout|lighting))\b", clause,
        ):
            continue
        if re.search(
            r"(?i)\b(?:motion|inactive|inactivity|lockout|"
            r"light(?:s)?\b[^\n]{0,60}\boff)\b", clause,
        ):
            return True
    return False



# Contract-only reviews must never turn model-described guide snippets into
# source-certified native fields. Generic guide receipts do not include a
# typed field attestation, even when a model has read guide prose.
_GUIDE_ACKNOWLEDGEMENT = re.compile(
    r"(?i)I-HAVE-READ-THE-GUIDE-[A-Za-z0-9_.-]+"
)

_NATIVE_CONTRACT_SAFETY_NOTE = (
    "\n\n### Rule design feasibility gate (read-only)\n"
    "**Native authoring readiness is unverified.** The current receipts "
    "do not attest the exact dated-trigger field schema, calendar-year "
    "handling, log-action encoding or scheduler registration/firing. "
    "Guide descriptions are not installed-runtime proof. No executable "
    "payload, mutation readiness or confirmation is authorised by this review."
)


def _calibrate_native_contract_table(message: str) -> str:
    """Demote unsupported table certainty without inventing field schemas."""
    out = []
    for line in message.splitlines(keepends=True):
        if not line.lstrip().startswith("|"):
            out.append(line)
            continue
        cells = line.rstrip("\n").split("|")
        if len(cells) < 5:
            out.append(line)
            continue
        status = cells[2].strip().strip("*" + chr(96)).casefold()
        if status in ("verified", "fully verified", "confirmed", "proven"):
            cells[2] = " Not source-verified "
        # A numbered form-field placeholder is not a calendar-year field.
        label = cells[1].casefold()
        if re.search(r"\byear(?:\s*#|[ -]?field|[ -]?handling)?\b", label):
            cells[2] = " Unverified "
            cells[3] = (
                " No source-attested dated-trigger year key or year semantics; "
                "a numbered form-field placeholder does not establish this. "
            )
        elif re.search(r"date\s*(?:/|and)\s*time\s*format", label):
            cells[2] = " Unverified "
            cells[3] = (
                " A variable timestamp example does not establish the "
                "dated-trigger field encoding or timezone semantics. "
            )
        elif re.search(r"scheduler|schedul(?:ing|er)?\s+verif", label):
            cells[2] = " Unverified "
            cells[3] = (
                " No source-attested scheduler registration or actual "
                "trigger firing was observed. "
            )
        elif re.search(r"\bparent\s+id\b", label):
            cells[3] = (
                " The guide may require a parent ID; the installed parent "
                "identity was not attested in this review. "
            )
        elif re.search(r"\bbackup\b", label):
            cells[3] = (
                " Backup requirements may be guide-described; no current "
                "installed-hub backup was verified in this review. "
            )
        out.append("|".join(cells) + ("\n" if line.endswith("\n") else ""))
    return "".join(out)


def _calibrate_unverified_native_contract(message: str) -> str:
    """Restrict a contract review to the evidence actually in receipts."""
    text = _calibrate_native_contract_table(message)
    text = re.sub(
        r"(?im)^-\s*\*\*Upstream[- ]Tested Facts\*\*:[^\n]*",
        "- **Documentation vs upstream tests:** Guide-access receipts are "
        "not evidence that upstream integration tests validated these exact "
        "dated-trigger fields or action semantics.",
        text,
    )
    text = re.sub(
        r"(?im)^(-\s*\*\*Evidence Complete\*\*:\s*)[^\n]*",
        r"\g<1>No — the required typed native contract was not source-attested.",
        text,
    )
    text = re.sub(
        r"(?im)^(-\s*\*\*Readiness for Mutation\*\*:\s*)[^\n]*",
        r"\g<1>NOT READY (readinessForMutation=false).",
        text,
    )
    # A JSON sketch of trigger/action properties can be mistaken for an
    # authorized encoding; retain a minimal evidence-only technical result.
    def replace_contract_json(match: re.Match[str]) -> str:
        block = match.group(0)
        if not re.search(
            r'"(?:authoring_contract|structural_types|write_requirements)"\s*:',
            block, re.I,
        ):
            return block
        fence = chr(96) * 3
        return (
            fence + 'json\n'
            '{\n  "reviewDomain": "rule_design_review",\n'
            '  "evidenceComplete": false,\n'
            '  "typed_authoring_contract": "checked-unverified",\n'
            '  "readinessForMutation": false\n'
            '}\n' + fence
        )
    return _JSON_CODE.sub(replace_contract_json, text)


_GENERIC_SAFETY_NOTE = (
    "\n\n### Rule design feasibility gate (read-only)\n"
    "**Native rule creation is not yet validated.** An inventory and a "
    "read-only guide acknowledgment do not establish an installed "
    "trigger/action field schema or safe executable payload. Confirm "
    "the precise types, time zone, parent ID, backup, guide key and "
    "isolated action before separately authorising a test. Verify "
    "persistence and scheduled jobs after creation, then separately "
    "verify actual firing. No changes are authorised by this review."
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
    # Guide acknowledgements are request-local credentials, never suitable
    # for publication (including in Technical JSON). Preserve the fact that
    # a key is required, not its actual value.
    text = _GUIDE_ACKNOWLEDGEMENT.sub("[redacted-guide-key]", text)
    from targeted_rule_scope_policy import is_native_rule_contract_review_request
    native_contract_review = is_native_rule_contract_review_request(request)
    if evidence_validates_compiler:
        return text
    if native_contract_review:
        text = _calibrate_unverified_native_contract(text)
    # A model's "upstream-tested facts" and READY conclusion are not
    # substitutes for a typed, source-attested native operation contract.
    text, _ = _SCHEMA_HEADING.subn(
        "### Native authoring schema — unverified\n"
        "The current read receipts do not certify typed trigger/action "
        "fields, date/time formats, optional year conditions or native "
        "runtime semantics. Treat any model-reported format as unverified.\n\n",
        text,
    )
    text, _ = _READY_HEADING.subn(
        "### Readiness assessment — unverified\n"
        "The native authoring contract is not source-verified, so this "
        "proposal is NOT READY for an executable test and no rule "
        "creation is authorised.\n\n",
        text,
    )
    text = _JSON_CODE.sub(_strip_unverified_json, text)
    # Standalone positive READY claims are also unsupported.
    text = re.sub(
        r"(?im)^[^\n]*(?:\bplan\b[^\n]{0,80}\bREADY\b|"
        r"\bREADY\b[^\n]{0,80}\bfor\b[^\n]{0,80}"
        r"\b(?:test|creation|implementation)\b)[^\n]*$",
        lambda m: m.group(0) if re.search(
            r"(?i)\b(?:not|unverified|never)\s+ready\b",
            m.group(0),
        ) else "**Readiness unverified: no authorised native write.**",
        text,
    )
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
    device_read, app_read = _targeted_sources(receipts)
    if not device_read and not app_read:
        text, _ = _INSTALLED_HEADING.subn(
            "### Installed-hub evidence — limited to recorded reads\n"
            "The current receipts record no targeted device or complete "
            "app-configuration reads. Inventory and tool-guide calls alone "
            "cannot verify hub time zone, settings, device identity or "
            "native authoring schema.\n\n", text,
        )
    guide_checked = any(
        row.get("success") is True and _source_operation(row)[0] == "hub_get_tool_guide"
        for row in receipts if isinstance(row, dict)
    )
    provenance = (
        "**Evidence qualification:** "
        + (
            "This is a native authoring-contract review, not a device or "
            "installed-rule configuration audit. "
            + ("Guide access was recorded, " if guide_checked else
               "No successful guide read was recorded, ")
            + "but typed dated-trigger/action field proof and scheduler "
            "execution are not source-attested by the receipts. "
            if native_contract_review else
            "Targeted device and app configuration reads were recorded, "
            "but generic field-name receipts cannot prove their "
            "semantics or a complete native writer schema."
            if device_read and app_read else
            "The read receipts did not verify both targeted device and "
            "complete app-configuration sources. An inventory or guide "
            "read alone does not establish the current rule settings, "
            "hub time zone or native authoring contract."
        )
        + " Typed source confirmation is required before any new rule "
          "is authorised.\n\n"
    )
    if native_contract_review:
        # Model prose can already contain a generic controller/device
        # disclaimer. Replace it rather than leaving an irrelevant warning
        # in a contract-only review.
        text = re.sub(
            r"(?m)^\*\*Evidence qualification:\*\*[^\n]*(?:\n(?!\n)[^\n]*)*",
            lambda _match: provenance.strip(),
            text, count=1,
        )
        text = re.sub(
            r"(?ms)^### Rule design feasibility gate \(read-only\)\n.*?"
            r"(?=^### |\Z)",
            lambda _match: _NATIVE_CONTRACT_SAFETY_NOTE.strip() + "\n",
            text,
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
        text += (_NATIVE_CONTRACT_SAFETY_NOTE if native_contract_review
                 else _SAFETY_NOTE if _motion_scope(request, text)
                 else _GENERIC_SAFETY_NOTE)
    return text


__all__ = ["calibrate_rule_design_review"]

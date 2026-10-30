"""Source-grounded terminal reconciliation for incomplete historical evidence.

Preserves the original model-led investigator. At publication, if verified
command and switch observations contradict its answer, this module publishes
one truthful evidence-led explanation instead of appending a second timeline
to an uncorrected false first paragraph. No MCP tools, writes, or invented
device histories are involved.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping


def _clock(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc).strftime("%H:%M:%S") if result.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def source_contradiction_flags(text: str, facts: Mapping[str, Any]) -> list[str]:
    """Check mutually exclusive facts, not just word 'routing' signals."""
    coverage = facts.get("target_coverage", [])
    if not isinstance(coverage, list):
        return []
    message = str(text or "")
    off_commands = any(c.get("issued_off", 0) for c in coverage)
    off_states = any(c.get("reported_switch_off", 0) for c in coverage)
    gap = bool(facts.get("missing_switch_history_for_targets"))
    flags = []
    if (off_commands or off_states) and re.search(
        r"(?is)\b(?:no|none|zero)\b.{0,110}"
        r"\b(?:off\s+commands?|off\s+states?|off\s+transitions?)\b",
        message,
    ):
        flags.append("off_evidence_denied")
    if off_commands and re.search(
        r"(?is)\ball\b.{0,60}\blight events\b.{0,55}\bsetLevel\b", message
    ):
        flags.append("issued_off_commands_omitted")
    if gap and re.search(
        r"(?is)\b(?:activations? (?:were|was) driven by|"
        r"(?:lights?|shower|bathroom).{0,75}(?:were|was) activated by|"
        r"\bconfirmed\b.{0,75}\bactivat)",
        message,
    ):
        flags.append("initiator_claim_without_switch_history")
    if gap and re.search(
        r"(?is)\b(?:physical confirmation|complete (?:on|off) cycles?)\b",
        message,
    ):
        flags.append("physical_confirmation_not_attested")
    return flags


def verified_incident_ledger(facts: Mapping[str, Any]) -> str:
    """All observed target command, switch and level rows, with exact labels."""
    labels = {
        "reported_switch_on": ("Reported switch", "ON"),
        "reported_switch_off": ("Reported switch", "OFF"),
        "issued_on": ("Issued command", "on()"),
        "issued_off": ("Issued command", "off()"),
        "issued_setlevel": ("Issued command", "setLevel(...)"),
        "reported_level": ("Reported level", "level"),
    }
    entries = facts.get("incident_ledger") or []
    rendered = []
    for record in entries[:75]:
        if not isinstance(record, Mapping):
            continue
        kind = record.get("event_class")
        if kind not in labels:
            continue
        time = _clock(record.get("date"))
        if time is None:
            continue
        label, change = labels[kind]
        if kind == "reported_level":
            change = "level " + str(record.get("value") or "")[:20]
        name = str(record.get("device_name") or "Target").replace("|", "/")[:70]
        actor = ("App " + str(record["app_id"])
                 if record.get("app_id") else "Device report; initiating source unverified")
        rendered.append("| " + time + " | " + name + " | " + label
                        + " | " + change + " | " + actor + " |")
    if not rendered:
        return ""
    missing = facts.get("missing_switch_history_for_targets") or []
    caveat = (
        "\n\n**Incomplete switch-state coverage:** " + ", ".join(missing)
        + " had commands and/or levels in the returned histories, but "
          "no switch ON/OFF transition reports. Those command records "
          "cannot establish actual ON/OFF cycles."
        if missing else ""
    )
    more = int(facts.get("incident_ledger_total") or 0) - len(rendered)
    return (
        "### Verified incident ledger\n\n"
        "These are individually source-attested, time-ordered records in UTC; "
        "issued commands are not physical state confirmations.\n\n"
        "| UTC | Light | Evidence type | Event | Provenance |\n"
        "|---|---|---|---|---|\n" + "\n".join(rendered)
        + caveat
        + ("\n\n" + str(more) + " more entries are omitted by the display "
           "limit." if more > 0 else "")
    )


def source_first_explanation(facts: Mapping[str, Any]) -> str:
    coverage = facts.get("target_coverage") or []
    off_commands = [c["device_name"] for c in coverage if c.get("issued_off")]
    off_states = [c["device_name"] for c in coverage if c.get("reported_switch_off")]
    on_states = [c["device_name"] for c in coverage if c.get("reported_switch_on")]
    gap = facts.get("missing_switch_history_for_targets") or []
    passages = [
        "**What the evidence actually establishes:** "
        "The returned Hubitat evidence separates commands issued by apps "
        "from switch-state reports and brightness-level observations."
    ]
    if off_commands:
        passages.append(
            "**OFF commands were recorded** for " + ", ".join(off_commands)
            + ". An issued command proves the app requested OFF, not that "
              "physical actuation was independently verified.")
    if off_states:
        passages.append(
            "**OFF switch reports were recorded** for " + ", ".join(off_states)
            + ". It is incorrect to say that no OFF transitions occurred "
              "in the returned data.")
    if on_states:
        passages.append(
            "**ON switch reports were recorded** for " + ", ".join(on_states)
            + ". A later setLevel changes or reapplies brightness; it "
              "cannot have initiated an already-reported ON.")
    if gap:
        passages.append(
            "**Missing historical evidence:** " + ", ".join(gap)
            + " returned commands and levels but no switch ON/OFF "
              "transition records in this retrieval. An independently "
              "scoped switch-only read or retained incident-time logs "
              "are required to establish those cycles.")
    passages.append(
        "**Cause is not fully verified:** Current automation source code "
        "shows possible behaviour, not historical execution. Motion events "
        "close to a light change are correlations, not proof of the "
        "initiating automation. A bridge reporting an event is not "
        "necessarily the external controller that caused it.")
    return "\n\n".join(passages)


def reconcile_ledger_if_needed(
    original: str, facts: Mapping[str, Any],
) -> tuple[str, bool]:
    """Replace contradictory answers; never stack contradicting timelines."""
    gaps = bool(facts.get("missing_switch_history_for_targets"))
    flags = source_contradiction_flags(original, facts)
    if not gaps and not flags:
        return original, False
    timeline = verified_incident_ledger(facts)
    if not timeline:
        return original, False
    return source_first_explanation(facts) + "\n\n" + timeline, True


__all__ = [
    "source_contradiction_flags", "verified_incident_ledger",
    "source_first_explanation", "reconcile_ledger_if_needed",
]

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

from unified_incident_digest import source_incident_digest
from causal_claim_publication import claim_guided_incident_answer
from causal_claim_attestation import (
    extract_claim_envelope, validate_claim_envelope,
)


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
        "journal_source_switch_on": ("Journal source-timed switch", "ON"),
        "journal_source_switch_off": ("Journal source-timed switch", "OFF"),
        "journal_received_switch_on": ("Journal collector-received switch", "ON"),
        "journal_received_switch_off": ("Journal collector-received switch", "OFF"),
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
        actor = ("Historical Journal (" + (
            "source timestamp" if record.get("timestamp_basis") == "source"
            else "collector reception only") + "; initiator unverified)"
            if kind.startswith("journal_") else
            ("App " + str(record["app_id"])
             if record.get("app_id") else
             "Device report; initiating source unverified"))
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
        "issued commands are not physical state confirmations. Journal "
        "collector-reception timestamps do not establish exact physical "
        "event order or original-source timestamps.\n\n"
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
    archive_source = int(facts.get("journal_source_observations") or 0)
    archive_received = int(facts.get("journal_collector_observations") or 0)
    if archive_source or archive_received:
        passages.append(
            "**Historical Journal fallback checked:** "
            + (str(archive_source) + " source-timestamped switch observation(s); ")
            + (str(archive_received) + " collector-received switch observation(s). ")
            + "Collector-received events cannot be used as exact historical "
              "switch times or proof of who initiated a change. "
              "The journal may have recorded connection gaps."
        )
    if gap:
        passages.append(
            "**Missing historical evidence:** " + ", ".join(gap)
            + " returned commands and levels but no switch ON/OFF "
              "transition records in the *live Hubitat pages*. "
              "A journal observation is independently reported, but does "
              "not make the incomplete live history complete. The exact "
              "initiating controller remains unverified; the initiating controller "
              "cannot be conclusively identified without incident-time "
              "app logs or external automation traces may be required.")
    passages.append(
        "**Cause is not fully verified:** Current automation source code "
        "shows possible behaviour, not historical execution. Motion events "
        "close to a light change are correlations, not proof of the "
        "initiating automation. A bridge reporting an event is not "
        "necessarily the external controller that caused it.")
    return "\n\n".join(passages)



def publication_shadow_assessment(
    draft: str, facts: Mapping[str, Any],
) -> dict[str, int | bool]:
    """Measure draft coverage; never approve claims or publish raw draft text.

    A timestamp token is NOT a witness citation. This diagnostic only
    compares aggregate source-clock tokens and counts contradiction flags.
    No names, event timestamps, app logs or model text enter telemetry.
    """
    source_times: set[str] = set()
    for row in (facts.get("incident_ledger") or [])[:200]:
        if (not isinstance(row, Mapping)
                or str(row.get("event_class") or "") not in (
                    "journal_source_switch_on", "journal_source_switch_off",
                    "reported_switch_on", "reported_switch_off")):
            continue
        clock = _clock(row.get("date"))
        if clock:
            source_times.add(clock)
    text = str(draft or "")
    matches = sum(
        1 for clock in source_times
        if re.search(r"(?<!\d)" + re.escape(clock) + r"(?!\d)", text)
    )
    return {
        "source_time_tokens_available": min(len(source_times), 200),
        "source_time_tokens_mentioned": matches,
        "draft_mentions_source_time": bool(matches),
        "source_contradiction_flag_count": len(
            source_contradiction_flags(text, facts)),
        "native_history_gap": bool(
            facts.get("missing_switch_history_for_targets")),
        "journal_switch_source_available": bool(
            facts.get("journal_source_observations")),
    }


def _record_publication_shadow(
    draft: str, facts: Mapping[str, Any], action: str,
) -> None:
    """Record only allowlisted request counters. No model text retained."""
    from request_metrics import increment_active_metric

    analysis = publication_shadow_assessment(draft, facts)
    increment_active_metric("v3_shadow_publications_seen")
    actions = {
        "claim_guided": "v3_claim_guided_publications",
        "digest": "v3_shadow_legacy_digest_replaced",
        "ledger": "v3_shadow_legacy_ledger_replaced",
        "preserved": "v3_shadow_legacy_draft_preserved",
    }
    increment_active_metric(actions[action])
    # The witness ledger is shadow-only. Expose aggregate source-role
    # coverage while preserving the exact legacy final-answer decision.
    # observe_counter_max keeps the counters stable if multiple candidate
    # explanations pass through the finalization boundary.
    ledger = facts.get("v3_witness_ledger")
    if isinstance(ledger, Mapping):
        from request_metrics import observe_active_metric_max
        observe_active_metric_max(
            "v3_witness_total", int(ledger.get("witness_total") or 0))
        observe_active_metric_max(
            "v3_witness_source_inputs",
            int(ledger.get("source_timed_input_witness_count") or 0))
        observe_active_metric_max(
            "v3_witness_immediate_command_matches",
            len(ledger.get("immediate_hubitat_on_command_matches") or []))
        observe_active_metric_max(
            "v3_witness_targets_without_on_issuer",
            max(0, int(ledger.get("target_count") or 0)
                - int(ledger.get("issuer_verified_target_count") or 0)))
    # Shadow attestations never approve arbitrary prose and do not affect
    # the existing digest/ledger publication choice.
    if isinstance(ledger, Mapping):
        attestation = extract_claim_envelope(draft)
        if attestation is None:
            increment_active_metric("v3_claim_envelope_missing")
        else:
            result = validate_claim_envelope(attestation, ledger)
            increment_active_metric("v3_claim_envelope_present")
            if result["valid"]:
                increment_active_metric("v3_claim_envelope_valid")
            else:
                increment_active_metric("v3_claim_envelope_invalid")
            if result["supported"]:
                increment_active_metric(
                    "v3_claim_supported", min(32, result["supported"]))
            if result["rejected"]:
                increment_active_metric(
                    "v3_claim_rejected", min(32, result["rejected"]))
            # Telemetry may report allowlisted validation *categories*,
            # never model text, event IDs, times, or witness identifiers.
            allowed_reasons = {
                "malformed_envelope", "unknown_claim_kind", "missing_witness",
                "wrong_witness_role", "target_mismatch", "state_mismatch",
                "app_mismatch", "clock_unverified",
                "command_pair_not_attested", "unknown_target",
                "unsupported_unverified_claim", "claim_limit_exceeded",
            }
            for reason in result.get("reasons") or []:
                if reason in allowed_reasons:
                    increment_active_metric("v3_claim_reason_" + reason)
    if analysis["native_history_gap"]:
        increment_active_metric("v3_shadow_history_gap")
    if analysis["source_contradiction_flag_count"]:
        increment_active_metric("v3_shadow_draft_contradiction")
    if analysis["draft_mentions_source_time"]:
        increment_active_metric("v3_shadow_draft_mentions_source_time")
    if analysis["source_time_tokens_mentioned"]:
        increment_active_metric(
            "v3_shadow_source_time_token_matches",
            int(analysis["source_time_tokens_mentioned"]),
        )

def reconcile_ledger_if_needed(
    original: str, facts: Mapping[str, Any],
) -> tuple[str, bool]:
    """Replace contradictory answers; never stack contradicting timelines."""
    gaps = bool(facts.get("missing_switch_history_for_targets"))
    flags = source_contradiction_flags(original, facts)
    # Earlier versions always printed the raw 60+ row technical journal
    # ledger after recovering events. Source-attested switch observations
    # now support a concise, deduplicated, causal-first digest. This is
    # still the original agent's final safety boundary, not a V2 planner.
    if gaps and int(facts.get("journal_source_observations") or 0) > 0:
        # Publication uses selected *validated* witness claims to choose
        # evidence-backed natural paragraphs. NEVER publish raw model prose:
        # witness attestation does not semantically validate free text.
        natural, status = claim_guided_incident_answer(original, facts)
        if natural is not None:
            _record_publication_shadow(original, facts, "claim_guided")
            return natural, True
        if status != "not_eligible":
            from request_metrics import increment_active_metric
            increment_active_metric("v3_claim_guided_fallback")
        digest = source_incident_digest(facts)
        if digest:
            _record_publication_shadow(original, facts, "digest")
            return digest, True
    if not gaps and not flags:
        _record_publication_shadow(original, facts, "preserved")
        return original, False
    timeline = verified_incident_ledger(facts)
    if not timeline:
        _record_publication_shadow(original, facts, "preserved")
        return original, False
    _record_publication_shadow(original, facts, "ledger")
    return source_first_explanation(facts) + "\n\n" + timeline, True


__all__ = [
    "source_contradiction_flags", "verified_incident_ledger",
    "source_first_explanation", "reconcile_ledger_if_needed",
    "publication_shadow_assessment",
]

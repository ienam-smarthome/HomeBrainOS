"""One bounded shadow claim-attestation prompt, regardless of evidence arrival order.

The original model may first see empty native history, then see recovered
Historical Journal source-time rows via the cross-source checkpoint. Both
prompt paths must offer the SAME versioned claim contract only if the current
verified facts permit the legacy two-target digest fallback.

This module never calls MCP, modifies devices, or validates narrative prose.
"""
from __future__ import annotations

import json
from typing import Any, Mapping


def render_shadow_claim_pilot(
    facts: Mapping[str, Any] | None, *, final_synthesis: bool = False,
) -> str:
    if not isinstance(facts, Mapping):
        return ""
    ledger = facts.get("v3_witness_ledger")
    if not isinstance(ledger, Mapping):
        return ""
    if (not facts.get("missing_switch_history_for_targets")
            or ledger.get("schema") != "causal-witness-ledger.v1"):
        return ""
    source_ids = {
        str(w.get("entity") or "")
        for w in (ledger.get("witnesses") or [])[:200]
        if isinstance(w, Mapping)
        and w.get("event_class") in (
            "journal_source_switch_on", "journal_source_switch_off")
        and w.get("clock_basis") == "source"
    }
    if len(source_ids) < 2:
        return ""
    # Show paired positive/negative cases for *each* queried target, rather
    # than 18 chronological rows from only one busy light. An example must
    # always be a genuine witness in the current request.
    examples: list[dict[str, Any]] = []
    for target in sorted(source_ids, key=lambda x: int(x) if x.isdecimal() else 0)[:4]:
        picked = [
            w for w in (ledger.get("witnesses") or [])
            if isinstance(w, Mapping) and str(w.get("entity")) == target
            and w.get("event_class") in (
                "journal_source_switch_on", "journal_source_switch_off",
                "issued_on", "issued_off", "issued_setlevel")
        ]
        for row in picked[:3]:
            examples.append({
                "id": row["witness_id"], "device_id": row["entity"],
                "event_class": row["event_class"], "clock_basis":
                    row["clock_basis"],
            })
    if not examples:
        return ""
    sample = {
        "schema": "homebrain-claims.v1",
        "claims": [
            {"kind": "reported_switch_state",
             "device_id": examples[0]["device_id"], "state": (
                 "on" if examples[0]["event_class"].endswith("_on") else "off"),
             "witness_ids": [examples[0]["id"]]},
        ],
    }
    # Final synthesis receives the same source-qualified witness IDs as the
    # earlier optional discovery checkpoint. Unlike the optional pilot, this
    # last instruction explicitly requests the envelope after natural prose.
    # This changes no validation or publication authority.
    preamble = (
        "\nHOST FINAL-SYNTHESIS SHADOW CLAIM ATTESTATION (research diagnostic "
        if final_synthesis
        else "\nHOST OPTIONAL SHADOW CLAIM ATTESTATION (research diagnostic "
    )
    directive = (
        "After your natural-language explanation, append exactly one "
        if final_synthesis
        else "Once you finish the read-only investigation, you MAY append one "
    )
    return (
        preamble
        + "ONLY, legacy safety digest will still control publication): "
        + directive
        + "fenced code block with language homebrain-claims containing JSON "
          "schema homebrain-claims.v1 and at most 8 typed claims. "
          "Use only provided verified witness IDs and exact device IDs. "
          "Supported: reported_switch_state (state on/off, 1 matching source "
          "witness), hubitat_issued_command (command on/off/setlevel, app_id, "
          "1 matching command witness), matched_hubitat_on_command "
          "(only a recorded issued_on + matching ON state pair), and "
          "upstream_cause_unverified (0 witnesses). "
          "Missing history, a later setLevel, a notified app and input "
          "reception cannot prove the original initiator. "
          "Do not perform extra tool calls to fill optional metadata. "
          "Natural-language reasoning comes first and remains subject to "
          "the existing safety finalizer. "
          "Witness examples: "
        + json.dumps(examples[:12], ensure_ascii=True,
                     separators=(",", ":"))[:1650]
        + " Example envelope: "
        + json.dumps(sample, ensure_ascii=True,
                     separators=(",", ":"))[:550]
    )


__all__ = ["render_shadow_claim_pilot"]

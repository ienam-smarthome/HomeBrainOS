"""Compare available incident hypotheses from independently scoped evidence.

This is for users explicitly requesting an alternatives comparison after a
fully source-derived two-target summary. Do not append speculative, model-
proposed checklists that have no independently verified discriminator.
"""
from __future__ import annotations

from typing import Any, Mapping


def source_based_competing_explanations(facts: Mapping[str, Any] | None) -> str | None:
    if not isinstance(facts, Mapping):
        return None
    receiver = facts.get("same_receiver_evidence")
    if not isinstance(receiver, Mapping):
        return None
    leader = next((
        x for x in receiver.get("candidates") or []
        if isinstance(x, Mapping)
        and x.get("one_to_one_within_windows") is True
        and x.get("receiver_clock_only") is True
        and x.get("initiator_verified") is False
    ), None)
    if leader is None:
        return None
    lead_id = str(leader.get("input_id") or "")
    candidates = [
        p for p in facts.get("archived_input_reception_patterns") or []
        if isinstance(p, Mapping)
        and str(p.get("device_id") or "") != lead_id
        and type(p.get("on_near_active_receptions")) is int
        and type(p.get("target_source_on_count")) is int
        and p.get("target_source_on_count") > 0
    ]
    parts = []
    if candidates:
        # These are the archive's source-vs-reception-window summaries,
        # NOT the same-collector clock comparison used for the strongest
        # lead. Never present them as calibrated event-order probabilities.
        strongest_alt = sorted(
            candidates,
            key=lambda x: (-x["on_near_active_receptions"],
                           str(x["device_id"]))
        )[0]
        ident = str(strongest_alt["device_id"])
        matched = strongest_alt["on_near_active_receptions"]
        total = strongest_alt["target_source_on_count"]
        sample = int(strongest_alt.get("input_reception_sample_size") or 0)
        coverage = next((
            x for x in facts.get("archived_input_sample_coverage") or []
            if isinstance(x, Mapping) and str(x.get("device_id")) == ident
        ), {})
        returned = coverage.get("retrieved_observations")
        truncated = strongest_alt.get("input_sample_truncated") is True
        parts.append(
            "Alternative input " + ident + " had " + str(matched) + "/"
            + str(total) + " nearby active receptions in the archive's "
              "mixed source/collector window, versus the complete "
            + str(leader["matched_on"]) + "/" + str(leader["target_on_rows"])
            + " same-collector reception pairing for input " + lead_id
              # No direct probability comparison: asymmetric clocks/windows.
            + ("; its retained sample has " + str(sample)
               + " of " + str(returned)
               + " returned rows, so incomplete coverage limits comparison"
               if truncated and type(returned) is int else
               "; its own source-event order remains unverified")
            + "."
        )
    parts.append(
        "An external bridge, manual interaction or hardware reset remains "
        "an alternative only; no independently matched initiating command "
        "or physical reset was established for the requested window. "
        "The sensor correlation is stronger evidence for a motion-related "
        "sequence, not for a specific issuing app."
    )
    return "**Alternatives assessed:** " + " ".join(parts)


__all__ = ["source_based_competing_explanations"]

"""Compare available incident hypotheses from independently scoped evidence.

This is for users explicitly requesting an alternatives comparison after a
fully source-derived two-target summary. Do not append speculative, model-
proposed checklists that have no independently verified discriminator.
"""
from __future__ import annotations

from typing import Any, Mapping

from causal_incident_narrative import verified_input_label


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
    leader_name = verified_input_label(facts, lead_id)
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
        alternative_name = verified_input_label(facts, ident)
        parts.append(
            "**Other sensors:** " + alternative_name
            + " had activity near " + str(matched) + " of the "
            + str(total) + " light-on events, compared with "
            + str(leader["matched_on"]) + " of "
            + str(leader["target_on_rows"]) + " for "
            + leader_name + "."
            + (" Only " + str(sample) + " of " + str(returned)
               + " archived observations were retained in the comparison, "
                 "so this alternative's history is incomplete."
               if truncated and type(returned) is int else
               " The timing evidence for this alternative is less complete.")
        )
    parts.append(
        "A manual switch, another automation or a bridge could still "
        "explain the original command, but none was verified in the "
        "available history."
    )
    return "**Other explanations considered:** " + " ".join(parts)


__all__ = ["source_based_competing_explanations"]

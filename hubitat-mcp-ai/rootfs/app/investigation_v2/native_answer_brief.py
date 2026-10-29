"""Bounded general-source briefing and evidence readiness for Native V2.

Model selects the MCP evidence reads; the host may produce a *short factual
brief* from independently verified claim-catalog entries if the model's final
claim-only response is absent or unsupported. Never publish LLM free prose,
rank physical fault hypotheses or equate stale activity with offline.

This is a source-class renderer, not a question-keyword router or replacement
for richer independently verified model reasoning in a later stage.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


# Broad, generic evidence-class ordering; no device, room, model, app or
# question-specific IDs/words. Unknown evidence types remain eligible.
_PRIORITY = (
    "health_sample_summary", "health_unknown_entry", "health_stale_entry",
    "app_dependency_reference", "command_issuer", "device_observation",
    "warning", "source_reported_warning", "hub_metric",
)
_CLASSES = {
    "health_sample_summary": "Device-health sample",
    "health_unknown_entry": "Unverified device activity",
    "health_stale_entry": "Stale device activity",
    "app_dependency_reference": "App and automation references",
    "device_observation": "Live reported state",
    "command_issuer": "Recorded command issuer",
    "warning": "Source-reported warning",
    "hub_metric": "Hub metrics",
}


def evidence_readiness(
    witnesses: Sequence[Mapping[str, Any]],
    catalog: Sequence[Mapping[str, Any]],
    *, stop_reason: str,
) -> dict[str, Any]:
    """Report a coverage proxy, NOT a semantic-accuracy or completeness score.

    Only after READ limits are reached and multiple independently verified
    source classes exist can a separate, typically 8-second, model-only
    claim selection be safely omitted. Other queries keep the model chance
    to finish naturally. Neither this proxy nor success count establishes
    that the user question was fully answered.
    """
    source_ops = {
        str(w.get("operation")) for w in witnesses[:16]
        if type(w.get("read")) is int and isinstance(w.get("source_data"), Mapping)
    }
    fact_kinds = {
        str(row.get("kind")) for row in catalog[:64]
        if row.get("root_cause_verified") is False
        and isinstance(row.get("statement"), str)
    }
    ready = (
        stop_reason in ("round_budget_reached", "read_budget_reached")
        and len(source_ops) >= 2
        and len(catalog) >= 3
        and len(fact_kinds) >= 2
    )
    return {
        "host_factual_brief_ready": ready,
        "distinct_verified_read_operations": len(source_ops),
        "distinct_verified_fact_kinds": len(fact_kinds),
        "verified_catalog_facts": len(catalog),
        "accuracy_or_v1_superiority_measured": False,
        "limitations": (
            "These are evidence-coverage and completion proxies, not "
            "answer relevance, reasoning correctness or proof of "
            "superiority to V1."),
    }


def evidence_brief(
    catalog: Sequence[Mapping[str, Any]],
    *, max_points: int = 6,
) -> str:
    """Short, independently receipt-backed lead for broad/source-rich answers.

    Use returned claim statements verbatim (already host-authorised), bounded
    and deduplicated across source *kinds*, not invented paraphrases. If the
    statement is not in the verified catalog it cannot enter the brief.
    """
    candidates = [
        row for row in catalog[:64]
        if isinstance(row, Mapping)
        and type(row.get("id")) is str
        and isinstance(row.get("statement"), str)
        and bool(row["statement"].strip())
        and row.get("root_cause_verified") is False
        and isinstance(row.get("evidence_reads"), list)
        and row["evidence_reads"]
        and all(type(r) is int for r in row["evidence_reads"])
    ]
    if not candidates:
        return ""
    index = {kind: i for i, kind in enumerate(_PRIORITY)}
    candidates.sort(key=lambda item: (index.get(item.get("kind"), 100),
                                       int(item["evidence_reads"][0])))
    max_points = max(1, min(8, max_points))
    selected: list[Mapping[str, Any]] = []
    per_kind: dict[str, int] = {}
    for item in candidates:
        kind = str(item.get("kind", "unclassified"))
        kind_limit = (2 if kind in ("health_sample_summary", "health_stale_entry",
                                   "app_dependency_reference") else 1)
        if per_kind.get(kind, 0) >= kind_limit:
            continue
        if item["statement"] in {x["statement"] for x in selected}:
            continue
        selected.append(item)
        per_kind[kind] = per_kind.get(kind, 0) + 1
        if len(selected) >= max_points:
            break
    lines = ["**Evidence-based summary**"]
    for item in selected:
        refs = ", ".join("#" + str(i) for i in item["evidence_reads"])
        lines.append("- " + item["statement"] + " (Read " + refs + ")")
    kinds = {str(c.get("kind")) for c in selected}
    if kinds.intersection({"health_sample_summary", "health_stale_entry",
                           "health_unknown_entry"}):
        lines.append(
            "**Limit:** Last activity and missing event history do not by "
            "themselves confirm a device is offline.")
    if "app_dependency_reference" in kinds:
        lines.append(
            "App references show possible impact, not confirmed app failures "
            "or actual automation execution.")
    return "\n".join(lines)


__all__ = ["evidence_readiness", "evidence_brief"]

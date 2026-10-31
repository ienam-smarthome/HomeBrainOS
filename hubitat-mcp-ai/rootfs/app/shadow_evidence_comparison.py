"""Read-only, offline Stage 2.5 comparison of existing and canonical evidence.

This module is intentionally NOT imported by the agent, bridge, tool executor,
publisher, or Home Assistant entrypoints. The current witness ledger and causal
graph retain their own semantics; an agreement here is not causal proof.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import median
from time import perf_counter
from typing import Any, Mapping, Sequence

from canonical_investigation_evidence import build_canonical_evidence_view


# The legacy witness ledger calls native command time "hubitat-command".
# Canonical records it as "source-reported"; this mapping is ONLY for a
# comparison key, not an upgrade in timestamp or physical-ACK authority.
_LEGACY_KIND = {
    "journal_source_switch_on": ("switch", "on", "source"),
    "journal_source_switch_off": ("switch", "off", "source"),
    "journal_received_switch_on": ("switch", "on", "collector-received"),
    "journal_received_switch_off": ("switch", "off", "collector-received"),
    "reported_switch_on": ("switch", "on", "source-reported"),
    "reported_switch_off": ("switch", "off", "source-reported"),
    "reported_level": ("level", None, "source-reported"),
    "issued_on": ("on", "on", "source-reported"),
    "issued_off": ("off", "off", "source-reported"),
    "issued_setlevel": ("setLevel", "setLevel", "source-reported"),
}
_INPUT_ATTRS = frozenset(("motion", "occupancy", "presence"))


def _clock(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat() if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _canonical_key(event: Any) -> tuple[str, str, str, str, str] | None:
    when = _clock(event.time_utc)
    if when is None:
        return None
    return (event.entity_id, event.attribute, event.value.lower(),
            event.clock_basis, when)


def _witness_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str] | None:
    when = _clock(row.get("time"))
    if when is None:
        return None
    kind = row.get("event_class")
    if kind in _LEGACY_KIND:
        attr, value, basis = _LEGACY_KIND[kind]
        if value is None:
            value = str(row.get("value") or "").lower()
        return (str(row.get("entity") or ""), attr, value, basis, when)
    if kind in _INPUT_ATTRS and row.get("role") == "input-report":
        return (str(row.get("entity") or ""), kind,
                str(row.get("value") or "").lower(),
                str(row.get("clock_basis") or ""), when)
    return None


def _small_key(key: tuple[str, str, str, str, str]) -> dict[str, str]:
    return dict(zip(("entity_id", "attribute", "value", "clock_basis",
                     "time_utc"), key))


def compare_shadow_evidence(
    receipts: Sequence[Mapping[str, Any]],
    legacy_facts: Mapping[str, Any] | None,
    *,
    legacy_graph: Mapping[str, Any] | None = None,
    max_examples: int = 12,
) -> dict[str, Any]:
    """Compare identical retained read receipts, without taking actions.

    Only independently represented, exact observations are compared. Extra
    canonical rows are NOT automatically errors: the legacy witness ledger
    intentionally has a narrower group scope and a presentation cap.
    """
    view = build_canonical_evidence_view(receipts)
    canonical_keys = Counter(k for e in view.events
                             if (k := _canonical_key(e)) is not None)
    facts = legacy_facts if isinstance(legacy_facts, Mapping) else {}
    witness = facts.get("v3_witness_ledger")
    witness = witness if isinstance(witness, Mapping) else {}
    legacy_keys = {
        k for row in (witness.get("witnesses") or [])
        if isinstance(row, Mapping) and (k := _witness_key(row)) is not None
    }
    misses = sorted(k for k in legacy_keys if k not in canonical_keys)
    cap = max(0, min(int(max_examples), 25))
    target_ids = sorted({str(row.get("device_id"))
                         for row in (facts.get("target_coverage") or [])
                         if isinstance(row, Mapping) and row.get("device_id")},
                        key=lambda value: (not value.isdecimal(), value))
    missing_labels = [
        device for device in target_ids
        if view.verified_label("device", device) is None
    ]
    # Some legacy lookups are less strongly scoped than the new contract.
    # Report these as gaps; never copy an unauthenticated legacy label across.
    issuer_names = sorted({
        e.issuer_app_id for e in view.events
        if e.role == "issued-command" and e.issuer_app_id
        and view.verified_label("app", e.issuer_app_id)
    })
    legacy_app_ids = {str(row.get("app_id") or "")
                      for row in (facts.get("incident_ledger") or [])
                      if isinstance(row, Mapping)}
    missing_issuer_ids = [app for app in issuer_names if app in legacy_app_ids
                          and not any(row.get("issuer_name")
                                      for row in (facts.get("incident_ledger") or [])
                                      if isinstance(row, Mapping)
                                      and str(row.get("app_id")) == app)]
    target_gaps = []
    for device in target_ids:
        legacy = next((row for row in facts.get("target_coverage") or []
                       if isinstance(row, Mapping)
                       and str(row.get("device_id")) == device), {})
        canonical = [row for row in view.coverage if row.entity_id == device
                     and row.source == "historical-journal"]
        legacy_gaps = legacy.get("journal_gaps")
        # Journal gapCount counts query gaps, NOT confirmed physical outages.
        if type(legacy_gaps) is int and canonical:
            total = sum(row.gap_count for row in canonical)
            if total != legacy_gaps:
                target_gaps.append({"device_id": device,
                                    "legacy_query_gaps": legacy_gaps,
                                    "canonical_query_gaps": total})
    omitted = int(witness.get("witnesses_omitted") or 0)
    has_witness = witness.get("schema") == "causal-witness-ledger.v1"
    changes = bool(misses or missing_labels or target_gaps)
    limited = bool(omitted or len(receipts) > 160 or not has_witness)
    result = {
        "schema": "homebrain-shadow-comparison.v1",
        "shadow_only": True,
        "writes_performed": 0,
        "legacy_witness_available": has_witness,
        "legacy_graph_scope": (str(legacy_graph.get("scope") or "unknown")
                               if isinstance(legacy_graph, Mapping) else "not-supplied"),
        "status": ("not-comparable" if not has_witness else
                   "divergence" if changes else
                   "partial" if limited else "matching-comparable-witnesses"),
        "canonical_counts": {
            "identity_records": len(view.identities),
            "event_records": len(view.events),
            "unique_event_keys": len(canonical_keys),
            "coverage_records": len(view.coverage),
            "source_clock_records": sum(e.clock_basis == "source" for e in view.events),
            "collector_clock_records": sum(e.clock_basis == "collector-received" for e in view.events),
        },
        "legacy_counts": {
            "available_witness_keys": len(legacy_keys),
            "witnesses_omitted": omitted,
            "matched_witness_keys": len(legacy_keys) - len(misses),
            "missing_witness_keys": len(misses),
        },
        "missing_canonical_witnesses": [_small_key(key) for key in misses[:cap]],
        "missing_canonical_witnesses_omitted": max(0, len(misses) - cap),
        "target_ids_missing_canonical_verified_names": missing_labels[:16],
        "issuer_ids_with_name_lost_in_legacy_ledger": missing_issuer_ids[:16],
        "journal_query_gap_disagreements": target_gaps[:16],
        "source_coverage_proven_complete": False,
        "physical_ack_verified": False,
        "root_cause_verified_by_comparison": False,
        "limitations": [
            "Comparison never substitutes for source evidence or historical coverage.",
            "Legacy witness presentation is bounded and may omit receipts.",
            "Canonical events can outnumber legacy witnesses by design.",
            "No sensor/listener correlation is treated as a command issuer.",
        ],
    }
    return result


def benchmark_shadow_replay(
    receipts: Sequence[Mapping[str, Any]], question: str, *,
    iterations: int = 3,
) -> dict[str, Any]:
    """Offline, identical-input compute benchmark; excludes all MCP and LLM IO."""
    from unified_investigation_bridge import collect_unified_evidence

    count = max(1, min(int(iterations), 20))
    baseline_ms: list[float] = []
    comparison_ms: list[float] = []
    status = "not-run"
    for _ in range(count):
        start = perf_counter()
        facts = collect_unified_evidence(receipts, question)
        middle = perf_counter()
        report = compare_shadow_evidence(receipts, facts)
        end = perf_counter()
        status = report["status"]
        baseline_ms.append((middle - start) * 1000)
        comparison_ms.append((end - middle) * 1000)
    return {
        "schema": "homebrain-shadow-benchmark.v1",
        "offline_only": True, "iterations": count,
        "baseline_compute_median_ms": round(median(baseline_ms), 3),
        "shadow_comparison_median_ms": round(median(comparison_ms), 3),
        "comparison_status": status,
        "includes_mcp_or_model_latency": False,
        "changes_production_latency": False,
    }


__all__ = ["compare_shadow_evidence", "benchmark_shadow_replay"]

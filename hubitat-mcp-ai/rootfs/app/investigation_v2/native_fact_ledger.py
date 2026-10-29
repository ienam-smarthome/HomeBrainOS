"""Source-receipt-backed factual ledger for any Native V2 target investigation.

A factual ledger is not a semantic validator for free-form model text. It
attests narrow observations only, and never upgrades temporal coincidence,
static source, device state, or command issue to execution causality.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from .native_runtime_stats import focused_runtime_stat_receipts
from .native_operational_evidence import operational_evidence_facts

_METHOD = re.compile(r"\bmethod\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.I)
_DURATION = re.compile(r"\bran for\s+([\d,]+)\s*ms\b", re.I)


def factual_evidence_ledger(
    witnesses: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str] = (),
    *, max_facts: int = 36,
) -> list[dict[str, Any]]:
    """Host-attested, finite factual claims with original read numbers."""
    focus = {str(x) for x in focus_ids}
    facts: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    bound = max(1, min(80, max_facts))

    def add(fact: dict[str, Any], key: tuple[Any, ...]) -> None:
        if key in seen or len(facts) >= bound:
            return
        seen.add(key)
        fact["id"] = "fact-" + str(len(facts) + 1)
        fact["root_cause_verified"] = False
        facts.append(fact)

    for w in witnesses[:16]:
        read = w.get("read")
        op = w.get("operation")
        data = w.get("source_data")
        if type(read) is not int or not isinstance(data, Mapping):
            continue
        if op in ("hub_get_device_health", "hub_list_device_dependents"):
            # One receipt-based framework for cross-device health, stale
            # activity and app references. Neither staleness nor a dependency
            # is promoted to current offline/broken-automation causality.
            for observed in operational_evidence_facts(w, focus_ids):
                key = observed.pop("stable_key")
                add(observed, key)
            continue
        if op == "hub_get_logs":
            # Native Logs-page device/app runtime stats use this same READ
            # operation; do not discard them as malformed severity log rows.
            stats = data.get("runtime_stats")
            if isinstance(stats, Mapping):
                # One reusable source-scope rule governs incident text,
                # highlights and general claim publication. Even a broad
                # App Stats page contributes only independently verified
                # callers of the actual focused device.
                for row in focused_runtime_stat_receipts(witnesses,focus):
                    if row["read"] != read:
                        continue
                    values = {k: row[k] for k in ("pct","total","count")
                              if type(row.get(k)) in (int,float)}
                    if values:
                        add({
                            "kind": "cumulative_runtime_stats",
                            "evidence_reads": [read],
                            "source_kind": row["kind"], "source_id": row["id"],
                            "metrics": values,
                            "limits": (
                                "Hubitat Logs-page cumulative performance "
                                "snapshot, not historical incident-time CPU "
                                "attribution. Device and app percentages have "
                                "different denominators."),
                        }, (op,row["kind"],row["id"],
                            tuple(sorted(values.items()))))
                continue
            summary = data.get("log_summary")
            if not isinstance(summary, Mapping):
                continue
            for g in summary.get("warning_error_groups", [])[:20]:
                if not isinstance(g, Mapping):
                    continue
                src_id = str(g.get("source_id") or "")
                if focus and src_id not in focus:
                    continue
                level = str(g.get("level", "")).upper()
                if level not in ("WARN", "WARNING", "ERROR", "ERR", "FATAL"):
                    continue
                msg = str(g.get("message") or "")
                method = _METHOD.search(msg)
                elapsed = _DURATION.search(msg)
                duration = None
                if elapsed:
                    try:
                        parsed = int(elapsed.group(1).replace(",", ""))
                        if 0 <= parsed <= 86_400_000:
                            duration = parsed
                    except ValueError:
                        pass
                key = (op, src_id, level, g.get("oldest_returned"),
                       g.get("newest_returned"), method.group(1) if method else "")
                add({
                    "kind": "source_reported_warning",
                    "evidence_reads": [read],
                    "source_id": src_id or None,
                    "severity": level,
                    "oldest_returned": g.get("oldest_returned"),
                    "newest_returned": g.get("newest_returned"),
                    "observed_rows_in_group": g.get("count"),
                    "named_method": method.group(1) if method else None,
                    "source_reported_duration_ms": duration,
                    "limits": "Sampled warning; time zone, historical coverage and CPU causality unverified.",
                }, key)
        elif op == "hub_list_device_events":
            filters = w.get("read_filters", {})
            filters = filters if isinstance(filters, Mapping) else {}
            device_id = str(filters.get("deviceId") or "")
            if not device_id or (focus and device_id not in focus):
                continue
            for issuer in data.get("issuer_apps", [])[:12]:
                if not isinstance(issuer, Mapping):
                    continue
                aid = str(issuer.get("appId") or "")
                if not aid.isdecimal():
                    continue
                key = (op, device_id, aid)
                add({
                    "kind": "source_attested_device_command_issuer",
                    "evidence_reads": [read],
                    "device_id": device_id,
                    "app_id": aid,
                    "observed_command_rows": issuer.get("count"),
                    "first": issuer.get("oldest"),
                    "last": issuer.get("newest"),
                    "limits": "Bounded producedBy.appId observations, not a causal link to any WARN.",
                }, key)
        elif op == "hub_get_source":
            static = data.get("static_method_paths")
            if (data.get("source_complete") is not True
                    or not isinstance(static, Mapping)):
                continue
            source_id = str(data.get("requested_source_id") or "")
            source_type = data.get("requested_source_type")
            if not source_id.isdecimal() or source_type not in ("driver", "app"):
                continue
            add({
                "kind": "verified_static_source_structure",
                "evidence_reads": [read],
                "source_type": source_type,
                "source_id": source_id,
                "recognized_method_count": static.get("recognized_method_count"),
                "method_rows_returned": static.get("method_rows_returned"),
                "limits": "Static lexical method references, not executed branches or runtime CPU attribution.",
            }, (op, source_type, source_id))
    return facts


__all__ = ["factual_evidence_ledger"]

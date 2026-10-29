"""Source-receipt-backed factual ledger for any Native V2 target investigation.

A factual ledger is not a semantic validator for free-form model text. It
attests narrow observations only, and never upgrades temporal coincidence,
static source, device state, or command issue to execution causality.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

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
        if op == "hub_get_logs":
            # Native Logs-page device/app runtime stats use this same READ
            # operation; do not discard them as malformed severity log rows.
            stats = data.get("runtime_stats")
            filters = w.get("read_filters")
            filters = filters if isinstance(filters, Mapping) else {}
            if isinstance(stats, Mapping):
                mode = stats.get("mode")
                key_field = ("deviceId" if mode == "devices" else
                             "appId" if mode == "apps" else None)
                requested = str(filters.get(key_field) or "") if key_field else ""
                if not requested.isdecimal() or (focus and mode == "devices"
                                                 and requested not in focus):
                    continue
                for row in stats.get("rows", [])[:30]:
                    if not isinstance(row, Mapping) or str(row.get("id")) != requested:
                        continue
                    values = {k: row[k] for k in ("pct", "total", "count")
                              if type(row.get(k)) in (int, float)}
                    if values:
                        add({
                            "kind": "cumulative_runtime_stats",
                            "evidence_reads": [read],
                            "source_kind": mode, "source_id": requested,
                            "metrics": values,
                            "limits": (
                                "Logs-page performance snapshot, not the "
                                "device/app's measured CPU at any past warning."),
                        }, (op, mode, requested, tuple(sorted(values.items()))))
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

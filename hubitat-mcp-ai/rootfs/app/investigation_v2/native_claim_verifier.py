"""General, fail-closed structured claim publication for Native V2.

The model can *select* source-backed facts or ask for simple numeric comparisons,
but never supply the words that are published as verified observations. Every
published statement is rendered by the host from independently approved source
projections. This verifies only expressible predicates, not arbitrary natural
language or a full causal theory; unexpressible assertions are withheld.

No MCP calls, side effects, code, private settings or source strings are sent
from this module. Missing coverage is NEVER a verified absence.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .native_fact_ledger import factual_evidence_ledger
from .native_source_adapters import safe_string

_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,55}$")
_ID = re.compile(r"^(?:claim|fact)-[1-9][0-9]{0,3}$")
_PRIVATE = re.compile(
    r"(?i)(?:password|secret|token|credential|cookie|passphrase|"
    r"authorization|api_?key|url|ipaddress|macaddress|endpoint|"
    r"accesskey|bearer)"
)
_NUMERIC = {
    "temperature": "°C", "humidity": "%", "battery": "%",
    "power": "W", "level": "%", "illuminance": "lux",
    "cpuLoad": "%", "internalTempC": "°C",
    "freeMemoryMB": "MB", "freeMemoryKB": "KB",
    "databaseSizeMB": "MB",
}
_STATES = {
    "switch": {"on", "off"}, "motion": {"active", "inactive"},
    "contact": {"open", "closed"}, "healthStatus": {"online", "offline", "unknown"},
    "networkStatus": {"online", "offline", "unknown"},
    "deviceHealth": {"online", "offline", "unknown"},
    "status": {"idle", "playing", "paused", "buffering", "offline", "online"},
    "presence": {"present", "not present"},
}
_METRICS = frozenset((
    "cpuLoad", "internalTempC", "freeMemoryMB", "freeMemoryKB",
    "databaseSizeMB",
))
_MAX_CLAIMS = 64


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or type(value) not in (int, float):
        return None
    try:
        n = float(value)
    except (ValueError, OverflowError):
        return None
    return n if math.isfinite(n) and abs(n) < 1e10 else None


def _printed(value: Any) -> str:
    return str(int(value)) if float(value).is_integer() else str(round(float(value), 3))


def _scalar(attr: str, value: Any) -> tuple[str, float | None, str | None] | None:
    if attr in _NUMERIC:
        n = _number(value)
        if n is not None:
            return _printed(n), n, _NUMERIC[attr]
        return None
    if attr in _STATES and isinstance(value, str):
        normalized = value.casefold().strip()
        if normalized in _STATES[attr]:
            return normalized, None, None
    return None


def claim_catalog(
    witnesses: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str] = (),
    *, limit: int = _MAX_CLAIMS,
) -> list[dict[str, Any]]:
    """Build a typed receipt-backed catalog from *projected* successful reads.

    Source values are never accepted from an LLM. In particular no prose
    from log messages or arbitrary device attributes enters verified text.
    """
    limit = min(_MAX_CLAIMS, max(1, int(limit)))
    focus = {str(i) for i in focus_ids}
    catalog: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def add(kind: str, label: str, read: int, key: tuple[Any, ...],
            *, numeric: float | None = None, unit: str | None = None,
            metric: str | None = None, scope: str | None = None,
            cause: bool = False) -> None:
        if key in seen or len(catalog) >= limit:
            return
        seen.add(key)
        catalog.append({
            "id": "claim-" + str(len(catalog) + 1),
            "kind": kind, "statement": safe_string(label, 250),
            "evidence_reads": [read],
            "status": "observed_in_bounded_source",
            "root_cause_verified": bool(cause),
            "numeric": numeric, "unit": unit, "metric": metric,
            "scope": scope,
        })

    # Labels are taken solely from the exact independently retrieved
    # projected read, never a model assertion or a different entity.
    def matching_source(read: int, op: str, src: str) -> Mapping[str, Any]:
        for w in witnesses[:16]:
            if w.get("read") != read or w.get("operation") != op:
                continue
            d = w.get("source_data", {})
            if not isinstance(d, Mapping):
                continue
            if op == "hub_get_logs":
                groups = d.get("log_summary", {}).get("warning_error_groups", [])
            else:
                groups = d.get("issuer_apps", [])
            for row in groups[:25] if isinstance(groups, list) else []:
                if not isinstance(row, Mapping):
                    continue
                ident = (row.get("source_id") if op == "hub_get_logs"
                         else row.get("appId"))
                if str(ident) == src:
                    return row
        return {}

    for fact in factual_evidence_ledger(witnesses, focus_ids, max_facts=40):
        reads = fact.get("evidence_reads", [])
        if not reads or type(reads[0]) is not int:
            continue
        read = reads[0]
        kind = fact["kind"]
        if kind == "source_reported_warning":
            src = fact.get("source_id")
            severity = fact.get("severity")
            period = (str(fact.get("oldest_returned") or "unknown")[:35] +
                      " to " + str(fact.get("newest_returned") or "unknown")[:35])
            method = fact.get("named_method")
            duration = fact.get("source_reported_duration_ms")
            original = matching_source(read, "hub_get_logs", str(src))
            display_name = safe_string(original.get("source_name") or "", 75)
            observed_msg = str(original.get("message") or "").casefold()
            if isinstance(method, str) and _FIELD.fullmatch(method):
                detail = f"reported slow method {method}"
            elif "watchdog fired" in observed_msg:
                detail = "watchdog warning; source-reported Watchdog fired"
            else:
                detail = "reported warning"
            if type(duration) is int:
                detail += f" (source-reported {duration} ms)"
            label = display_name or ("Source " + str(src or "unknown"))
            add("warning", f"{label} {detail} (source {src or 'unknown'}, "
                f"severity {severity}); sampled period {period}. "
                "Historical coverage is incomplete.",
                read, (kind, src, severity, period, method, duration),
                scope=str(src) if src else None)
        elif kind == "source_attested_device_command_issuer":
            dev, app = str(fact.get("device_id")), str(fact.get("app_id"))
            count = fact.get("observed_command_rows")
            count_text = str(count) if type(count) is int and 0 <= count < 100000 else "some"
            caller = matching_source(read, "hub_list_device_events", app)
            name = safe_string(caller.get("name") or "", 75)
            app_label = f"{name} (app {app})" if name else f"app {app}"
            add("command_issuer",
                f"In the bounded event sample for device {dev}, {app_label} "
                f"issued {count_text} recorded commands. This does not show causation.",
                read, (kind, dev, app), scope=dev)
        elif kind == "cumulative_runtime_stats":
            sid, stype = str(fact.get("source_id")), fact.get("source_kind")
            values = fact.get("metrics")
            if not isinstance(values, Mapping) or stype not in ("devices", "apps"):
                continue
            for field in ("pct", "total", "count"):
                n = _number(values.get(field))
                if n is None or n < 0:
                    continue
                suffix = "%" if field == "pct" else ""
                add(
                    "runtime_stat",
                    f"Hubitat Logs {stype} source {sid} reported {field}="
                    f"{_printed(n)}{suffix} in a cumulative performance "
                    "snapshot; this is not incident-time CPU attribution.",
                    read, (kind, stype, sid, field, n),
                    numeric=n, unit=suffix or None, metric=field, scope=sid,
                )
        elif kind == "verified_static_source_structure":
            sid, stype = str(fact.get("source_id")), fact.get("source_type")
            n = fact.get("recognized_method_count")
            if type(n) is int and n >= 0:
                add("static_source",
                    f"Complete verified {stype} source {sid} contains "
                    f"{n} lexically recognised methods; execution not established.",
                    read, (kind, stype, sid), scope=sid)
    for w in witnesses[:16]:
        read, op, data = w.get("read"), w.get("operation"), w.get("source_data")
        if type(read) is not int or not isinstance(data, Mapping):
            continue
        filters = w.get("read_filters")
        filters = filters if isinstance(filters, Mapping) else {}
        if op == "hub_get_device":
            device = str(filters.get("deviceId") or "")
            if (not device.isdecimal()
                    or (data.get("id") is not None
                        and str(data["id"]) != device)
                    or (focus and device not in focus)):
                continue
            attrs = data.get("attributes", [])
            if not isinstance(attrs, list):
                continue
            for row in attrs[:60]:
                if not isinstance(row, Mapping):
                    continue
                field = row.get("name")
                if not isinstance(field, str) or _PRIVATE.search(field):
                    continue
                scalar = _scalar(field, row.get("value"))
                if scalar is None:
                    continue
                printed, numeric, unit = scalar
                add("device_observation",
                    f"Device {device} source-reported {field}={printed}"
                    f"{unit or ''} at this read (not independent physical confirmation).",
                    read, (op, device, field, printed),
                    numeric=numeric, unit=unit, metric=field, scope=device)
        elif op in ("hub_get_metrics", "hub_get_performance_stats"):
            current = data.get("current")
            if not isinstance(current, Mapping):
                continue
            for field in _METRICS:
                n = _number(current.get(field))
                if n is not None:
                    add("hub_metric", f"Hub source-reported {field}={_printed(n)}"
                        f"{_NUMERIC.get(field, '')} at the metric read; not "
                        "incident-time device CPU attribution.",
                        read, (op, field, n), numeric=n,
                        unit=_NUMERIC.get(field), metric=field, scope="hub")
        elif op == "hub_get_app_config":
            app = str(data.get("requested_app_id") or filters.get("appId") or "")
            if (app.isdecimal() and data.get("requested_app_id_verified") is True
                    and data.get("source_app_id_matches_request") is not False):
                add("app_metadata", f"App {app} configuration metadata was read; "
                    "settings values and historical execution are not verified.",
                    read, (op, app), scope=app)
    return catalog


def _proposal(content: Any) -> Mapping[str, Any] | None:
    """Accept only a bounded strict JSON object; never interpret free text."""
    if isinstance(content, Mapping):
        obj = content
    elif isinstance(content, str) and len(content) <= 12000:
        try:
            obj = json.loads(content)
        except (ValueError, TypeError):
            return None
    else:
        return None
    return obj if isinstance(obj, Mapping) else None


def validate_claims(
    proposal: Any, catalog: Sequence[Mapping[str, Any]], *,
    max_selection: int = 12,
) -> dict[str, Any]:
    """Independent, exact validation of structured claims and comparisons.

    No free-text explanations, causal claims, missing-data negations, external
    values, unit conversions or unverifiable operators are publishable.
    """
    obj = _proposal(proposal)
    by_id = {x["id"]: x for x in catalog if x.get("id")}
    rejected: list[str] = []
    accepted: list[dict[str, Any]] = []
    used: set[tuple[Any, ...]] = set()
    if obj is None:
        return {"accepted": [], "rejected": ["non_structured_answer"],
                "status": "unstructured_withheld"}
    if set(obj) != {"claims"}:
        return {"accepted": [], "rejected": ["unrecognised_top_level_fields"],
                "status": "unverified"}
    raw_claims = obj.get("claims")
    if not isinstance(raw_claims, list) or len(raw_claims) > 50:
        return {"accepted": [], "rejected": ["invalid_claim_list"],
                "status": "unverified"}
    for item in raw_claims:
        if len(accepted) >= min(20, max_selection):
            rejected.append("selection_limit")
            break
        if not isinstance(item, Mapping) or len(item) > 8:
            rejected.append("invalid_item")
            continue
        # Explicitly ignore any untrusted model-supplied statement/justification.
        # A model cannot confer cause authority by claiming confidence.
        kind = item.get("operator", "observed")
        permitted = ({"fact_id", "operator"} if kind == "observed" else
                     {"operator", "left_id", "right_id"})
        if not set(item).issubset(permitted):
            rejected.append("unvalidated_claim_fields")
            continue
        if kind == "observed":
            ident = item.get("fact_id")
            if not isinstance(ident, str) or not _ID.fullmatch(ident):
                rejected.append("invalid_fact_id")
                continue
            fact = by_id.get(ident)
            if fact is None or fact.get("root_cause_verified") is True:
                rejected.append("unknown_or_unauthorised_fact")
                continue
            key = ("observed", ident)
            if key not in used:
                accepted.append({"text": fact["statement"],
                                 "evidence_reads": fact["evidence_reads"],
                                 "fact_ids": [ident], "predicate": "observed"})
                used.add(key)
        elif kind in ("greater_than", "less_than", "equal_to"):
            left_id, right_id = item.get("left_id"), item.get("right_id")
            if not isinstance(left_id, str) or not isinstance(right_id, str):
                rejected.append("invalid_comparison_ref")
                continue
            if not _ID.fullmatch(left_id) or not _ID.fullmatch(right_id):
                rejected.append("invalid_comparison_ref")
                continue
            a, b = by_id.get(left_id), by_id.get(right_id)
            if (not a or not b or a["id"] == b["id"]
                    or a.get("numeric") is None or b.get("numeric") is None
                    or a.get("metric") != b.get("metric")
                    or a.get("unit") != b.get("unit")
                    or a.get("metric") not in _NUMERIC):
                rejected.append("incompatible_or_missing_numeric_evidence")
                continue
            av, bv = float(a["numeric"]), float(b["numeric"])
            truth = {"greater_than": av > bv, "less_than": av < bv,
                     "equal_to": av == bv}[kind]
            if not truth:
                rejected.append("comparison_contradicts_source")
                continue
            key = (kind, left_id, right_id)
            if key in used:
                continue
            symbol = {"greater_than": "greater than",
                      "less_than": "less than", "equal_to": "equal to"}[kind]
            unit = a.get("unit") or ""
            text = (f"In the returned measurements, {a['metric']} for "
                    f"{a.get('scope')} ({_printed(av)}{unit}) was {symbol} "
                    f"{a['metric']} for {b.get('scope')} "
                    f"({_printed(bv)}{unit}); simultaneous sampling unverified.")
            accepted.append({"text": text,
                             "evidence_reads": sorted(set(
                                 a["evidence_reads"] + b["evidence_reads"])),
                             "fact_ids": [left_id, right_id], "predicate": kind})
            used.add(key)
        else:
            rejected.append("unverifiable_operator")
    return {"accepted": accepted, "rejected": rejected,
            "status": "validated" if accepted else "no_valid_claims"}


def publish_verified_claims(
    proposed: Any, catalog: Sequence[Mapping[str, Any]], *,
    max_fallback: int = 9,
) -> dict[str, Any]:
    """Return only host-authored statements. Fallback itself is evidence-backed."""
    verdict = validate_claims(proposed, catalog)
    chosen = verdict["accepted"]
    fallback = not chosen
    if fallback:
        chosen = [{
            "text": fact["statement"], "evidence_reads": fact["evidence_reads"],
            "fact_ids": [fact["id"]], "predicate": "observed",
        } for fact in catalog[:max_fallback]]
    lines = ["**Source-verified findings**"]
    if not chosen:
        lines.append("No independently verifiable source claim was recovered.")
    else:
        for claim in chosen:
            reads = ",".join("#" + str(i) for i in claim["evidence_reads"])
            lines.append("- " + claim["text"] + f" (Read {reads})")
    lines.extend([
        "",
        "**Conclusion and uncertainty**",
        "Only the observations above are independently verified in the "
        "bounded returned data. The root cause, device performance impact "
        "or real-world action is not established merely by these facts. "
        "Unsupported model conclusions were not published.",
    ])
    return {
        "text": "\n".join(lines),
        "validation": verdict,
        "fallback": fallback,
        "published_claims": chosen,
        "model_prose_published": False,
        "limits": "A structured fact protocol can verify supported predicates "
                  "and withhold others; it cannot prove arbitrary semantic or "
                  "causal claims without corresponding independent evidence.",
    }


__all__ = ["claim_catalog", "validate_claims", "publish_verified_claims"]

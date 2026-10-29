"""Link independent source observations by independently returned source ID.

A generic, source-typed evidence graph for broad Hubitat investigations:
warning groups and current device attributes are joined ONLY when their
source IDs agree with an independently verified, successful scoped device
read. No question keyword, device-specific rule, inferred driver cause,
network reachability guarantee or automation execution assertion.

Ranks evidence *triage* by observed offline telemetry, corroborating
independent reads and bounded warning recurrence. This is not a physical
failure severity score or proof of cause; ranked entries remain observations.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .native_source_adapters import safe_string


_DISPLAY_FIELDS = ("healthStatus", "networkStatus", "deviceHealth",
                   "lastSeen", "dataAgeSeconds", "mqttStatus")
_ALLOWED_STATES = {
    "healthStatus": {"online", "offline", "unknown"},
    "networkStatus": {"online", "offline", "unknown"},
    "deviceHealth": {"online", "offline", "unknown", "stale"},
    "mqttStatus": {"online", "offline", "connected", "disconnected"},
}


def _source_id(value: Any) -> str:
    if type(value) not in (int, str):
        return ""
    text = str(value)
    return text if text.isdecimal() and len(text) <= 20 else ""


def verified_source_cases(
    witnesses: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return bounded multi-read observational packets, never inferred faults."""
    cases: dict[tuple[str, str], dict[str, Any]] = {}
    for w in witnesses[:16]:
        read = w.get("read")
        data = w.get("source_data")
        if type(read) is not int or not isinstance(data, Mapping):
            continue
        op = w.get("operation")
        if op == "hub_get_logs":
            groups = data.get("log_summary")
            groups = groups.get("warning_error_groups", []) if isinstance(groups, Mapping) else []
            if not isinstance(groups, list):
                continue
            for group in groups[:35]:
                if not isinstance(group, Mapping):
                    continue
                ident = _source_id(group.get("source_id"))
                typ = group.get("source_type")
                count = group.get("count")
                level = str(group.get("level") or "").upper()
                if not ident or typ not in ("dev", "device", "app") or level not in ("WARN", "ERROR"):
                    continue
                if type(count) is not int or not (0 < count <= 100000):
                    continue
                key = ("device" if typ in ("dev", "device") else "app", ident)
                case = cases.setdefault(key, {
                    "source_type": key[0], "source_id": ident,
                    "name": "", "warning_rows": 0, "log_reads": [],
                    "device_reads": [], "status": {},
                    "warning_levels": set(), "warning_groups": 0,
                    "observations": 0,
                })
                label = safe_string(group.get("source_name") or "", 70)
                if label and not case["name"]:
                    case["name"] = label
                case["warning_rows"] += count
                case["warning_groups"] += 1
                case["warning_levels"].add(level)
                if read not in case["log_reads"]:
                    case["log_reads"].append(read)
        elif op == "hub_get_device":
            filters = w.get("read_filters")
            if not isinstance(filters, Mapping):
                continue
            ident = _source_id(filters.get("deviceId"))
            if not ident or _source_id(data.get("id")) != ident:
                continue
            # Only a previously source-attested ID may connect to a
            # warning case. An unrelated device read cannot create a
            # second source's apparent evidence.
            case = cases.get(("device", ident))
            if case is None:
                continue
            attrs = data.get("attributes")
            if not isinstance(attrs, list):
                continue
            observed = {}
            for row in attrs[:80]:
                if not isinstance(row, Mapping):
                    continue
                field = row.get("name")
                value = row.get("value")
                if field not in _DISPLAY_FIELDS:
                    continue
                if field in _ALLOWED_STATES:
                    if not isinstance(value, str):
                        continue
                    status = value.strip().casefold()
                    if status not in _ALLOWED_STATES[field]:
                        continue
                    observed[field] = status
                elif field == "lastSeen":
                    if (isinstance(value, str) and len(value) <= 65
                            and not any(token in value.casefold() for token in
                                        ("http", "token", "secret", "key=", "password"))):
                        observed[field] = safe_string(value, 65)
                elif field == "dataAgeSeconds":
                    if type(value) in (float, int) and 0 <= value < 10**9:
                        observed[field] = str(int(value))
            if observed:
                case["status"].update(observed)
                case["observations"] += len(observed)
                if read not in case["device_reads"]:
                    case["device_reads"].append(read)
    output = []
    for c in cases.values():
        if not c["warning_rows"]:
            continue
        offline = any(c["status"].get(field) == "offline"
                      for field in ("healthStatus", "networkStatus", "deviceHealth"))
        # Explicitly a triage evidence-strength heuristic, not physical
        # seriousness. App-only logs can still rank via recurrence.
        score = (60 if offline else 0) + (
            15 if c["device_reads"] else 0) + min(c["warning_rows"], 40)
        output.append({
            "source_type": c["source_type"],
            "source_id": c["source_id"],
            "name": c["name"] or (c["source_type"] + " " + c["source_id"]),
            "warning_rows_in_returned_sample": c["warning_rows"],
            "warning_groups_in_returned_sample": c["warning_groups"],
            "warning_levels": sorted(c["warning_levels"]),
            "status": c["status"],
            "evidence_reads": sorted(set(c["log_reads"] + c["device_reads"])),
            "source_correlated": bool(c["device_reads"]),
            "triage_evidence_score": score,
            "confirmed_physical_fault": False,
            "cause_attributed": False,
        })
    output.sort(key=lambda c: (-c["triage_evidence_score"],
                               -c["warning_rows_in_returned_sample"],
                               c["source_id"]))
    return output[:12]


def source_connected_brief(
    witnesses: Sequence[Mapping[str, Any]], *,
    max_cases: int = 3,
) -> str:
    """Lead with multi-read evidence when available, not stale-list order.

    Only publish when at least one same-ID warning/current-state join
    succeeds. Display a few distinct source cases for triage, and keep
    all source/uncertainty disclosures. Never treat state labels as a
    network probe or collapse healthStatus and networkStatus semantics.
    """
    cases = verified_source_cases(witnesses)
    if not any(c["source_correlated"] for c in cases):
        return ""
    max_cases = max(1, min(5, max_cases))
    lines = ["**Most significant source-reported issues to check**"]
    for c in cases[:max_cases]:
        name = safe_string(c["name"], 70)
        refs = ", ".join("#" + str(n) for n in c["evidence_reads"])
        typ = "device" if c["source_type"] == "device" else "app"
        levels = "/".join(c["warning_levels"])
        line = (f"- **{name} ({typ} {c['source_id']})**: "
                f"{c['warning_rows_in_returned_sample']} {levels} log rows "
                "in the returned sample")
        statuses = c["status"]
        displayed = [
            f"{field}={statuses[field]}" for field in _DISPLAY_FIELDS
            if field in statuses
        ]
        if displayed:
            line += "; independent device reading: " + ", ".join(displayed)
        line += f". (Read {refs})"
        lines.append(line)
    lines.append(
        "**Limits:** These are ranked by source evidence for triage, not "
        "verified severity or root cause. Different status attributes "
        "can disagree; no independent connectivity test, app-execution "
        "confirmation or complete log coverage is established.")
    return "\n".join(lines)


__all__ = ["verified_source_cases", "source_connected_brief"]

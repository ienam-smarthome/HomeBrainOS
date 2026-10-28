"""Source adapters for model-native read investigations.

A gateway returning success only proves that the call completed. The adapter
must project actual returned data into bounded, typed evidence before the model
may use it. In particular, hub_get_logs returns 'entries' on live Hubitat MCP,
not necessarily 'logs'. Log row IDs and message text are not device identity.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping


_LOG_PREFIX = re.compile(r"^(dev|app)\|([0-9]{1,20})\|([^|]{1,120})\|")
_NUMERIC = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?")
_SECRET = re.compile(r"(?i)\b(?:token|secret|apikey|api_key|password|"
                     r"authorization|bearer|credential)\b\s*[:=]\s*[^\s,;]+")
_URL = re.compile(r"https?://[^\s<>]+", re.I)


def safe_string(value: Any, limit: int = 300) -> str:
    s = str(value if value is not None else "")[:2000]
    s = _URL.sub("[URL redacted]", s)
    s = _SECRET.sub("[credential redacted]", s)
    return " ".join("".join(ch if ch.isprintable() and ch not in "<>\x60"
                            else " " for ch in s).split())[:limit]


def unwrapped(data: Any) -> Mapping[str, Any]:
    """Follow only recognised protocol envelope dictionaries."""
    if not isinstance(data, dict):
        return {}
    current = data
    for _ in range(3):
        inner = next((current[k] for k in ("result", "data", "output")
                      if isinstance(current.get(k), dict)), None)
        if inner is None:
            break
        if any(k in current for k in ("entries", "logs", "events", "devices",
                                       "alerts", "health", "metrics")):
            break
        current = inner
    return current


def log_rows(data: Any) -> list[dict[str, Any]] | None:
    d = unwrapped(data)
    for key in ("entries", "logs"):
        value = d.get(key)
        if isinstance(value, list):
            return [v for v in value[:350] if isinstance(v, dict)]
    return None


def log_source(row: Mapping[str, Any]) -> tuple[str, str | None, str]:
    """Infer identity only from a strict structured source prefix AND metadata."""
    source_type = str(row.get("type") or row.get("sourceType") or "").lower()
    name = safe_string(row.get("name") or row.get("appName"), 110)
    message = str(row.get("message") or row.get("msg") or "")
    matched = _LOG_PREFIX.match(message)
    # Normalise cosmetic label differences (case, brackets, punctuation),
    # but require BOTH source kind and full label to agree with the
    # structured prefix. Never accept a source ID from free text alone.
    def stable_label(v: str) -> str:
        return " ".join(re.findall(r"[^\\W_]+", v.casefold(), flags=re.UNICODE))
    normalized_kind = "dev" if source_type in ("dev", "device") else source_type
    if (matched and matched.group(1) == normalized_kind
            and name and stable_label(name) == stable_label(matched.group(3))):
        return matched.group(1), matched.group(2), name
    source = row.get("source")
    if isinstance(source, dict):
        kind = str(source.get("type") or source.get("sourceType") or "").lower()
        identity = source.get("id")
        if (kind in ("app", "dev", "device")
                and type(identity) in (str, int)
                and str(identity).isdecimal()):
            return kind, str(identity), safe_string(source.get("name"), 110)
    return source_type or "unknown", None, name or "unknown"


def attested_source_ids(operation: str, data: Any) -> set[str]:
    d = unwrapped(data)
    contracts = {
        "hub_list_devices": ("devices", ("id", "deviceId")),
        "hub_list_apps": ("apps", ("id", "appId")),
        "hub_list_rules": ("rules", ("id", "appId")),
        "hub_get_device_health": ("devices", ("id", "deviceId")),
    }
    if operation == "hub_get_logs":
        result: set[str] = set()
        for row in log_rows(d) or []:
            # Structured sourceId/appId/deviceId fields are source identities;
            # the generic log row "id" remains a log entry ID, never a target.
            for key in ("appId", "deviceId", "sourceId"):
                value = row.get(key)
                if type(value) in (str, int) and str(value).isdecimal():
                    result.add(str(value))
            source_identity = log_source(row)[1]
            if source_identity is not None:
                result.add(source_identity)
        return result
    contract = contracts.get(operation)
    if contract is None:
        return set()
    collection, keys = contract
    rows = d.get(collection)
    result: set[str] = set()
    if isinstance(rows, list):
        for row in rows[:500]:
            if not isinstance(row, dict):
                continue
            for key in keys:
                value = row.get(key)
                if type(value) in (str, int) and str(value).isdecimal():
                    result.add(str(value))
    return result


def compact_logs(data: Any) -> dict[str, Any] | None:
    """Prefer actionable severity over high-frequency INFO chatter."""
    rows = log_rows(data)
    if rows is None:
        return None
    d = unwrapped(data)
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    stamps: dict[tuple[str, str, str], set[str]] = {}
    counts: Counter[str] = Counter()
    observed_times: list[str] = []
    for row in rows:
        level = safe_string(row.get("level") or row.get("severity") or "unknown", 20).upper()
        counts[level] += 1
        stamp = safe_string(row.get("time") or row.get("date")
                            or row.get("timestamp"), 65)
        if stamp:
            observed_times.append(stamp)
        if level not in ("WARN", "WARNING", "ERROR", "ERR", "FATAL"):
            continue
        kind, identity, name = log_source(row)
        message = safe_string(row.get("message") or row.get("msg")
                              or row.get("description"), 330)
        normalized = _NUMERIC.sub("#", message).casefold()
        key = (kind + ":" + (identity or name), level, normalized)
        record = groups.setdefault(key, {
            "level": level, "source_type": kind,
            "source_id": identity, "source_name": name,
            "message": message, "count": 0,
            "duplicate_timestamp_rows": 0,
            "oldest_returned": None, "newest_returned": None,
        })
        record["count"] += 1
        if stamp:
            seen = stamps.setdefault(key, set())
            if stamp in seen:
                record["duplicate_timestamp_rows"] += 1
            seen.add(stamp)
            record["oldest_returned"] = min(
                stamp, record["oldest_returned"]) if record["oldest_returned"] else stamp
            record["newest_returned"] = max(
                stamp, record["newest_returned"]) if record["newest_returned"] else stamp
    ordered = sorted(groups.values(), key=lambda g: (
        0 if g["level"] in ("ERROR", "ERR", "FATAL") else 1,
        -g["count"], g["source_name"].casefold(),
    ))
    total = d.get("total")
    total = total if type(total) is int and total >= 0 else None
    return {
        "returned_rows": len(rows),
        "total_reported_by_gateway": total,
        "level_counts_in_returned_rows": dict(counts),
        "warning_error_groups": ordered[:15],
        "warning_error_group_count": len(groups),
        "oldest_returned": min(observed_times) if observed_times else None,
        "newest_returned": max(observed_times) if observed_times else None,
        "time_basis": "source timestamps; timezone not verified",
        "truncated_or_partial": bool(
            d.get("truncated") is True or len(rows) >= 350 or
            (total is not None and total > len(rows))),
        "warning_error_audit_complete": False,
        "interpretation_guard": (
            "A sample containing no WARN/ERROR is NOT evidence that the hub "
            "has no warnings. Request a severity-filtered log read if "
            "errors or health issues remain unverified."
        ) if not groups else (
            "WARN/ERROR observations are present; inspect sources and "
            "request additional targeted evidence before concluding cause."
        ),
    }


__all__ = [
    "safe_string", "unwrapped", "log_rows", "log_source",
    "attested_source_ids", "compact_logs",
]

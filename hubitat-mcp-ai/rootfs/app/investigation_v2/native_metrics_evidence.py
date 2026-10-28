"""Bounded, privacy-filtered Hubitat metrics and numeric trends.

The live metrics operation reports current and trends but earlier native
projection dropped both. Keep numeric/boolean health observations, bounded
time-series points and provenance; never pass service endpoints, identifiers,
file paths, tokens or arbitrary prose through an evidence read.
"""
from __future__ import annotations

import re
from typing import Any, Mapping
from .native_source_adapters import unwrapped, safe_string

_FORBIDDEN = re.compile(
    r"(?i)(token|secret|password|credential|authorization|cookie|"
    r"api.?key|url|uri|host|address|ip|mac|path|file|bearer|"
    r"private|certificate|auth|user|account|session|device.?id|app.?id)"
)
_TIME_KEYS = frozenset({
    "time", "timestamp", "date", "recordedAt", "updatedAt", "collectedAt",
})
_STATUS_KEYS = frozenset({
    "status", "state", "health", "level", "severity", "unit",
    "period", "interval", "source", "reason",
})


def _public_key(key: Any) -> bool:
    return isinstance(key, str) and len(key) <= 65 and not _FORBIDDEN.search(key)


def _numbers(value: Any, *, depth: int = 0,
             max_rows: int = 14) -> Any:
    if depth >= 5:
        return None
    if isinstance(value, bool):
        return value
    if type(value) in (int, float):
        return value if abs(float(value)) < 1e18 else None
    if isinstance(value, str):
        # Only statuses, units and timestamps are retained by calling context.
        return None
    if isinstance(value, list):
        results = [_numbers(v, depth=depth+1, max_rows=max_rows)
                   for v in value[:max_rows]]
        return [v for v in results if v is not None]
    if isinstance(value, dict):
        output = {}
        for key, nested in list(value.items())[:65]:
            if not _public_key(key):
                continue
            if isinstance(nested, str):
                if key in _TIME_KEYS:
                    output[key] = safe_string(nested, 45)
                elif key in _STATUS_KEYS:
                    output[key] = safe_string(nested, 55)
                continue
            val = _numbers(nested, depth=depth+1, max_rows=max_rows)
            if val is not None:
                output[key] = val
        return output
    return None


def project_metrics(data: Any) -> dict[str, Any]:
    raw = unwrapped(data)
    result: dict[str, Any] = {}
    for field in ("current", "trends"):
        nested = raw.get(field)
        if isinstance(nested, (dict, list)):
            result[field] = _numbers(nested,
                                     max_rows=12 if field == "trends" else 15)
    for key in ("trendPointsAvailable", "trendRowsSkipped"):
        val = raw.get(key)
        if type(val) is int:
            result[key] = val
    result["metric_evidence_partial"] = True
    result["metric_projection_basis"] = (
        "bounded numeric/boolean observations; source timestamps if present")
    if not result.get("current") and not result.get("trends"):
        result["metrics_uninterpreted"] = True
    return result


__all__ = ["project_metrics"]

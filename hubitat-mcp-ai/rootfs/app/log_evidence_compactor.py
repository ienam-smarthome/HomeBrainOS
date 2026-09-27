"""Compact log evidence without losing threshold-crossing proof.

The model can inspect a larger raw log result than the final evidence receipt retains.
Keep the normal receipt bounded to the first 20 rows, but scan the full returned log
set for tiny structured Rule Machine threshold samples. This lets final synthesis
validate threshold-crossing claims against the same evidence the model saw without
serializing the entire log stream.
"""

from __future__ import annotations

import re
from typing import Any

_TRIGGERED = re.compile(
    r"Triggered:.*?reported\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_EVENT_VALUE = re.compile(
    r"^(?:Wait\s+)?Event:.*?(-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


def _message(item: dict[str, Any]) -> str:
    return str(
        item.get("message")
        or item.get("msg")
        or item.get("description")
        or item.get("text")
        or ""
    )


def _bounded_row(item: dict[str, Any]) -> dict[str, Any] | None:
    row = {
        "date": item.get("date") or item.get("timestamp") or item.get("time"),
        "source": (
            item.get("source")
            or item.get("sourceName")
            or item.get("app")
            or item.get("device")
        ),
        "level": item.get("level"),
        "message": _message(item),
    }
    return row if any(value not in {None, ""} for value in row.values()) else None


def _qualifies(operator: str, value: float, threshold: float) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == ">":
        return value > threshold
    if operator == "<=":
        return value <= threshold
    if operator == "<":
        return value < threshold
    return False


def _threshold_samples(logs: list[Any]) -> list[dict[str, Any]]:
    thresholds: dict[str, tuple[str, float, str]] = {}
    values: dict[str, list[float]] = {}

    for raw in logs:
        if not isinstance(raw, dict):
            continue
        message = _message(raw)
        parts = message.split("|", 3)
        if len(parts) < 4:
            continue
        prefix = "|".join(parts[:3])
        source = parts[2].strip()
        body = parts[3]

        triggered = _TRIGGERED.search(body)
        if triggered:
            thresholds[prefix] = (
                triggered.group(1),
                float(triggered.group(2)),
                source,
            )

        event_value = _EVENT_VALUE.search(body)
        if event_value:
            values.setdefault(prefix, []).append(float(event_value.group(1)))

    samples: list[dict[str, Any]] = []
    for prefix, (operator, threshold, source) in thresholds.items():
        observed = values.get(prefix, [])
        if len(observed) < 2:
            continue
        bounded_values = observed[:12]
        qualifying_count = sum(
            1 for value in observed if _qualifies(operator, value, threshold)
        )
        samples.append(
            {
                "source": source,
                "operator": operator,
                "threshold": threshold,
                "values": bounded_values,
                "minObserved": min(observed),
                "maxObserved": max(observed),
                "qualifyingCount": qualifying_count,
                "nonQualifyingCount": len(observed) - qualifying_count,
                "allQualifying": qualifying_count == len(observed),
                "observedValueCount": len(observed),
            }
        )
        if len(samples) >= 8:
            break
    return samples


def compact_log_evidence(data: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded human-readable excerpt plus full-result threshold proof."""

    logs = data.get("logs")
    if not isinstance(logs, list):
        return {}

    rows: list[dict[str, Any]] = []
    for raw in logs[:20]:
        if not isinstance(raw, dict):
            continue
        row = _bounded_row(raw)
        if row is not None:
            rows.append(row)

    details: dict[str, Any] = {
        "logCount": data.get("count", len(logs)),
        "logs": rows,
    }
    samples = _threshold_samples(logs)
    if samples:
        details["thresholdSamples"] = samples
    return details


__all__ = ["compact_log_evidence"]

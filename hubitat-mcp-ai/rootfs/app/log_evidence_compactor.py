"""Compact log evidence without losing threshold or timing proof.

The model can inspect a larger raw log result than the final evidence receipt retains.
Keep the normal receipt bounded to the first 20 rows, but scan the full returned log
set for tiny structured summaries. Threshold samples support Rule Machine validation;
host-derived timing summaries keep cadence and same-second cluster facts numeric so
the model does not have to infer them from timestamps.
"""

from __future__ import annotations

import re
from datetime import datetime
from statistics import median
from typing import Any

_TRIGGERED = re.compile(
    r"Triggered:.*?reported\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_EVENT_VALUE = re.compile(
    r"^(?:Wait\s+)?Event:.*?(-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
_IS_VALUE = re.compile(r"^(?P<signal>.+?)\s+is\b", re.IGNORECASE)


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


def _timestamp(item: dict[str, Any]) -> datetime | None:
    raw = item.get("date") or item.get("timestamp") or item.get("time")
    if raw in (None, ""):
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _source_signal(item: dict[str, Any]) -> tuple[str, str, str, str] | None:
    message = _message(item)
    parts = message.split("|", 3)
    if len(parts) < 4 or parts[0].casefold() not in {"dev", "app"}:
        return None
    source_kind = parts[0].strip()
    source_id = parts[1].strip()
    source = parts[2].strip()
    body = parts[3].strip()
    remainder = body
    if source and body.casefold().startswith(source.casefold()):
        remainder = body[len(source) :].strip()
    match = _IS_VALUE.match(remainder)
    if match is None:
        return source_kind, source_id, source, ""
    signal = match.group("signal").strip()
    if len(signal) > 100:
        signal = signal[:100].rstrip()
    return source_kind, source_id, source, signal


def _round_seconds(milliseconds: float) -> float | int:
    seconds = milliseconds / 1000.0
    rounded = round(seconds, 3)
    return int(rounded) if rounded.is_integer() else rounded


def _approx_cadence_seconds(milliseconds: float) -> float | int:
    """Return a human-scale cadence while preserving precise interval provenance.

    Cadence is explicitly approximate. Small timestamp jitter around a whole second
    should therefore render as that whole second (for example 60.01 -> 60), while
    min/max/median and one-off observed gaps keep their more precise values.
    """

    seconds = milliseconds / 1000.0
    nearest = round(seconds)
    if abs(seconds - nearest) <= 0.1:
        return int(nearest)
    return _round_seconds(milliseconds)


def _timing_observations(logs: list[Any]) -> dict[str, Any]:
    """Derive bounded cadence/gap and same-second facts from authoritative timestamps."""

    series: dict[tuple[str, str, str, str], list[datetime]] = {}
    same_second: dict[datetime, list[tuple[datetime, str, str]]] = {}

    for raw in logs:
        if not isinstance(raw, dict):
            continue
        stamp = _timestamp(raw)
        parsed = _source_signal(raw)
        if stamp is None or parsed is None:
            continue
        source_kind, source_id, source, signal = parsed
        source_key = f"{source_kind}|{source_id}"
        if signal:
            series.setdefault(parsed, []).append(stamp)
        second = stamp.replace(microsecond=0)
        same_second.setdefault(second, []).append((stamp, source_key, source))

    cadence: list[dict[str, Any]] = []
    for (source_kind, source_id, source, signal), stamps in series.items():
        ordered = sorted(set(stamps))
        if len(ordered) < 2:
            continue
        intervals_ms = [
            (right - left).total_seconds() * 1000.0
            for left, right in zip(ordered, ordered[1:])
            if right > left
        ]
        if not intervals_ms:
            continue
        entry: dict[str, Any] = {
            "source": source,
            "sourceRef": f"{source_kind}|{source_id}",
            "signal": signal,
            "observationCount": len(ordered),
            "first": ordered[0].isoformat(sep=" ", timespec="milliseconds"),
            "last": ordered[-1].isoformat(sep=" ", timespec="milliseconds"),
        }
        if len(intervals_ms) == 1:
            entry["observedGapSeconds"] = _round_seconds(intervals_ms[0])
        else:
            median_ms = float(median(intervals_ms))
            tolerance_ms = max(1000.0, median_ms * 0.15)
            stable = all(abs(value - median_ms) <= tolerance_ms for value in intervals_ms)
            entry.update(
                {
                    "intervalCount": len(intervals_ms),
                    "medianIntervalSeconds": _round_seconds(median_ms),
                    "minIntervalSeconds": _round_seconds(min(intervals_ms)),
                    "maxIntervalSeconds": _round_seconds(max(intervals_ms)),
                    "regularCadence": stable,
                }
            )
            if stable:
                entry["approxCadenceSeconds"] = _approx_cadence_seconds(median_ms)
        cadence.append(entry)

    cadence.sort(
        key=lambda row: (
            -int(row.get("observationCount") or 0),
            str(row.get("source") or "").casefold(),
            str(row.get("signal") or "").casefold(),
        )
    )

    clusters: list[dict[str, Any]] = []
    for second, rows in same_second.items():
        sources = sorted({source_key for _, source_key, _ in rows})
        if len(rows) < 3 or len(sources) < 3:
            continue
        ordered_rows = sorted(rows, key=lambda row: row[0])
        span_ms = round(
            (ordered_rows[-1][0] - ordered_rows[0][0]).total_seconds() * 1000.0
        )
        labels: list[str] = []
        seen_labels: set[str] = set()
        for _, _, label in ordered_rows:
            if label and label not in seen_labels:
                labels.append(label)
                seen_labels.add(label)
            if len(labels) >= 8:
                break
        clusters.append(
            {
                "second": second.isoformat(sep=" ", timespec="seconds"),
                "rowCount": len(rows),
                "distinctSourceCount": len(sources),
                "spanMs": span_ms,
                "sources": labels,
            }
        )

    clusters.sort(key=lambda row: (-int(row["distinctSourceCount"]), row["second"]))
    result: dict[str, Any] = {}
    if cadence:
        result["cadence"] = cadence[:12]
    if clusters:
        result["sameSecondClusters"] = clusters[:8]
    return result


def compact_log_evidence(data: dict[str, Any]) -> dict[str, Any]:
    """Return bounded raw rows plus full-result structured proof."""

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
    timing = _timing_observations(logs)
    if timing:
        details["hostDerivedTiming"] = timing
    return details


__all__ = ["compact_log_evidence"]

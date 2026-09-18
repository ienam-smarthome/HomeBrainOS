"""Deterministic proximity checks between subject history and location events."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _subject_boundaries(
    evidence: list[dict[str, Any]],
) -> list[tuple[datetime, str, str, str]]:
    boundaries: list[tuple[datetime, str, str, str]] = []
    for receipt in evidence:
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is not True
            or receipt.get("tool") != "homebrain_device_history"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        temporal = details.get("temporalAnalysis")
        if not isinstance(temporal, dict):
            continue
        label = str(details.get("label") or "the device").strip() or "the device"
        active = str(temporal.get("activeState") or "active").strip() or "active"
        intervals = temporal.get("observedIntervals")
        if not isinstance(intervals, list):
            continue
        for interval in intervals:
            if not isinstance(interval, dict):
                continue
            for field, transition in (("start", "started"), ("end", "ended")):
                parsed = _parse_timestamp(interval.get(field))
                if parsed is not None:
                    boundaries.append((parsed, label, active, transition))
        if boundaries:
            break
    return boundaries


def _location_rows(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if str(receipt.get("evidence_kind") or "") != "authoritative_location_event_history":
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        rows = details.get("events")
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict)]
    return []


def nearest_location_correlations(
    evidence: list[dict[str, Any]],
    *,
    max_delta_seconds: float = 15.0,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return location events tightly adjacent to observed subject boundaries."""

    boundaries = _subject_boundaries(evidence)
    rows = _location_rows(evidence)
    if not boundaries or not rows:
        return []

    matches: list[dict[str, Any]] = []
    for row in rows:
        when = _parse_timestamp(row.get("date"))
        if when is None:
            continue
        best: tuple[float, datetime, str, str, str] | None = None
        for boundary, label, active, transition in boundaries:
            delta = abs((when - boundary).total_seconds())
            if best is None or delta < best[0]:
                best = (delta, boundary, label, active, transition)
        if best is None or best[0] > max_delta_seconds:
            continue
        delta, boundary, label, active, transition = best
        matches.append({
            "deltaSeconds": round(delta, 3),
            "eventName": str(row.get("name") or "").strip(),
            "eventValue": str(row.get("value") or "").strip(),
            "eventDate": str(row.get("date") or "").strip(),
            "subjectLabel": label,
            "activeState": active,
            "subjectTransition": transition,
            "subjectDate": boundary.isoformat(),
        })

    matches.sort(key=lambda item: (float(item["deltaSeconds"]), item["eventDate"]))
    return matches[: max(0, int(limit))]


def render_location_correlation(match: dict[str, Any]) -> str:
    event_name = str(match.get("eventName") or "location event").strip()
    event_value = str(match.get("eventValue") or "").strip()
    event_date = str(match.get("eventDate") or "").strip()
    label = str(match.get("subjectLabel") or "the device").strip()
    active = str(match.get("activeState") or "active").strip()
    transition = str(match.get("subjectTransition") or "changed").strip()
    delta = float(match.get("deltaSeconds") or 0.0)
    event = f"{event_name}={event_value}" if event_value else event_name
    return (
        f"{event} at {event_date} was {delta:.1f}s from when "
        f"{label} {active} interval {transition}"
    )


__all__ = ["nearest_location_correlations", "render_location_correlation"]

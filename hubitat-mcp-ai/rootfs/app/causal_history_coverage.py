"""Coverage proof obligations for focal historical sensor reads.

A returned newest-N page containing only events *after* a requested boundary
cannot be used as negative evidence about activity at that boundary.
The check is source-agnostic and does not infer that data were deleted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _instant(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def assess_local_sensor_history_coverage(
    histories: list[dict[str, Any]], focal_boundary: Any,
) -> dict[str, Any]:
    """Classify returned timestamps, not the real-world continuity of a sensor.

    Having one event before the boundary is *not* sufficient to prove that all
    events were returned. It merely prevents the specific 'all events newer'
    coverage gap from being asserted.
    """
    target = _instant(focal_boundary)
    if target is None:
        return {"status": "unknown-boundary", "preFocalObserved": False}
    observed = []
    counts = {"historiesRead": 0, "historiesWithEvents": 0, "historiesWithPreFocal": 0,
              "historiesWithOnlyLater": 0, "historiesWithoutEvents": 0}
    for history in histories:
        if not isinstance(history, dict):
            continue
        counts["historiesRead"] += 1
        # events/observedEvents is the collected source page. boundaryEvents may
        # be a condensed derivative, so avoid double counting.
        source = history.get("observedEvents")
        if not isinstance(source, list):
            source = history.get("events")
        if not isinstance(source, list):
            source = history.get("boundaryEvents")
        times = [
            t for row in (source or [])
            if isinstance(row, dict)
            if (t := _instant(row.get("date") or row.get("timestamp"))) is not None
        ]
        if not times:
            counts["historiesWithoutEvents"] += 1
            continue
        observed.extend(times)
        counts["historiesWithEvents"] += 1
        if min(times) <= target:
            counts["historiesWithPreFocal"] += 1
        else:
            counts["historiesWithOnlyLater"] += 1
    gap = bool(
        counts["historiesRead"] > 0
        and counts["historiesWithPreFocal"] == 0
    )
    return {
        "status": "pre-focal-not-observed-in-returned-pages" if gap
        else "at-least-one-pre-focal-event-returned" if observed
        else "no-local-sensor-histories",
        **counts,
        "focalBoundary": target.isoformat(),
        "oldestReturnedEvent": min(observed).isoformat() if observed else None,
        "preFocalObserved": counts["historiesWithPreFocal"] > 0,
        "historicalCompletenessVerified": False,
        "unobservedIsNotInactive": True,
        "gapCanBeCausedByNewestNPage": True,
        "upstreamHistoricalWindowAvailable": False,
    }


__all__ = ["assess_local_sensor_history_coverage"]

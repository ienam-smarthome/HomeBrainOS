"""Source-clock-aware native history lookback for explicitly dated focal events.

Requested 23:49 BST 12 October was ~24h 3m old by the time a 13 October
22:52 UTC investigation made native history requests. The default 24-hour
history omitted that event while an earlier request had returned it. Plan
one bounded wider read *before* fetching light/button/command histories.
Do not confuse bounds requested with actual server retention/coverage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from focal_event_provenance import (
    explicit_british_clock_source, explicit_requested_instant,
)
from hub_timezone import required_history_hours_absolute

DEFAULT_HISTORY_HOURS = 24
MAX_HISTORY_HOURS = 168


def explicit_focal_history_lookback(
    prompt: str, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Return exact anchored UTC time and bounded hoursBack for native feeds.

    An explicit UK wall clock with a BST/GMT marker is sufficient to select
    the time window; it does NOT prove the actual historical event happened.
    Unlabelled ambiguous times are intentionally not converted or expanded.
    """
    source = explicit_british_clock_source(prompt)
    target = explicit_requested_instant(prompt, source) if source else None
    result: dict[str, Any] = {
        "schema": "explicit-focal-native-lookback-v1",
        "status": "no-trusted-explicit-anchor",
        "requestedEventUtc": None,
        "hoursBackRequested": DEFAULT_HISTORY_HOURS,
        "defaultHoursBack": DEFAULT_HISTORY_HOURS,
        "expandedBeyondDefault": False,
        "defaultWindowWouldMissFocal": None,
        "maxHoursBack": MAX_HISTORY_HOURS,
        "requestedBeyondMaxLookback": False,
        "successfulRequestNotProofOfSourceRetention": True,
    }
    if target is None:
        return result
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    clock = clock.astimezone(timezone.utc)
    age_seconds = max(0.0, (clock-target).total_seconds())
    hours_back = max(
        DEFAULT_HISTORY_HOURS,
        required_history_hours_absolute(
            target - timedelta(seconds=20), now=clock
        ),
    )
    result.update({
        "status": "anchor-in-future" if target > clock
                  else "historical-anchor-resolved",
        "requestedEventUtc": target.isoformat(),
        "ageHoursAtRequest": round(age_seconds/3600, 3),
        "hoursBackRequested": min(hours_back, MAX_HISTORY_HOURS),
        "expandedBeyondDefault": hours_back > DEFAULT_HISTORY_HOURS,
        "defaultWindowWouldMissFocal": age_seconds > DEFAULT_HISTORY_HOURS*3600,
        "requestedBeyondMaxLookback": age_seconds + 20 > MAX_HISTORY_HOURS*3600,
        "earliestRequestedNativeTimestampUtc": (
            clock - timedelta(hours=hours_back)
        ).isoformat(),
    })
    return result


__all__ = ["explicit_focal_history_lookback"]

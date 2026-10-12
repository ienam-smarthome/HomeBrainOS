"""Bounded authoritative MCP window reads for historical causal sensor evidence.

These probes can recover events excluded by HomeBrain's newest-N page, but
cannot recover anything removed from Hubitat's underlying event store.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _parse_time(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def build_focal_sensor_window_probe(
    spec: dict[str, Any],
    focal_boundary: Any,
    *, minutes_before: int = 5, minutes_after: int = 2,
) -> dict[str, Any] | None:
    """Return a bounded, read-only request for a known sensor ID and attribute."""
    target = _parse_time(focal_boundary)
    if target is None:
        return None
    candidate = spec.get("candidate") or {}
    if not isinstance(candidate, dict):
        return None
    device_id = str(candidate.get("id") or "").strip()
    attribute = str(spec.get("attribute") or "").strip()
    if not device_id.isdigit() or attribute not in {"motion", "presence"}:
        return None
    start = target - timedelta(minutes=max(1, min(10, minutes_before)))
    end = target + timedelta(minutes=max(1, min(5, minutes_after)))
    return {
        "deviceId": device_id,
        "attribute": attribute,
        "since": start.isoformat(timespec="milliseconds"),
        "until": end.isoformat(timespec="milliseconds"),
        "limit": 100,
    }


def verify_windowed_sensor_reply(
    request: dict[str, Any],
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Accept events only when the server proves both requested window bounds.

    Older servers may ignore unknown since/until parameters. An unverified
    response cannot be promoted into focal historical evidence.
    """
    if not isinstance(result, dict):
        return {"status": "unavailable", "events": []}
    if result.get("success") is False or result.get("isError") is True:
        return {"status": "unavailable", "events": []}
    expected_start = _parse_time(request.get("since"))
    expected_end = _parse_time(request.get("until"))
    server_start = _parse_time(result.get("sinceTimestamp"))
    server_end = _parse_time(result.get("untilTimestamp"))
    server_id = result.get("deviceId")
    if (
        not expected_start or not expected_end or not server_start or not server_end
        or str(result.get("sinceMode") or "") != "explicit"
        or server_start.astimezone(timezone.utc) != expected_start.astimezone(timezone.utc)
        or server_end.astimezone(timezone.utc) != expected_end.astimezone(timezone.utc)
        or (server_id is not None and str(server_id) != str(request.get("deviceId")))
    ):
        return {"status": "unsupported-or-unverified-window", "events": []}
    rows = result.get("events")
    if not isinstance(rows, list):
        return {"status": "invalid-events", "events": []}
    accepted = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("name") or "") != request["attribute"]:
            continue
        stamp = _parse_time(row.get("date"))
        if stamp is None or not expected_start < stamp <= expected_end:
            continue
        accepted.append(row)
    return {
        "status": "verified-window",
        "events": accepted,
        "returned": len(rows),
        "verifiedRows": len(accepted),
        "windowSupported": True,
        "sourceHistoryComplete": False,
    }


def merge_windowed_sensor_history(
    history: dict[str, Any], probe: dict[str, Any],
) -> dict[str, Any]:
    """Merge verified source observations; preserve pre-existing newer rows."""
    if probe.get("status") != "verified-window":
        return dict(history)
    combined = {}
    for row in [
        *(history.get("events") or []),
        *(probe.get("events") or []),
    ]:
        if isinstance(row, dict):
            key = (str(row.get("name")), str(row.get("date")), str(row.get("value")))
            combined[key] = row
    merged = dict(history)
    merged["events"] = list(combined.values())
    merged["windowedEvidenceVerified"] = True
    merged["windowedEventsRecovered"] = len(probe.get("events") or [])
    return merged


__all__ = [
    "build_focal_sensor_window_probe", "verify_windowed_sensor_reply",
    "merge_windowed_sensor_history",
]

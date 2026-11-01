"""Stage 8.3: privacy-preserving one-device archive timeline projection.

Historical Journal source rows are NOT proof of full event coverage or
physical command execution. This is a pure, source-bounded projection, never
a model inference, event backfill, or newly captured stream.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

_EVENT_STATE = {
    "switch": frozenset({"on", "off"}),
    "motion": frozenset({"active", "inactive"}),
    "presence": frozenset({"present", "not present"}),
    "level": None,
    "power": None,
}
_MAX_EVENTS = 50


def _valid_timestamp(value: Any) -> str | None:
    if type(value) is not str or not 10 <= len(value) <= 40:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _status_value(attribute: str, value: Any) -> str | float | None:
    if attribute in ("switch", "motion", "presence"):
        if type(value) is str and value.strip().lower() in _EVENT_STATE[attribute]:
            return value.strip().lower()
        return None
    if attribute in ("level", "power") and type(value) in (str, int, float):
        try:
            number = float(value)
        except (ValueError, TypeError):
            return None
        if number != number or not -1e5 <= number <= 1e5:
            return None
        return number
    return None


def project_shadow_history(device_id: str, archive: Any, *,
                           window_start: str, window_end: str,
                           read_at: str) -> dict[str, Any]:
    if type(device_id) is not str or not device_id.isascii() or not device_id.isdecimal() or not 1 <= len(device_id) <= 12:
        raise ValueError("invalid device id")
    if not all(_valid_timestamp(v) for v in (window_start, window_end, read_at)):
        raise ValueError("invalid timestamp")
    baseline = {
        "schema": "homebrain-live-shadow-journal.v1",
        "target_device_id": device_id,
        "read_at_utc": read_at,
        "requested_window_start": window_start,
        "requested_window_end": window_end,
        "source": "local_historical_journal",
        "source_is_live_device_query": False,
        "cloud_requests": 0,
        "device_commands": 0,
        "publisher_approval": False,
        "history_complete": False,
        "missing_events_prove_inactivity": False,
        "physical_execution_verified": False,
        "causal_attribution_verified": False,
        "events": [],
        "collection_gaps": [],
        "limitations": [
            "This query reads only previously collected journal rows.",
            "Missing events may reflect collection gaps, unavailable source histories or retention.",
            "Source timestamps and collector receipt times are not interchangeable.",
            "A reported state does not prove physical actuator behaviour or command causation.",
        ],
    }
    if type(archive) is not dict or type(archive.get("events")) is not list or type(archive.get("gaps")) is not list:
        return {**baseline, "status": "blocked_archive_shape"}
    if len(archive["events"]) > _MAX_EVENTS or archive.get("offset") != 0:
        return {**baseline, "status": "blocked_unbounded_archive_page"}
    cleaned = []
    for row in archive["events"]:
        if type(row) is not dict or row.get("stream") != "events" or str(row.get("device_id")) != device_id:
            continue
        attribute = row.get("attribute")
        if type(attribute) is not str or attribute not in _EVENT_STATE:
            continue
        val = _status_value(attribute, row.get("value"))
        receipt = _valid_timestamp(row.get("received_at"))
        event_at = _valid_timestamp(row.get("observed_at"))
        source_time = _valid_timestamp(row.get("source_time"))
        if val is None or receipt is None or event_at is None:
            continue
        cleaned.append({
            "attribute": attribute, "reported_value": val,
            "observed_at_utc": event_at,
            "received_at_utc": receipt,
            "source_time_utc": source_time,
            "timestamp_basis": ("source_declared_not_authenticated"
                                if source_time else "collector_only"),
        })
    gaps = []
    for gap in archive["gaps"][:50]:
        if type(gap) is not dict or gap.get("stream") != "events":
            continue
        start = _valid_timestamp(gap.get("started_at"))
        end = _valid_timestamp(gap.get("ended_at"))
        if start:
            gaps.append({"started_at_utc": start, "ended_at_utc": end,
                         "open_gap": end is None})
    baseline["events"] = cleaned
    baseline["collection_gaps"] = gaps
    baseline["returned_event_count"] = len(cleaned)
    baseline["archive_has_more"] = archive.get("has_more") is True
    baseline["status"] = "bounded_archive_evidence"
    return baseline


__all__ = ["project_shadow_history"]

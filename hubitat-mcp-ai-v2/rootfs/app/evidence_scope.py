"""Generic scope notes for native MCP event-history responses.

Notes describe only RETURNED rows and the request parameters. They never infer
the cause of missing records, a historic device state, or completeness of a
native store. Original MCP results remain intact in the client-side envelope.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _payload(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    content = value.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                continue
            try:
                inner = json.loads(part["text"])
            except ValueError:
                continue
            if isinstance(inner, dict) and isinstance(inner.get("events"), list):
                return inner
    return value if isinstance(value.get("events"), list) else None


def _normalized_date(value: str):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def scope_of(result: dict, arguments: dict | None = None) -> dict | None:
    """Derive only observational metadata, never conclusions about cause."""
    if not isinstance(result, dict) or result.get("isError"):
        return None
    source = _payload(result)
    if source is None:
        return None
    rows = source["events"]
    times = [
        (dt, row["date"])
        for row in rows if isinstance(row, dict) and isinstance(row.get("date"), str)
        if (dt := _normalized_date(row["date"])) is not None
    ]
    args = arguments if isinstance(arguments, dict) else {}
    leaf = args.get("args") if isinstance(args.get("args"), dict) else args
    limit = leaf.get("limit") if type(leaf.get("limit")) is int else None
    result_scope = {
        "source_scope": "returned event rows only",
        "events_returned": len(rows),
        "oldest_returned_event": min(times)[1] if times else None,
        "newest_returned_event": max(times)[1] if times else None,
        "date_rows_without_parseable_offset": sum(
            1 for row in rows if isinstance(row, dict) and isinstance(row.get("date"), str)
            and _normalized_date(row["date"]) is None
        ),
        "requested_lookback_hours": leaf.get("hoursBack") if type(leaf.get("hoursBack")) is int else None,
        "requested_limit": limit,
        "limit_reached": len(rows) >= limit if limit is not None else None,
        "native_store_checked_independently": False,
        "can_infer_older_events_absent": False,
        "can_infer_requested_window_fully_covered": False,
        "can_infer_cause_of_missing_records": False,
        "note": (
            "The query window, first returned timestamp, count, and limit describe "
            "only the rows that the source returned. They do not establish the "
            "oldest event in the native store, absence of earlier events, or a "
            "retention/truncation/transport cause. Where the distinction matters, "
            "seek a discriminating source or mark the cause unverified."
        ),
    }
    # An upstream-provided truncation flag has distinct meaning from an inferred
    # cap; preserve the source claim without deriving a causal explanation.
    for key in ("truncated", "hasMore", "matchedCount", "timeFilterUnparseable"):
        if key in source and isinstance(source[key], (bool, int)):
            result_scope["upstream_" + key] = source[key]
    return result_scope


def model_result_with_scope(result: dict, arguments: dict | None = None) -> dict:
    """Retain exact original payload under its original keys plus a separate note."""
    info = scope_of(result, arguments)
    if info is None:
        return result
    return {**result, "client_event_source_scope": info}

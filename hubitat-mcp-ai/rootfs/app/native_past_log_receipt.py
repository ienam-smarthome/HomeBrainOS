"""Privacy-safe proof of actual returned Hubitat past-log rows.

The native MCP hub_get_logs(mode="past") response contains entries with
time (usually hub-local), type, name and message. It is not the current
apps runtime-statistics tab. The model may read the native tool result,
but public API evidence receipts must not publish private messages.

This module certifies returned row presence, not historic completeness,
retention, absolute UTC source times or causal significance.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_MAX_SCAN = 200
_MAX_ID_SUMMARY = 12
_SOURCE_PREFIX = re.compile(r"^(app|dev)\|([1-9][0-9]{0,11})\|")
_LOCAL_CLOCK = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$"
)


def _timestamp_present(row: dict[str, Any]) -> bool:
    stamp = row.get("time")
    if not isinstance(stamp, str) or not stamp.strip():
        return False
    # Hubitat past-log timestamp strings may be hub-local, without a zone.
    # Parse for structural validity only. Never compare to UTC bounds without
    # a source-confirmed Hubitat timezone.
    stamp = stamp.strip()
    if not _LOCAL_CLOCK.fullmatch(stamp):
        return False
    try:
        datetime.fromisoformat(stamp)
        return True
    except ValueError:
        return False


def native_past_log_receipt(
    gateway: str, arguments: dict[str, Any], data: Any
) -> dict[str, Any] | None:
    """Project bounded typed rows and pagination metadata; no raw message text.

    Only an authenticated successful read-only execution should call this.
    A returned page without timestamps, source identity or messages does not
    support a positive verified message-row count.
    """
    if (gateway != "hub_get_logs"
            and arguments.get("tool") != "hub_get_logs"):
        return None
    inner = arguments.get("args") if isinstance(arguments.get("args"), dict) else arguments
    if not isinstance(inner, dict) or inner.get("mode", "past") != "past":
        return None
    if not isinstance(data, dict) or data.get("mode") != "past":
        return None
    entries = data.get("entries")
    if not isinstance(entries, list):
        return None

    message_rows = 0
    app_rows = 0
    device_rows = 0
    source_time_rows = 0
    app_ids: set[str] = set()
    device_ids: set[str] = set()

    for row in entries[:_MAX_SCAN]:
        if not isinstance(row, dict):
            continue
        if not _timestamp_present(row):
            continue
        source_time_rows += 1
        message = row.get("message")
        if not isinstance(message, str) or not message.strip():
            continue
        message_rows += 1
        # Upstream native past-log rows normally remove sourceId but retain
        # the original app|id|name|body marker in the message. Refuse to
        # invent an app identity from a display name or free-form text.
        match = _SOURCE_PREFIX.match(message.strip())
        if not match:
            continue
        source_kind, source_id = match.groups()
        row_type = str(row.get("type") or "").casefold()
        if source_kind == "app" and row_type == "app":
            app_rows += 1
            app_ids.add(source_id)
        elif source_kind == "dev" and row_type in {"device", "dev"}:
            device_rows += 1
            device_ids.add(source_id)

    def count(key: str) -> int | None:
        n = data.get(key)
        return n if type(n) is int and 0 <= n <= 1_000_000 else None

    result: dict[str, Any] = {
        "nativePastLog": {
            "returnedRowsInspected": min(len(entries), _MAX_SCAN),
            "returnedRowsCapped": len(entries) > _MAX_SCAN,
            "timestampedRows": source_time_rows,
            "timestampedMessageRows": message_rows,
            "appMessageRowsWithVerifiedSourceId": app_rows,
            "deviceMessageRowsWithVerifiedSourceId": device_rows,
            "appSourceIds": sorted(app_ids, key=int)[:_MAX_ID_SUMMARY],
            "deviceSourceIds": sorted(device_ids, key=int)[:_MAX_ID_SUMMARY],
            "sourceIdSummaryCapped": (
                len(app_ids) > _MAX_ID_SUMMARY or len(device_ids) > _MAX_ID_SUMMARY
            ),
            "timeBasis": "hub_local_source_time_not_utc_verified",
            "hasNextCursor": data.get("nextCursor") is not None,
            "responseTruncated": data.get("truncated") is True,
            "requestDateBounded": bool(
                inner.get("since") not in (None, "")
                and inner.get("until") not in (None, "")
            ),
            "completeHistoricalCoverageVerified": False,
        },
    }
    summary = result["nativePastLog"]
    for key, out_key in (
        ("count", "returnedPageCount"),
        ("matched", "matchedRowsReported"),
        ("total", "sourceRowsReported"),
        ("timeFilterUnparseable", "timeFilterUnparseable"),
    ):
        value = count(key)
        if value is not None:
            summary[out_key] = value
    return result


__all__ = ["native_past_log_receipt"]

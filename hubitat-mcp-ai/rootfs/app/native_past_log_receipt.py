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
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

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


def _absolute_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def past_log_request_scope(row: Any) -> dict[str, Any] | None:
    """Normalize an executed past-log request, not returned event coverage.

    The native contract defaults omitted mode to past. Never invent an until
    time from execution time, source rows or model text. Invalid/one-sided
    bounds remain counted reads but cannot attest a focal bounded window.
    """
    if (not isinstance(row, Mapping) or row.get("success") is not True
            or row.get("mutates") is True
            or row.get("effect") not in (None, "read")):
        return None
    outer = row.get("arguments")
    if not isinstance(outer, Mapping):
        return None
    operation = row.get("sub_tool") or outer.get("tool") or row.get("tool")
    if operation != "hub_get_logs":
        return None
    args = outer.get("args", outer)
    if not isinstance(args, Mapping) or args.get("mode", "past") != "past":
        return None
    start, end = _absolute_time(args.get("since")), _absolute_time(args.get("until"))
    bounded = start is not None and end is not None and start <= end
    detail = row.get("details")
    native = detail.get("nativePastLog") if isinstance(detail, Mapping) else None
    native = native if isinstance(native, Mapping) else {}
    # Unknown source filter interpretation cannot attest that the requested
    # window was applied, even though the read itself really happened.
    filter_ok = native.get("timeFilterUnparseable") in (None, 0)
    app = str(args.get("appId") or "")
    device = str(args.get("deviceId") or "")
    return {
        "since": start, "until": end,
        "bounded": bounded and filter_ok,
        "app_scoped": app.isdecimal() and int(app) > 0,
        "device_scoped": device.isdecimal() and int(device) > 0,
        "supports_live_claim": row.get("supports_live_claim") is not False,
        "historical_completeness_verified": False,
    }


def summarize_past_log_requests(
    evidence: Sequence[Mapping[str, Any]], focal_time: str = "",
) -> dict[str, Any]:
    """Privacy-safe request counts; no private IDs, messages or absence proof."""
    focal = _absolute_time(focal_time)
    scopes = [scope for row in evidence[:200]
              if (scope := past_log_request_scope(row)) is not None]
    bounded = [scope for scope in scopes if scope["bounded"]]
    focal_scopes = [scope for scope in bounded if focal is not None
                    and scope["since"] <= focal <= scope["until"]
                    and scope["supports_live_claim"]]
    return {
        "past_log_requests": len(scopes),
        "bounded_log_requests": len(bounded),
        "unbounded_or_invalid_window_requests": len(scopes) - len(bounded),
        "app_scoped_log_requests": sum(scope["app_scoped"] for scope in scopes),
        "bounded_log_requests_covering_focal": len(focal_scopes),
        "bounded_app_log_requests_covering_focal": sum(
            scope["app_scoped"] for scope in focal_scopes),
        "historical_completeness_verified": False,
        "returned_focal_event_absence_verified": False,
    }


__all__ = ["native_past_log_receipt", "past_log_request_scope",
           "summarize_past_log_requests"]

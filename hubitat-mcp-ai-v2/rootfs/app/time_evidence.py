"""Read-only clock arithmetic and neutral timestamps for model-led V2 actions.

This module does not parse a user prompt, select a native tool/device/command,
schedule work, rewrite answers or claim the hub's clock was independently read.
"""
from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime, time as time_type, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

TOOL_NAME = "homebrain_read_clock"
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Read the CLIENT'S current clock and configured/native-reported hub timezone, "
            "with a structured, deterministic date/time-to-minutes calculation. "
            "This is not an independently measured hub clock. For a fixed date supply "
            "local_datetime (ISO local YYYY-MM-DDTHH:MM[:SS]) or instant (ISO with offset); "
            "for the next occurrence of a wall clock time supply time_of_day (HH:MM[:SS]). "
            "Nonexistent DST wall times are refused and ambiguous autumn times need fold. "
            "Client never parses the user's question to choose a target or command."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "local_datetime": {"type": "string", "description": "Explicit ISO date and local clock, no timezone offset"},
                "time_of_day": {"type": "string", "description": "Next wall-clock occurrence HH:MM or HH:MM:SS"},
                "instant": {"type": "string", "description": "Absolute ISO 8601 timestamp with explicit UTC offset or Z"},
                "fold": {"type": "integer", "enum": [0, 1],
                         "description": "Choose which occurrence of an ambiguous DST fall-back wall-clock time"},
            },
            "additionalProperties": False,
        },
    },
}
_CLOCK_TIME = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
_DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}(?::\d{2})?$")
_DEADLINE_FIELD = re.compile(
    r"^(?:pending[A-Za-z0-9_]*(?:until|at)|scheduled[A-Za-z0-9_]*(?:until|at|for)|"
    r"next[A-Za-z0-9_]*(?:run|action|at)|(?:deadline|dueAt|runAt|executeAt|blockAt|blockUntil))$",
    re.IGNORECASE,
)
_HUB_CLOCK_FIELD = frozenset(("hubTime", "hubTimestamp", "serverTime", "currentTime"))
_HUB_TZ_FIELD = frozenset(("timezone", "timeZone", "timezoneId", "timeZoneId", "hubTimezone"))


def _iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("An absolute instant must have a UTC offset or Z")
    return dt.astimezone(UTC)


def _iana(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("A valid IANA timezone is required") from None


def _local_target(naive: datetime, zone: ZoneInfo, fold: int | None) -> datetime:
    candidates = [naive.replace(tzinfo=zone, fold=x) for x in (0, 1)]
    valid = [x for x in candidates if x.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive]
    if not valid:
        raise ValueError("This local date/time does not exist in the timezone (DST transition)")
    if len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset() and fold is None:
        raise ValueError("Ambiguous local date/time requires fold=0 or fold=1")
    if fold is not None and fold not in (0, 1):
        raise ValueError("fold must be 0 or 1")
    choice = candidates[fold or 0]
    if choice not in valid:
        raise ValueError("Selected DST fold does not exist")
    return choice


def clock_facts(args: dict[str, Any], timezone_name: str = "Europe/London",
                *, now: datetime | None = None, timezone_source: str = "add-on configured timezone") -> dict:
    """Compute facts from structured model arguments, not user-request text."""
    if not isinstance(args, dict) or set(args) - {"local_datetime", "time_of_day", "instant", "fold"}:
        raise ValueError("Unexpected clock tool arguments")
    selected = [k for k in ("local_datetime", "time_of_day", "instant") if k in args]
    if len(selected) > 1:
        raise ValueError("Use exactly one target form")
    zone = _iana(timezone_name)
    current = (now or datetime.now(UTC))
    if current.tzinfo is None:
        raise ValueError("Clock must be timezone aware")
    current = current.astimezone(UTC)
    local = current.astimezone(zone)
    offset = local.utcoffset() or timedelta()
    answer = {
        "source": "client clock",
        "hub_clock_independently_read": False,
        "client_now_utc": current.isoformat(),
        "client_now_local": local.isoformat(),
        "hub_timezone": timezone_name,
        "hub_timezone_source": timezone_source,
        "utc_offset_seconds": int(offset.total_seconds()),
        "dst_active": bool(local.dst()),
    }
    if not selected:
        return answer
    key = selected[0]
    value = args[key]
    if not isinstance(value, str):
        raise ValueError("Target must be a text date/time")
    fold = args.get("fold")
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise ValueError("fold must be 0 or 1")
    if key == "instant":
        if fold is not None:
            raise ValueError("fold applies only to wall-clock targets")
        target = _iso(value).astimezone(zone)
    elif key == "local_datetime":
        if not _DATE_TIME.fullmatch(value):
            raise ValueError("local_datetime must be ISO YYYY-MM-DDTHH:MM[:SS]")
        target = _local_target(datetime.fromisoformat(value), zone, fold)
    else:
        if not _CLOCK_TIME.fullmatch(value):
            raise ValueError("time_of_day must be HH:MM[:SS]")
        parsed = time_type.fromisoformat(value)
        target = _local_target(datetime.combine(local.date(), parsed), zone, fold)
        if target.astimezone(UTC) <= current:
            target = _local_target(datetime.combine(local.date() + timedelta(days=1), parsed), zone, fold)
    delta = (target.astimezone(UTC) - current).total_seconds()
    answer["target"] = {
        "input_kind": key,
        "target_local": target.isoformat(),
        "target_utc": target.astimezone(UTC).isoformat(),
        "next_occurrence": key == "time_of_day",
        "seconds_ahead": delta,
        "whole_minutes_ahead": math.floor(delta / 60),
        "past": delta < 0,
        "too_imminent_under_60s": 0 <= delta < 60,
        "not_yet_due": delta > 0,
    }
    return answer


def native_document(value: Any) -> dict | None:
    """Extract the ORIGINAL native JSON object from MCP text envelopes."""
    if not isinstance(value, dict):
        return None
    content = value.get("content")
    if isinstance(content, list):
        for part in content[:4]:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                try:
                    parsed = json.loads(part["text"])
                except (ValueError, TypeError):
                    continue
                if isinstance(parsed, dict):
                    return parsed
    return value if "content" not in value else None


def hub_clock_source(name: str, value: dict) -> dict | None:
    """Recognise *only* explicit hub-info clock/timezone source fields."""
    if name != "hub_get_info":
        return None
    document = native_document(value)
    if not document:
        return None
    sources = [document]
    for key in ("hub", "info", "hubInfo"):
        if isinstance(document.get(key), dict):
            sources.append(document[key])
    outcome = {}
    for item in sources:
        for key in _HUB_TZ_FIELD:
            raw = item.get(key)
            if isinstance(raw, str):
                try:
                    _iana(raw)
                except ValueError:
                    continue
                outcome["timezone"] = raw
        for key in _HUB_CLOCK_FIELD:
            raw = item.get(key)
            if isinstance(raw, str):
                try:
                    outcome["hub_instant_utc"] = _iso(raw).isoformat()
                except ValueError:
                    pass
    return outcome or None


def deadline_facts(value: dict, *, now: datetime | None = None) -> dict | None:
    """Index only recognised native pending-deadline fields, never arbitrary dates.

    A state snapshot embedded in a write reply is NOT independent readback.
    """
    document = native_document(value)
    if not document:
        return None
    current = (now or datetime.now(UTC)).astimezone(UTC)
    def collect(obj: Any, depth: int = 0):
        if depth > 4 or not isinstance(obj, dict):
            return None
        for key, raw in obj.items():
            if _DEADLINE_FIELD.fullmatch(key) and isinstance(raw, str):
                try:
                    due = _iso(raw)
                except ValueError:
                    continue
                delta = (due - current).total_seconds()
                if delta > 0:
                    return {
                        "field": key,
                        "stored_deadline_utc": due.isoformat(),
                        "offset_from_client_now_seconds": round(delta, 3),
                        "offset_from_client_now_minutes": round(delta / 60, 3),
                        "source": "original native MCP response",
                        "independent_post_write_readback": False,
                    }
            if key in ("state", "attributes", "schedule", "result", "data", "pending"):
                match = collect(raw, depth + 1)
                if match is not None:
                    return match
        return None
    return collect(document)


def reported_hub_skew(source: dict | None, *, now: datetime | None = None,
                      threshold_seconds: float = 30) -> dict | None:
    if not isinstance(source, dict) or not isinstance(source.get("hub_instant_utc"), str):
        return None
    current = (now or datetime.now(UTC)).astimezone(UTC)
    delta = (_iso(source["hub_instant_utc"]) - current).total_seconds()
    if abs(delta) <= threshold_seconds:
        return None
    return {"source": "hub_get_info explicit timestamp compared with client clock",
            "hub_minus_client_seconds": round(delta, 3), "threshold_seconds": threshold_seconds,
            "clock_skew_unverified_until_source_freshness_checked": True}

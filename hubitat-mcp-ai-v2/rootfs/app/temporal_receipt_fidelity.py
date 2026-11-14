"""Bounded temporal navigation over ORIGINAL successful native event receipts.

No tool calls, model calls, causal classification or answer rewriting. This
audit aid re-exposes only safe, source-quoted clock/attribute/value pairs already
present in returned MCP data, and never asserts absence outside those rows.
"""
from __future__ import annotations

from datetime import datetime
import json
import re

_CLOCK = re.compile(r"(?<!\d)(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?!\d)")
_PRIVATE_FIELD = re.compile(
    r"passw|secret|token|credential|auth|pin|code|api.key|access.key|lock.code",
    re.IGNORECASE,
)
_SAFE_SCALAR = re.compile(
    r"(?:[-+]?\d+(?:\.\d+)?|true|false|on|off|open|closed|"
    r"active|inactive|idle|heating|cooling|heat|cool|unknown|"
    r"locked|unlocked|present|not.present|wet|dry)", re.IGNORECASE,
)
_MAX_RECEIPTS = 16
_MAX_SOURCE_EVENTS = 900
_MAX_CITED_CLOCKS = 18
_MAX_MATCHES = 4
_MAX_NEARBY = 3


def _native_payload(record: dict) -> dict | None:
    """Unwrap source text, never treating client annotations as raw events."""
    try:
        payload = json.loads(str(record.get("response", "")))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    inner = json.loads(str(item.get("text") or ""))
                except (TypeError, ValueError):
                    return None
                return inner if isinstance(inner, dict) else None
    return payload


def _safe_event(record: dict, receipt_number: int) -> dict | None:
    """Never copy descriptions, source logs, listeners or arbitrary values."""
    stamp, name = record.get("date"), record.get("name")
    if not isinstance(stamp, str) or not 0 < len(stamp) <= 48:
        return None
    if not isinstance(name, str) or not 0 < len(name) <= 64:
        return None
    if _PRIVATE_FIELD.search(name):
        return None
    try:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        return None
    clock_match = _CLOCK.search(stamp)
    if clock_match is None:
        return None
    result = {
        "receipt_number": receipt_number, "event_date_as_returned": stamp,
        "event_clock_as_returned": clock_match.group(0),
        "event_name": name,
    }
    raw = record.get("value")
    if type(raw) in (int, float, bool):
        value = str(raw).lower() if type(raw) is bool else str(raw)
    elif isinstance(raw, str):
        value = raw
    else:
        value = ""
    if 0 < len(value) <= 30 and _SAFE_SCALAR.fullmatch(value):
        result["event_value"] = value
    return result


def _seconds(clock: str) -> float:
    h, m, s = clock.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def temporal_receipt_fidelity_index(receipts: list[dict], draft: str) -> dict | None:
    """Build a small navigation aid around clocks the draft actually cites.

    An absent matching clock is a REVIEW CUE, never proof that the event did
    not occur, or that the cited clock is not a computed/hypothetical value.
    All original receipts remain authoritative; source selection is unchanged.
    """
    if not isinstance(draft, str) or not draft:
        return None
    cited = list(dict.fromkeys(_CLOCK.findall(draft[:24000])))
    if not cited:
        return None
    events = []
    omitted = 0
    for pos, receipt in enumerate(receipts[:_MAX_RECEIPTS], 1):
        if (not isinstance(receipt, dict)
                or receipt.get("success") is not True
                or receipt.get("name") != "hub_list_device_events"):
            continue
        original = _native_payload(receipt)
        if not isinstance(original, dict) or not isinstance(original.get("events"), list):
            continue
        for row in original["events"]:
            if len(events) >= _MAX_SOURCE_EVENTS:
                omitted += 1
                continue
            if not isinstance(row, dict):
                continue
            safe = _safe_event(row, pos)
            if safe is not None:
                events.append(safe)
    if not events:
        return None

    anchors = []
    for clock in cited[:_MAX_CITED_CLOCKS]:
        matched = [row for row in events if (
            row["event_clock_as_returned"] == clock
            or ("." not in clock and row["event_clock_as_returned"].startswith(clock + "."))
        )]
        clock_seconds = _seconds(clock)
        nearby = sorted(
            (row for row in events if row not in matched),
            key=lambda row: abs(_seconds(row["event_clock_as_returned"]) - clock_seconds)
        )
        nearby = [row for row in nearby
                  if abs(_seconds(row["event_clock_as_returned"]) - clock_seconds) <= 120]
        anchors.append({
            "draft_cited_clock": clock,
            "exact_returned_event_clock_found": bool(matched),
            "matching_returned_event_rows": matched[:_MAX_MATCHES],
            "other_matching_rows_omitted": max(0, len(matched) - _MAX_MATCHES),
            "nearby_returned_event_rows_not_a_match": nearby[:_MAX_NEARBY],
        })
    return {
        "source_scope": "only native event rows already returned in this request",
        "warning": (
            "These are navigation anchors, not independent evidence or a "
            "claim-verdict engine. A missing clock match does NOT prove an "
            "event absent; clocks may be derived or outside returned rows. "
            "Check full DATE, event NAME, value, timezone, scope and timing "
            "against ORIGINAL receipts before attributing an observation."
        ),
        "returned_event_rows_indexed": len(events),
        "source_rows_omitted_due_to_cap": omitted,
        "draft_clocks_not_indexed_due_to_cap": max(0, len(cited) - _MAX_CITED_CLOCKS),
        "draft_clock_anchors": anchors,
    }

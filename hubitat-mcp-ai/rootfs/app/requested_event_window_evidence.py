"""Source-bounded rolling-window evidence for final model synthesis.

The tool may retrieve one hour to satisfy a thirty-minute question. Never
promote events or aggregate intervals outside the user's requested window into
events 'in the last N minutes'. This is read-only source context, not a new
model route, mutation permission, or final-answer template.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

_ROLLING = re.compile(
    r"\b(?:last|past|previous)\s+(?P<count>\d{1,4})\s*"
    r"(?P<unit>minutes?|mins?|hours?|hrs?|days?)\b",
    re.IGNORECASE,
)
_STATES = frozenset(("motion", "presence", "contact", "switch", "power", "acceleration", "water", "temperature", "humidity", "illuminance"))
_SAFE_VALUE = re.compile(r"^[a-zA-Z0-9 .:+_-]{1,32}$")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _duration_seconds(prompt: str) -> tuple[int, str] | None:
    match = _ROLLING.search(prompt or "")
    if not match:
        return None
    count = int(match.group("count"))
    unit = match.group("unit").lower()
    factor = 60 if unit.startswith(("min",)) else 3600 if unit.startswith(("h",)) else 86400
    seconds = count * factor
    if not 60 <= seconds <= 7 * 86400:
        return None
    return seconds, f"last {count} {unit}"


def render_requested_event_window_evidence(
    question: str, receipts: list[dict[str, Any]],
) -> str | None:
    """Constrain timed source assertions to the explicit user rolling window.

    A missing event in returned rows is NOT proof of no detection, missing
    upstream telemetry, or a physical absence. 'physical' event type and
    producedBy bridge identify reporting metadata, not upstream cause.
    """
    parsed = _duration_seconds(question)
    if parsed is None:
        return None
    seconds, label = parsed
    rows: list[dict[str, Any]] = []
    for receipt in receipts:
        if (not isinstance(receipt, dict)
                or receipt.get("success") is not True
                or receipt.get("effect") != "read"
                or receipt.get("evidence_kind") != "deterministic_device_event_history"):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict) or not isinstance(details.get("observedEvents"), list):
            continue
        attr = details.get("attribute")
        if not isinstance(attr, str) or attr not in _STATES:
            continue
        timestamp = _utc(receipt.get("timestamp"))
        if timestamp is None:
            continue
        source_events = []
        for event in details["observedEvents"][:250]:
            if not isinstance(event, dict) or event.get("name") != attr:
                continue
            when = _utc(event.get("date"))
            raw = event.get("value")
            val = str(raw) if isinstance(raw, (str, int, float)) and not isinstance(raw, bool) else ""
            if when is None or not _SAFE_VALUE.fullmatch(val):
                continue
            source_events.append((when, val))
        rows.append({
            "attr": attr,
            "asof": timestamp,
            "events": source_events,
            "integrity": details.get("historySourceIntegrityVerified") is True,
            "source_count": details.get("sourceEventCount"),
            "truncated": details.get("observedEventsTruncated") is True,
            "label": str(details.get("label") or ""),
        })
    if not rows:
        return None
    # Never collapse multiple unrelated targets into one time window result.
    targets = {row["label"].casefold() for row in rows}
    if len(targets) != 1 or "" in targets:
        return None
    asof = max(row["asof"] for row in rows)
    start = asof - timedelta(seconds=seconds)
    lines = [
        "HOST USER-REQUESTED ROLLING WINDOW EVIDENCE (source read-only; no tool calls):",
        f"- The user specifically requested {label}; use the window "
        f"{start.isoformat()} through {asof.isoformat()} UTC (as of the retained read).",
        "- Tool history may cover LONGER than the user asked. NEVER count "
        "earlier events, pairs or intervals as occurring in this window.",
    ]
    for row in sorted(rows, key=lambda x: x["attr"]):
        # De-duplicate identical source reports without assuming missing rows.
        distinct = sorted(set(row["events"]), key=lambda p: p[0])
        inside = [(t, v) for t, v in distinct if start <= t <= asof]
        earlier = [(t, v) for t, v in distinct if t < start]
        future = [(t, v) for t, v in distinct if t > asof]
        kind = row["attr"]
        lines.append(
            f"- Returned {kind} events WITHIN the requested window: "
            f"{len(inside)}. Returned events BEFORE the requested window: "
            f"{len(earlier)}."
        )
        if inside:
            first, last = inside[0], inside[-1]
            lines.append(
                f"- First/last returned in-window {kind} reports: "
                f"{first[0].isoformat()} ({first[1]}) and "
                f"{last[0].isoformat()} ({last[1]})."
            )
        if earlier:
            latest = earlier[-1]
            lines.append(
                f"- Latest returned {kind} report BEFORE the requested window: "
                f"{latest[0].isoformat()} ({latest[1]}). "
                "This is CONTEXT, not activity in the requested window."
            )
        if future:
            lines.append(
                f"- {len(future)} source events fall after the recorded read "
                "timestamp; do not silently fold them into the requested window."
            )
        if not row["integrity"]:
            lines.append(
                "- Source history integrity was NOT independently verified; "
                "zero returned events means no events IN THIS RETURNED PAGE, "
                "not proof of no real detection, continuous inactivity or "
                "complete physical coverage."
            )
        if row["truncated"]:
            lines.append(
                "- Returned event list is truncated; source coverage is incomplete."
            )
    lines.append(
        "- Event type='physical' or producedBy a Matter bridge is a reported "
        "origin/transport label, NOT independent proof the hardware initiated "
        "a transition. triggered[] identifies listeners, NOT command issuers. "
        "A device history without command rows does NOT prove no automation "
        "command was sent elsewhere."
    )
    return "\n".join(lines)


__all__ = ["render_requested_event_window_evidence"]

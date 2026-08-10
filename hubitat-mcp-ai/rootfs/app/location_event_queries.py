"""Pure parsing/filtering/presentation helpers for Hubitat location events.

Location events are the hub's own mode changes, sunrise/sunset markers, HSM
status, and hub-variable changes -- reported by ``hub_list_device_events``
when called with both ``deviceId`` and ``appId`` omitted (confirmed live:
the same "Hub C8 Pro is now in <Mode> mode" rows the hub's own Logs >
Location events page shows). These helpers stay pure/testable the same way
``contact_history_queries.py`` does for device contact events -- no network
calls, no agent state.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from contact_history_queries import parse_event_datetime
from natural_datetime import format_natural_datetime

_MODE_EVENT_NAME = "mode"

_LOCATION_EVENTS_LIST = re.compile(
    r"^\s*(?:please\s+)?show\s+(?:me\s+)?(?:the\s+)?"
    r"(?:recent\s+)?(?:mode\s+(?:changes|history)|location\s+events)\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?(?:recent\s+)?(?:mode\s+(?:changes|history)|location\s+events)\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?what\s+mode\s+changes\s+happened\s+today\s*[?.!]*\s*$",
    re.I,
)

_MODE_LAST_ENTERED = re.compile(
    r"^\s*(?:please\s+)?when\s+did\s+(?:we|the\s+hub)\s+last\s+enter\s+"
    r"(?P<mode>.+?)\s+mode\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?when\s+was\s+(?P<mode2>.+?)\s+mode\s+last\s+active\s*[?.!]*\s*$"
    r"|^\s*(?:please\s+)?when\s+did\s+the\s+mode\s+last\s+change\s+to\s+"
    r"(?P<mode3>.+?)\s*[?.!]*\s*$",
    re.I,
)


def parse_location_events_intent(prompt: str) -> bool:
    """True for a request to list recent location events (mode changes)."""

    return _LOCATION_EVENTS_LIST.fullmatch(str(prompt).strip()) is not None


def parse_mode_last_entered(prompt: str) -> str | None:
    """Extract the mode name from "when did we last enter <Mode> mode" and
    close variants. Returns None for anything else.
    """

    match = _MODE_LAST_ENTERED.fullmatch(str(prompt).strip())
    if match is None:
        return None
    mode = match.group("mode") or match.group("mode2") or match.group("mode3")
    return mode.strip() if mode and mode.strip() else None


def mode_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter raw location events down to mode-change rows only."""

    return [
        item
        for item in events
        if str(item.get("name") or "").casefold() == _MODE_EVENT_NAME
        and str(item.get("value") or "").strip()
    ]


def mode_active_before(
    events: list[dict[str, Any]],
    *,
    reference_timestamp: str,
) -> dict[str, Any] | None:
    """Return the most recent mode-change event at or before a reference
    timestamp -- i.e. "what mode was active when this other event fired."

    Returns None if the reference timestamp can't be parsed or no mode
    event was reported at or before it (the events window the caller
    fetched may simply not reach back far enough).
    """

    reference = parse_event_datetime(reference_timestamp)
    if reference is None:
        return None
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for item in mode_events(events):
        parsed = parse_event_datetime(item.get("date"))
        if parsed is not None and parsed <= reference:
            candidates.append((parsed, item))
    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]


def find_mode_last_entered(
    events: list[dict[str, Any]],
    *,
    mode_name: str,
) -> dict[str, Any] | None:
    """Return the most recent mode-change event whose value matches
    ``mode_name`` (case-insensitive), or None if it never appears in the
    events window the caller fetched.
    """

    target = mode_name.strip().casefold()
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for item in mode_events(events):
        if str(item.get("value") or "").casefold() != target:
            continue
        parsed = parse_event_datetime(item.get("date"))
        if parsed is not None:
            candidates.append((parsed, item))
    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]


def present_location_events(events: list[dict[str, Any]]) -> str:
    """Format a newest-first list of mode-change events for a direct query."""

    changes = mode_events(events)
    if not changes:
        return "No mode changes were reported in that window."
    lines = ["Recent mode changes:"]
    for item in changes:
        value = str(item.get("value") or "").strip()
        lines.append(f"- {value} at {format_natural_datetime(item.get('date'))}")
    return "\n".join(lines)


def present_mode_last_entered(mode_name: str, event: dict[str, Any] | None) -> str:
    if event is None:
        return f'No "{mode_name}" mode change was reported in that window.'
    value = str(event.get("value") or mode_name).strip()
    return f"The hub last entered {value} mode at {format_natural_datetime(event.get('date'))}."


def present_mode_at_time(event: dict[str, Any] | None) -> str | None:
    """Format a short clause describing the mode active at another event's
    timestamp, for appending to an unrelated device-history answer. Returns
    None if no mode event is available to cite (caller must not fabricate
    a mode in that case).
    """

    if event is None:
        return None
    value = str(event.get("value") or "").strip()
    if not value:
        return None
    return f"{value} mode"


__all__ = [
    "find_mode_last_entered",
    "mode_active_before",
    "mode_events",
    "parse_location_events_intent",
    "parse_mode_last_entered",
    "present_location_events",
    "present_mode_at_time",
    "present_mode_last_entered",
]

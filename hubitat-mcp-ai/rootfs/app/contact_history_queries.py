from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from natural_datetime import format_natural_datetime


@dataclass(frozen=True, slots=True)
class HistoryReference:
    label: str
    state: str
    timestamp: str


_COUNT_YESTERDAY = re.compile(
    r"^\s*how\s+many\s+times\s+did\s+(?P<name>.+?)\s+"
    r"(?P<state>open|close|closed)\s+yesterday\s*[?.!]*\s*$",
    re.I,
)
_LIST_YESTERDAY = re.compile(
    r"^\s*show\s+(?:me\s+)?only\s+(?P<name>.+?)\s+contact\s+events\s+"
    r"from\s+yesterday\s*[?.!]*\s*$",
    re.I,
)
_BEFORE_THAT = re.compile(
    r"^\s*when\s+did\s+(?P<name>.+?)\s+(?P<state>open|close|closed)\s+"
    r"before\s+that\s*[?.!]*\s*$",
    re.I,
)


def literal_device_name(name: str) -> str:
    return re.sub(r"^(?:the|a|an)\s+", "", name.strip(), flags=re.I)


def normalise_state(value: str) -> str:
    return "closed" if value.casefold().startswith("clos") else "open"


def parse_count_yesterday(prompt: str) -> tuple[str, str] | None:
    match = _COUNT_YESTERDAY.fullmatch(prompt)
    if match is None:
        return None
    return literal_device_name(match.group("name")), normalise_state(match.group("state"))


def parse_list_yesterday(prompt: str) -> str | None:
    match = _LIST_YESTERDAY.fullmatch(prompt)
    if match is None:
        return None
    return literal_device_name(match.group("name"))


def parse_before_that(prompt: str) -> tuple[str, str] | None:
    match = _BEFORE_THAT.fullmatch(prompt)
    if match is None:
        return None
    return literal_device_name(match.group("name")), normalise_state(match.group("state"))


def parse_event_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def yesterday_bounds(now: datetime) -> tuple[datetime, datetime]:
    local_now = now.astimezone()
    start_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_today - timedelta(days=1), start_today


def contact_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in events
        if str(item.get("name") or "").casefold() == "contact"
        and str(item.get("value") or "").casefold() in {"open", "closed"}
    ]


def events_in_window(
    events: list[dict[str, Any]],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in contact_events(events):
        parsed = parse_event_datetime(item.get("date"))
        if parsed is not None and start <= parsed.astimezone(start.tzinfo) < end:
            selected.append(item)
    return selected


def find_before_reference(
    events: list[dict[str, Any]],
    *,
    state: str,
    reference_timestamp: str,
) -> dict[str, Any] | None:
    reference = parse_event_datetime(reference_timestamp)
    if reference is None:
        return None
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for item in contact_events(events):
        if str(item.get("value") or "").casefold() != state:
            continue
        parsed = parse_event_datetime(item.get("date"))
        if parsed is not None and parsed < reference:
            candidates.append((parsed, item))
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def present_count(label: str, state: str, count: int) -> str:
    verb = "opened" if state == "open" else "closed"
    suffix = "time" if count == 1 else "times"
    return f"{label} {verb} {count} {suffix} yesterday."


def present_yesterday_events(label: str, events: list[dict[str, Any]]) -> str:
    if not events:
        return f"No contact events were reported for {label} yesterday."
    lines = [f"{label} contact events yesterday:"]
    for item in events:
        state = str(item.get("value") or "").casefold()
        verb = "Opened" if state == "open" else "Closed"
        lines.append(f"- {verb} at {format_natural_datetime(item.get('date'))}")
    return "\n".join(lines)


__all__ = [
    "HistoryReference",
    "contact_events",
    "events_in_window",
    "find_before_reference",
    "parse_before_that",
    "parse_count_yesterday",
    "parse_list_yesterday",
    "present_count",
    "present_yesterday_events",
    "yesterday_bounds",
]

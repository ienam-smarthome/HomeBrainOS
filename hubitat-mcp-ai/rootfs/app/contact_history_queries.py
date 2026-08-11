from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from natural_datetime import format_natural_datetime, normalize_iso_offset


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
_RELATIVE_THAT = re.compile(
    r"^\s*when\s+did\s+(?P<name>.+?)\s+(?P<state>open|close|closed)\s+"
    r"(?P<direction>before|after)\s+that\s*[?.!]*\s*$",
    re.I,
)
_PRONOUN_TARGETS = {"it", "that", "this", "the door", "the device"}


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


def parse_relative_that(prompt: str) -> tuple[str | None, str, str] | None:
    match = _RELATIVE_THAT.fullmatch(prompt)
    if match is None:
        return None
    raw_name = match.group("name").strip()
    name = None if raw_name.casefold() in _PRONOUN_TARGETS else literal_device_name(raw_name)
    return name, normalise_state(match.group("state")), match.group("direction").casefold()


def parse_before_that(prompt: str) -> tuple[str | None, str] | None:
    parsed = parse_relative_that(prompt)
    if parsed is None or parsed[2] != "before":
        return None
    return parsed[0], parsed[1]


def parse_after_that(prompt: str) -> tuple[str | None, str] | None:
    parsed = parse_relative_that(prompt)
    if parsed is None or parsed[2] != "after":
        return None
    return parsed[0], parsed[1]


def parse_event_datetime(value: Any) -> datetime | None:
    """Parse a raw Hubitat event timestamp, shared by this module and
    location_event_queries.py (which imports this function directly).

    Uses natural_datetime.normalize_iso_offset() for the same
    offset-without-colon normalization format_natural_datetime() applies --
    currently inert in practice (the deployed Python parses a trailing
    "+0100"-style offset natively), but this call site used to carry its
    own bare `.replace("Z", "+00:00")` with no such guard, a latent
    inconsistency against natural_datetime.py's fix if that Python-version
    reliance ever changes. Delegating to the shared helper keeps both call
    sites in exact agreement rather than drifting.
    """

    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
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


def find_relative_to_reference(
    events: list[dict[str, Any]],
    *,
    state: str,
    reference_timestamp: str,
    direction: str,
) -> dict[str, Any] | None:
    reference = parse_event_datetime(reference_timestamp)
    if reference is None:
        return None
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for item in contact_events(events):
        if str(item.get("value") or "").casefold() != state:
            continue
        parsed = parse_event_datetime(item.get("date"))
        if parsed is None:
            continue
        if direction == "before" and parsed < reference:
            candidates.append((parsed, item))
        elif direction == "after" and parsed > reference:
            candidates.append((parsed, item))
    if not candidates:
        return None
    selector = max if direction == "before" else min
    return selector(candidates, key=lambda pair: pair[0])[1]


def find_before_reference(
    events: list[dict[str, Any]],
    *,
    state: str,
    reference_timestamp: str,
) -> dict[str, Any] | None:
    return find_relative_to_reference(
        events,
        state=state,
        reference_timestamp=reference_timestamp,
        direction="before",
    )


def find_after_reference(
    events: list[dict[str, Any]],
    *,
    state: str,
    reference_timestamp: str,
) -> dict[str, Any] | None:
    return find_relative_to_reference(
        events,
        state=state,
        reference_timestamp=reference_timestamp,
        direction="after",
    )


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
    "find_after_reference",
    "find_before_reference",
    "find_relative_to_reference",
    "parse_after_that",
    "parse_before_that",
    "parse_count_yesterday",
    "parse_list_yesterday",
    "parse_relative_that",
    "present_count",
    "present_yesterday_events",
    "yesterday_bounds",
]

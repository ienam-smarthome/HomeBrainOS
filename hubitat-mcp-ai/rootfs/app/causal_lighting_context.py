"""Bounded, evidence-led context for proven lighting command attribution.

A producing app is a confirmed command source, not a confirmed sensor trigger.
These helpers turn existing command history into a short pattern explanation and
correlate only a specifically identified occupancy sensor with the focal edge.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from device_state_summary import device_attributes, room_name


def _time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if re.search(r"[+-]\d{4}$", raw):
        raw = raw[:-5] + raw[-5:-2] + ":" + raw[-2:]
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


def _clock(moment: datetime, zone: datetime) -> str:
    return moment.astimezone(zone.tzinfo).strftime("%H:%M:%S")


def _relevant_details(
    evidence: list[dict[str, Any]], subject: str
) -> dict[str, Any]:
    for receipt in reversed(evidence):
        if receipt.get("tool") != "homebrain_device_history":
            continue
        details = receipt.get("details")
        if (
            isinstance(details, dict)
            and str(details.get("label") or "").casefold() == subject.casefold()
            and isinstance(details.get("commandEvents"), list)
        ):
            return details
    return {}


def render_level_command_pattern(
    evidence: list[dict[str, Any]],
    focus: dict[str, Any],
) -> str | None:
    """Distinguish earlier activations from later dimming, without inferring a schedule."""

    details = _relevant_details(evidence, str(focus.get("subject") or ""))
    commands = details.get("commandEvents") or []
    # correlationEvents is the broadest subject switch sample, when provided.
    transitions = details.get("correlationEvents") or details.get("observedEvents") or []
    source_id = str((focus.get("producer") or {}).get("id") or "")
    focal_time = _time((focus.get("command") or {}).get("date"))
    focal_boundary = _time(focus.get("stateBoundary"))
    if not (source_id and focal_time and focal_boundary):
        return None

    on_edges, off_edges = [], []
    for event in transitions:
        if not isinstance(event, dict) or event.get("name") != "switch":
            continue
        when = _time(event.get("date"))
        if when is None:
            continue
        if event.get("value") == "on":
            on_edges.append(when)
        elif event.get("value") == "off":
            off_edges.append(when)

    earlier: dict[str, tuple[datetime, float]] = {}
    later: list[tuple[datetime, float]] = []
    for event in commands:
        if not isinstance(event, dict):
            continue
        producer = event.get("producedBy") or {}
        if str(producer.get("id") or "") != source_id:
            continue
        match = re.search(
            r"\bsetLevel\(\s*(\d+(?:\.\d+)?)",
            str(event.get("description") or ""),
            re.I,
        )
        when = _time(event.get("date"))
        if match is None or when is None:
            continue
        level = float(match.group(1))
        aligned = min(
            (edge for edge in on_edges if abs((edge - when).total_seconds()) <= 2.0),
            key=lambda edge: abs((edge - when).total_seconds()),
            default=None,
        )
        if aligned is not None and aligned < focal_boundary:
            key = aligned.isoformat()
            # Multiple identical commands around one ON boundary are one episode.
            previous = earlier.get(key)
            if previous is None or abs((aligned - when).total_seconds()) < abs(
                (aligned - previous[0]).total_seconds()
            ):
                earlier[key] = (when, level)
        elif when > focal_boundary and (when - focal_boundary).total_seconds() > 2:
            if (
                not any(focal_boundary < off <= when for off in off_edges)
                and (focus.get("open") or not focus.get("intervalEnd")
                     or (_time(focus.get("intervalEnd")) or when) >= when)
            ):
                later.append((when, level))

    lines: list[str] = []
    if earlier:
        examples = sorted(earlier.values(), key=lambda row: row[0])[-3:]
        snippets = [
            f"{_clock(when, focal_time)} ({level:g}%)"
            for when, level in examples
        ]
        lines.append(
            "**Earlier observed lighting commands:** " + ", ".join(snippets)
            + ". These are historical commands from the same app, not proof of"
            " which sensor triggered them."
        )
        levels = {value for _, value in examples}
        current_level = (focus.get("command") or {}).get("level")
        if current_level is not None:
            try:
                levels.add(float(current_level))
            except (TypeError, ValueError):
                pass
        if len(levels) > 1:
            lines.append(
                "Brightness varies between observed activations; a time-of-day"
                " schedule is plausible but not verified without the app settings."
            )
    if later:
        when, level = sorted(later, key=lambda item: item[0])[0]
        lines.append(
            f"**Later dimmer command:** At {_clock(when, focal_time)} the same app"
            f" issued setLevel({level:g}) during the observed ON interval;"
            " this is not another switch-on."
        )
    return "\n".join(lines) if lines else None


def choose_occupancy_event_sources(
    identities: list[dict[str, Any]],
    *,
    config_search: str,
    subject_room: str,
    limit: int = 2,
) -> list[tuple[dict[str, Any], str, bool]]:
    """Prefer exact configured occupancy references; otherwise one unambiguous
    same-room, explicitly named occupancy device. Never scan arbitrary sensors.
    """
    eligible: list[tuple[dict[str, Any], str, bool]] = []
    for item in identities:
        if not isinstance(item, dict):
            continue
        device_id = str(item.get("id") or item.get("deviceId") or "")
        name = str(item.get("label") or item.get("name") or "").strip()
        if not device_id.isdecimal() or not name:
            continue
        room = room_name(item)
        if not subject_room or not room or room.casefold() != subject_room.casefold():
            continue
        cap = {re.sub(r"[^a-z]", "", str(c).casefold())
               for c in item.get("capabilities") or []}
        attrs = {str(a).casefold() for a in device_attributes(item)}
        attribute = next(
            (a for a in ("occupancy", "motion", "presence") if a in attrs),
            None,
        )
        if attribute is None:
            if "motionsensor" in cap:
                attribute = "motion"
            elif "presencesensor" in cap:
                attribute = "presence"
        if attribute is None:
            continue
        configured = bool(config_search and name.casefold() in config_search.casefold())
        named_occupancy = bool(
            re.search(r"\b(?:occupancy|motion|presence|pir)\b", name, re.I)
        )
        if configured or named_occupancy:
            eligible.append((item, attribute, configured))
    configured_sources = [item for item in eligible if item[2]]
    if configured_sources:
        return configured_sources[:max(0, limit)]
    # Without configuration, multiple plausible sensors cannot be ranked
    # solely from their labels. Leave the precise trigger unidentified.
    return eligible[:1] if len(eligible) == 1 and limit > 0 else []


def render_occupancy_edge_correlation(
    focus: dict[str, Any],
    *,
    label: str,
    attribute: str,
    event_data: dict[str, Any],
) -> str | None:
    """Report a nearby active edge as correlation, never proven app input."""
    focus_time = _time(focus.get("stateBoundary"))
    if focus_time is None or not isinstance(event_data.get("events"), list):
        return None
    active = {
        "motion": {"active"},
        "presence": {"present"},
        "occupancy": {"occupied", "active", "true"},
    }.get(attribute, set())
    candidates = []
    for item in event_data["events"]:
        if not isinstance(item, dict):
            continue
        when = _time(item.get("date") or item.get("timestamp"))
        value = str(item.get("value") or "").strip().casefold()
        if when is None or value not in active:
            continue
        delta = (when - focus_time).total_seconds()
        if abs(delta) <= 2:
            candidates.append((abs(delta), delta, when))
    if not candidates:
        return None
    _, delta, when = min(candidates)
    relation = (
        f"{abs(delta):.2f}s before" if delta < 0
        else f"{abs(delta):.2f}s after" if delta > 0
        else "at the same instant as"
    )
    interpretation = (
        "It was reported after the light changed; this timing alone cannot"
        " establish that the sensor event triggered the app."
        if delta > 0 else
        "This is consistent with a possible occupancy trigger, but only"
        " the app's execution evidence can confirm the exact decision."
    )
    return (
        f"**Occupancy correlation:** {label} reported {attribute} active at "
        f"{_clock(when, focus_time)}, {relation} the light's ON transition. "
        + interpretation
    )

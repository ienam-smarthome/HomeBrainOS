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


def matched_occupancy_edge(
    focus: dict[str, Any],
    *,
    label: str,
    attribute: str,
    event_data: dict[str, Any],
    configured: bool,
) -> dict[str, Any] | None:
    """Return a narrowly time-aligned observation, not causal proof."""
    boundary = _time(focus.get("stateBoundary"))
    if boundary is None or not isinstance(event_data.get("events"), list):
        return None
    active = {
        "motion": {"active"},
        "presence": {"present"},
        "occupancy": {"occupied", "active", "true"},
    }.get(attribute, set())
    candidates: list[tuple[float, float, datetime]] = []
    for row in event_data["events"]:
        if not isinstance(row, dict):
            continue
        event_time = _time(row.get("date") or row.get("timestamp"))
        if event_time is None or str(row.get("value") or "").casefold().strip() not in active:
            continue
        delta = (event_time - boundary).total_seconds()
        if abs(delta) <= 2.0:
            candidates.append((abs(delta), delta, event_time))
    if not candidates:
        return None
    _distance, delta, when = min(candidates)
    return {
        "label": label,
        "attribute": attribute,
        "configured": configured,
        "signedDeltaSeconds": delta,
        "when": when,
    }


def _readable_app_name(label: str) -> str:
    """Discard live status decoration without losing the producing app name."""
    text = str(label or "").strip()
    suffix = re.search(r"\s*\(([^()]*)\)\s*$", text)
    if suffix and re.search(
        r"\b(?:lights?\s+(?:on|off)|motion\s+(?:active|idle))\b",
        suffix.group(1), re.I,
    ):
        text = text[:suffix.start()].strip()
    return text


def _short_clock(when: datetime, anchor: datetime) -> str:
    return when.astimezone(anchor.tzinfo).strftime("%H:%M")


def _level_changes_after(
    evidence: list[dict[str, Any]], focus: dict[str, Any]
) -> tuple[datetime, float] | None:
    """Find a later dimming within the same observed ON interval."""
    details = _relevant_details(evidence, str(focus.get("subject") or ""))
    boundary = _time(focus.get("stateBoundary"))
    end = _time(focus.get("intervalEnd"))
    producer_id = str((focus.get("producer") or {}).get("id") or "")
    if boundary is None or not producer_id:
        return None
    edges = details.get("correlationEvents") or details.get("observedEvents") or []
    on_edges = [
        _time(row.get("date"))
        for row in edges
        if isinstance(row, dict) and row.get("name") == "switch"
        and row.get("value") == "on"
    ]
    off_edges = [
        _time(row.get("date"))
        for row in edges
        if isinstance(row, dict) and row.get("name") == "switch"
        and row.get("value") == "off"
    ]
    matches = []
    for event in details.get("commandEvents") or []:
        if not isinstance(event, dict):
            continue
        if str((event.get("producedBy") or {}).get("id") or "") != producer_id:
            continue
        when = _time(event.get("date"))
        if when is None or (when - boundary).total_seconds() <= 2:
            continue
        if end and when >= end:
            continue
        if any(edge and boundary < edge <= when for edge in off_edges):
            continue
        if any(edge and abs((edge - when).total_seconds()) <= 2 for edge in on_edges):
            continue
        level = re.search(
            r"\bsetLevel\(\s*(\d+(?:\.\d+)?)",
            str(event.get("description") or ""),
            re.I,
        )
        if level:
            matches.append((when, float(level.group(1))))
    return min(matches, default=None, key=lambda item: item[0])


def _logged_trigger(logs: list[str]) -> str | None:
    """Accept only timestamp-scoped, explicit 'Triggered:' app-log messages."""
    for line in logs:
        found = re.search(r"\bTriggered:\s*(.+)$", str(line), re.I)
        if found:
            trigger = re.sub(r"\s+", " ", found.group(1)).strip(" .")
            if trigger:
                return trigger
    return None


def render_concise_lighting_answer(
    evidence: list[dict[str, Any]],
    focus: dict[str, Any],
    *,
    logs: list[str],
    config_search: str,
    referenced_sensors: list[dict[str, Any]],
    occupancy_matches: list[dict[str, Any]],
    mode_events: list[str],
) -> str:
    """Answer WHO acted and WHAT triggered it, without exposing audit jargon.

    Direct producer information is certain; the initiating event is stated
    as confirmed only when retained app execution logs identify it.
    """
    subject = str(focus.get("subject") or "The light")
    producer = focus.get("producer") or {}
    app_id = str(producer.get("id") or "").strip()
    app_label = _readable_app_name(str(producer.get("label") or "the automation"))
    command = focus.get("command") or {}
    boundary = _time(focus.get("stateBoundary"))
    if boundary is None:
        return f"{subject} was switched on by {app_label} (app {app_id})."

    level = command.get("level")
    level_text = ""
    if level is not None:
        try:
            level_text = f" at {float(level):g}% brightness"
        except (ValueError, TypeError):
            pass
    first = (
        f"{subject} turned on at {_short_clock(boundary, boundary)}{level_text} "
        f"because {app_label} (app {app_id}) switched it on."
    )

    trigger = _logged_trigger(logs)
    if trigger:
        explanation = f"The app log shows it was triggered by {trigger}."
    else:
        matched = next(
            (row for row in occupancy_matches if row.get("configured")
             and float(row.get("signedDeltaSeconds") or 0) <= 0),
            None,
        )
        if matched is None:
            matched = next(
                (row for row in occupancy_matches
                 if float(row.get("signedDeltaSeconds") or 0) <= 0),
                None,
            )
        if matched is not None:
            name = str(matched.get("label") or "An occupancy sensor")
            relation = (
                "likely triggered the automation"
                if matched.get("configured")
                else "may have triggered the automation"
            )
            explanation = (
                f"{name} detected activity around "
                f"{_short_clock(matched['when'], boundary)}, which {relation}."
            )
        elif occupancy_matches:
            name = str(occupancy_matches[0].get("label") or "An occupancy sensor")
            explanation = (
                f"{name} also reported activity around "
                f"{_short_clock(occupancy_matches[0]['when'], boundary)}, "
                "but the exact trigger isn't confirmed."
            )
        elif mode_events:
            explanation = (
                "A hub mode change happened around the same time, "
                "but the exact trigger isn't confirmed."
            )
        elif referenced_sensors:
            names = [
                str(row.get("label") or row.get("name") or "").strip()
                for row in referenced_sensors
            ]
            names = [name for name in names if name]
            if names:
                explanation = (
                    f"The app is configured to respond to {names[0]}, "
                    "but its trigger at that moment couldn't be confirmed."
                )
            else:
                explanation = "The exact event that triggered the app isn't confirmed."
        elif re.search(r"\b(?:motion|occupancy|presence)\b", config_search, re.I):
            explanation = (
                "Occupancy or motion is configured in the automation, "
                "but the exact event that triggered it isn't confirmed."
            )
        else:
            explanation = "The event that triggered the app couldn't be confirmed."

    last = []
    later = _level_changes_after(evidence, focus)
    if later:
        when, value = later
        last.append(
            f"It later adjusted the brightness to {value:g}% at "
            f"{_short_clock(when, boundary)}"
        )
    end = _time(focus.get("intervalEnd"))
    if end:
        last.append(f"the light went off at {_short_clock(end, boundary)}")
    outcome = ""
    if last:
        outcome = ". ".join(last) + "."
        if len(last) == 2:
            outcome = last[0] + ", and " + last[1] + "."

    return " ".join(part for part in (first, explanation, outcome) if part)

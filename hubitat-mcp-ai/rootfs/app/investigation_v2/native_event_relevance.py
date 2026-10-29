"""General source-event selection for historical 'why' investigations.

Unlike top-N newest events, select observations nearest a user-supplied
incident clock, preserving distinct kinds of relevant change. Never infer
the actual hub timezone from a user clock: evaluate both UK civil offset
possibilities and only use the clock for *ranking*, not causal proof.
This module does not select tools, publish claims or execute any action.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping, Sequence

_CLOCK = re.compile(
    r"(?<![\d:])(?P<hour>\d{1,2}):(?P<minute>[0-5]\d)"
    r"(?:\s*(?P<period>a\.?m\.?|p\.?m\.?))?(?![\d:])",
    re.IGNORECASE,
)

def clock_candidates(question: str, period: Mapping[str, Any]) -> list[datetime]:
    """Bounded UTC/BST candidate instants when the question has a clock."""
    if not isinstance(question, str):
        return []
    match = _CLOCK.search(question)
    if match is None:
        return []
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    modifier = (match.group("period") or "").replace(".", "").casefold()
    if hour > 23 or (modifier and hour not in range(1, 13)):
        return []
    if modifier:
        hour = hour % 12 + (12 if modifier == "pm" else 0)
    try:
        start = datetime.fromisoformat(str(period["start_utc_interpreted"]))
        end = datetime.fromisoformat(str(period["end_utc_interpreted"]))
    except (ValueError, TypeError, KeyError):
        return []
    if (start.tzinfo is None or end.tzinfo is None
            or end <= start or end-start > timedelta(days=9)):
        return []
    candidates: list[datetime] = []
    # Date ranges may include two nights. Consider each actual calendar day
    # in a bounded window rather than asserting which date the clock names.
    day = start.astimezone(timezone.utc).date()
    last = end.astimezone(timezone.utc).date()
    while day <= last:
        civil = datetime(day.year,day.month,day.day,hour,minute,tzinfo=timezone.utc)
        for offset in (0, 1):
            instant = civil - timedelta(hours=offset)
            if start - timedelta(hours=2) <= instant <= end + timedelta(hours=2):
                candidates.append(instant)
        day += timedelta(days=1)
    return candidates[:20]


def select_incident_examples(
    events: Sequence[Mapping[str, Any]],
    question: str,
    period: Mapping[str, Any],
    *,
    limit: int = 18,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Prefer diverse observations near the incident over recent telemetry.

    Without a specific clock, retain the original returned order (and a
    bounded larger sample). This avoids accidentally inventing a focal
    moment for overnight/range questions.
    """
    limit = max(2, min(24, int(limit)))
    anchors = clock_candidates(question, period)
    if not anchors:
        return ([dict(e) for e in events[:limit]], {
            "selection": "source_order_no_explicit_clock",
            "selected": min(limit, len(events)),
            "clock_time_unverified": True,
        })

    def seconds(event: Mapping[str, Any]) -> float:
        try:
            dt = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
            if dt.utcoffset() is None:
                return float("inf")
            return min(abs((dt.astimezone(timezone.utc)-a).total_seconds())
                       for a in anchors)
        except (ValueError, TypeError, KeyError):
            return float("inf")

    def kind_priority(event: Mapping[str, Any]) -> int:
        name = str(event.get("name") or "").casefold()
        if name in ("thermostatoperatingstate", "switch", "healthstatus",
                    "networkstatus", "contact", "motion", "presence"):
            return 0
        if name in ("heatingsetpoint", "thermostatsetpoint",
                    "thermostatmode", "level", "position", "valve"):
            return 1
        if name.startswith("command-"):
            return 2
        return 3

    ranked = sorted(enumerate(events), key=lambda pair: (
        seconds(pair[1]), kind_priority(pair[1]), pair[0]))
    chosen: list[tuple[int, Mapping[str, Any]]] = []
    kind_counts: dict[str, int] = {}
    for index, event in ranked:
        name = str(event.get("name") or "")
        # Temperature, voltage and other frequent telemetry must not crowd
        # out the actual command/state transitions being investigated.
        max_kind = 3 if kind_priority(event) == 3 else 5
        if kind_counts.get(name, 0) >= max_kind:
            continue
        chosen.append((index, event))
        kind_counts[name] = kind_counts.get(name, 0) + 1
        if len(chosen) >= limit:
            break
    # Present a chronological causal timeline rather than proximity order.
    chosen.sort(key=lambda item: str(item[1].get("date", "")))
    return ([dict(e) for _,e in chosen], {
        "selection": "question_clock_proximity_and_event_kind",
        "selected": len(chosen),
        "clock_time_unverified": True,
        "clock_candidates_count": len(anchors),
        "source_events_examined": len(events),
    })


__all__ = ["clock_candidates", "select_incident_examples"]

"""Positive occupancy/timer timing evidence from Hubitat's typed event receipts.

This correlation is intentionally weaker than proof of physical occupancy or
of an automation's exact internal timer implementation. It requires actual
app-produced OFF commands, the reported OFF transition, and a sensor inactive
event that listed that *same* app among its event listeners. No names, rooms,
device IDs, or phrases in the question are hardcoded as causes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _histories(receipts: list[dict[str, Any]], attribute: str) -> list[dict[str, Any]]:
    return [
        row["details"] for row in receipts
        if isinstance(row, dict) and row.get("success") is True
        and row.get("mutates") is not True
        and row.get("tool") == "homebrain_device_history"
        and isinstance(row.get("details"), dict)
        and row["details"].get("attribute") == attribute
    ]


def correlate_occupancy_off_timing(
    receipts: list[dict[str, Any]],
    *,
    max_inactive_to_command_s: float = 180.0,
    max_command_to_state_s: float = 3.0,
) -> list[dict[str, Any]]:
    """Return positive source-linked events, never an inferred ghosting verdict.

    All clock gaps are calculated from timestamped typed source events, not
    rounded natural-language timestamps. Returned device history is bounded
    and potentially truncated; 'last' means latest *observed* eligible
    inactive transition, not an exhaustive assertion about the physical world.
    """
    sensor_events: list[dict[str, Any]] = []
    for details in _histories(receipts, "motion"):
        label = str(details.get("label") or "").strip()
        if not label:
            continue
        for event in details.get("boundaryEvents") or []:
            if not isinstance(event, dict) or event.get("name") != "motion":
                continue
            when = _timestamp(event.get("date"))
            listeners = {
                str(item.get("appId"))
                for item in event.get("triggered") or []
                if isinstance(item, dict) and item.get("appId") is not None
            }
            state = str(event.get("value") or "").casefold()
            if when and listeners and state in ("active", "inactive"):
                sensor_events.append({
                    "sensor": label, "when": when, "state": state,
                    "listeners": listeners,
                })

    observed: dict[tuple[str, datetime], dict[str, Any]] = {}
    for light in _histories(receipts, "switch"):
        transitions, commands = [], []
        for event in light.get("boundaryEvents") or []:
            if not isinstance(event, dict):
                continue
            when = _timestamp(event.get("date"))
            if not when:
                continue
            if event.get("name") == "switch" and event.get("value") == "off":
                transitions.append(when)
            if event.get("name") == "command-off":
                producer = event.get("producedBy") or {}
                if (isinstance(producer, dict)
                        and producer.get("type") == "app"
                        and str(producer.get("id") or "").isdigit()):
                    commands.append((when, str(producer["id"])))
        for issued, app in commands:
            switch_gaps = [
                (changed - issued).total_seconds()
                for changed in transitions
                if 0 <= (changed - issued).total_seconds() <= max_command_to_state_s
            ]
            if not switch_gaps:
                continue
            # Select each linked input's latest *observed* inactive transition
            # which is not contradicted by a later active edge from that input.
            linked = [event for event in sensor_events if app in event["listeners"]]
            candidates = []
            for edge in linked:
                if edge["state"] != "inactive":
                    continue
                gap = (issued - edge["when"]).total_seconds()
                if not 0 <= gap <= max_inactive_to_command_s:
                    continue
                if any(
                    later["sensor"] == edge["sensor"]
                    and edge["when"] < later["when"] <= issued
                    and later["state"] == "active"
                    for later in linked
                ):
                    continue
                candidates.append((edge["when"], edge["sensor"], gap))
            if not candidates:
                continue
            latest, sensor, lag = max(candidates, key=lambda x: x[0])
            # A bounded active interval covering the light's observed ON
            # boundary is supporting positive evidence, not vacancy proof.
            active_window = None
            for details in _histories(receipts, "motion"):
                if str(details.get("label") or "") != sensor:
                    continue
                for window in (details.get("temporalAnalysis") or {}).get("observedIntervals") or []:
                    if not isinstance(window, dict):
                        continue
                    begin, end = _timestamp(window.get("start")), _timestamp(window.get("end"))
                    if begin and end and end == latest and begin < end:
                        active_window = (begin, end)
                        break
            key = (app, issued)
            observed[key] = {
                "appId": app,
                "light": str(light.get("label") or "The light"),
                "commandAt": issued.isoformat(),
                "ackSeconds": round(min(switch_gaps), 3),
                "lastObservedInactiveSensor": sensor,
                "inactiveAt": latest.isoformat(),
                "inactiveToCommandSeconds": round(lag, 3),
                "sensorActiveFrom": active_window[0].isoformat() if active_window else None,
                "sensorActiveUntil": active_window[1].isoformat() if active_window else None,
                "verifiedAssociation": "controller-is-event-listener",
                "limits": "bounded-observed-events-not-physical-occupancy",
            }
    return [observed[k] for k in sorted(observed, key=lambda x: x[1])]


def summarize_supported_off_timing(receipts: list[dict[str, Any]]) -> str:
    """Human-facing mechanistic explanation without claiming ghost occupancy."""
    rows = correlate_occupancy_off_timing(receipts)
    if not rows:
        return ""
    parts = []
    for row in rows[-3:]:
        at = _timestamp(row["inactiveAt"])
        command = _timestamp(row["commandAt"])
        parts.append(
            f"{row['lastObservedInactiveSensor']} reported inactive at "
            f"{at:%H:%M:%S.%f}"[:-3]
            + f"; App {row['appId']} issued OFF "
            f"{row['inactiveToCommandSeconds']:.3f}s later "
            f"(at {command:%H:%M:%S.%f}"[:-3]
            + f", with the light reporting OFF {row['ackSeconds']:.3f}s after the command)"
        )
    opening = (
        "**Supported inactivity mechanism:** The recorded input transitions "
        "that list the OFF-producing app as a listener align with the OFF "
        "commands: "
    )
    output = opening + ". ".join(parts) + "."
    for row in rows:
        if not row["sensorActiveFrom"]:
            continue
        start, end = _timestamp(row["sensorActiveFrom"]), _timestamp(row["sensorActiveUntil"])
        output += (
            f" The returned {row['lastObservedInactiveSensor']} history "
            f"shows a bounded active interval from {start:%H:%M:%S} "
            f"to {end:%H:%M:%S}, ending immediately before the corresponding OFF delay."
        )
        break
    output += (
        " These event timings support the explanation that the controller "
        "kept the light ON while its subscribed inputs still reported activity "
        "and issued OFF after their reported inactivity. They do not prove "
        "the room was physically occupied or empty, that activity was false, "
        "or that no omitted event or other app influenced the timer."
    )
    return output

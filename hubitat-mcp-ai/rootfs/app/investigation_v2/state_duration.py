"""Deterministic session-duration answer from verified switch state evidence.

This is generic for binary switch devices: no TV-specific rule, hard-coded ID
or assumption that plug power implies video viewing. Its estimate depends on
history coverage and never asserts independently observed physical state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re

from .evidence import CaseFile, EvidenceItem
from .temporal_scope import IncidentWindow


def is_state_duration_request(question: str, window: IncidentWindow | None) -> bool:
    """Select arithmetic semantics, not a guessed device/tool identity."""
    if window is None or not isinstance(question, str):
        return False
    seeks_duration = re.search(
        r"\bhow\s+long\b|\b(?:total|cumulative)\s+(?:on[- ]?time|duration|time)\b"
        r"|\bon[- ]time\b|\btime\s+(?:spent|switched)\s+on\b",
        question, re.I,
    )
    seeks_state = re.search(r"\b(?:on|off|running|switched)\b", question, re.I)
    return seeks_duration is not None and seeks_state is not None


def _clock(stamp: datetime, zone: ZoneInfo) -> str:
    return stamp.astimezone(zone).strftime("%H:%M:%S %Z")


def _duration(seconds: float) -> str:
    whole = max(0, int(round(seconds)))
    hours, rem = divmod(whole, 3600)
    minutes, sec = divmod(rem, 60)
    return (f"{hours} h {minutes} min {sec} sec" if hours else
            f"{minutes} min {sec} sec")


def format_state_duration_report(
    case: CaseFile, window: IncidentWindow, *,
    device_label: str | None = None,
) -> tuple[str, tuple[str, ...]]:
    zone = ZoneInfo(window.zone_name)
    until = datetime.fromisoformat(window.end_utc)
    readings = [
        row for row in case.records
        if row.stage == "state_reported" and row.action.casefold() == "switch"
        and isinstance(row.value, str)
        and row.value.casefold() in ("on", "off")
        and window.contains(row.timestamp_utc)
    ]
    readings.sort(key=lambda r: (r.timestamp_utc, r.record_id))
    target = (device_label.strip()[:80] if isinstance(device_label, str)
              and device_label.strip() else "Device")
    lines = [f"**{target} — reported ON-time**",
             f"Window: {_clock(datetime.fromisoformat(window.start_utc),zone)}"
             f" to {_clock(until,zone)} ({window.zone_name})."]
    if not readings:
        lines.extend([
            "No verified switch ON/OFF transitions were recovered for this period, "
            "so a duration cannot be calculated.",
            "This does not mean the device was OFF. Check the Hubitat source "
            "history and whether the switch attribute is recorded.",
        ])
        return "\n\n".join(lines), ()
    sessions: list[tuple[datetime, datetime, bool, str]] = []
    started: datetime | None = None
    start_id = ""
    unmatched_off = False
    for row in readings:
        instant = datetime.fromisoformat(row.timestamp_utc).astimezone(timezone.utc)
        if row.value.casefold() == "on":
            if started is None:
                started = instant
                start_id = row.record_id
        elif started is not None:
            if instant >= started:
                sessions.append((started, instant, False, start_id))
            started = None
            start_id = ""
        else:
            unmatched_off = True
    final_open = started is not None
    if started is not None and until >= started:
        sessions.append((started, until, True, start_id))
    if not sessions:
        lines.append(
            "Switch events were recovered, but no complete ON-start interval "
            "could be established. The total duration is unknown."
        )
        return "\n\n".join(lines), tuple(r.record_id for r in readings)
    seconds = sum((end-start).total_seconds() for start,end,_,_ in sessions)
    lines.extend([
        f"**Recorded-session estimate: {_duration(seconds)}** "
        f"({seconds/60:.1f} minutes).",
        "This is calculated from the returned ON/OFF reports, not measured "
        "screen-viewing time or independent confirmation of physical state.",
        "",
        "| Session | ON (local) | OFF / endpoint (local) | Duration |",
        "|---|---|---|---|",
    ])
    for i, (start,end,is_open,_) in enumerate(sessions,1):
        endpoint = (_clock(end,zone)+" (as-of; unverified current state)"
                    if is_open else _clock(end,zone))
        lines.append(
            f"| {i} | {_clock(start,zone)} | {endpoint} | "
            f"{_duration((end-start).total_seconds())} |"
        )
    if final_open:
        lines.append(
            "\nThe last recovered switch report was ON. The final session is "
            "projected only to the request time, assuming no missing OFF event; "
            "**live ON state is not independently verified**."
        )
    else:
        lines.append("\nThe last recovered switch report was OFF.")
    if unmatched_off:
        lines.append(
            "An OFF report lacked a preceding ON report within the period, so "
            "any earlier ON-time remains unknown."
        )
    if not any(c.source_complete is True for c in case.coverage):
        lines.append(
            "Hubitat history is **not independently proven complete**. Missing "
            "transitions could make this estimate too high or too low."
        )
    lines.append(
        "Plug ON-time may include standby and is not the same as actual TV "
        "viewing time. Device power readings would be needed for that distinction."
    )
    return "\n".join(lines), tuple(r.record_id for r in readings)


__all__ = ["is_state_duration_request", "format_state_duration_report"]

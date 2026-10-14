"""Timestamp-aware interpretation of bounded Hubitat device event history.

A driver-attributed device event is not a confirmed MQTT/Zigbee packet and
a previously emitted `dataAgeSeconds` value is not a fresh computed age.
All timestamps here are taken from current-turn receipts, not wall-clock
guesses or provider-produced prose.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


def _instant(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def assess_recorded_telemetry_freshness(
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Report timestamped observations, never current physical reachability."""
    candidates: list[tuple[datetime, dict[str, Any], str]] = []
    stored_age: list[tuple[datetime, str]] = []
    checked_at: list[datetime] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("tool") != "homebrain_device_history":
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        label = str(details.get("label") or "")
        when = _instant(receipt.get("timestamp"))
        if when:
            checked_at.append(when)
        for row in details.get("observedEvents") or []:
            if not isinstance(row, dict):
                continue
            event_at = _instant(row.get("date") or row.get("timestamp"))
            if event_at is None:
                continue
            origin = row.get("producedBy") or {}
            if not isinstance(origin, dict) or (
                str(origin.get("type") or "").casefold() != "device"
            ):
                continue
            if label and str(origin.get("label") or "") != label:
                continue
            name = str(row.get("name") or "")
            if name.startswith("command-") or row.get("type") == "command":
                continue
            candidates.append((event_at, row, label))
            if name == "dataAgeSeconds":
                stored_age.append((event_at, str(row.get("value") or "")))
    if not candidates or not checked_at:
        return None
    latest_at, latest, label = max(candidates, key=lambda record: record[0])
    as_of = max(checked_at)
    seconds = max(0, int((as_of - latest_at).total_seconds()))
    result: dict[str, Any] = {
        "device": label,
        "asOf": as_of.isoformat(),
        "latestReturnedDeviceAttributedEventAt": latest_at.isoformat(),
        "latestReturnedEventAttribute": str(latest.get("name") or ""),
        "secondsSinceLatestReturnedEvent": seconds,
        "eventWithinPast24hOfRead": seconds < 86400,
        "physicalTelemetryVerified": False,
        "fullHistoryVerified": False,
        "interpretation": (
            "These are bounded Hubitat device-attributed event records, not "
            "independent proof of a live physical device connection or an "
            "exhaustive absence of other telemetry."
        ),
    }
    if stored_age:
        age_at, value = max(stored_age, key=lambda item: item[0])
        result["storedDataAgeSeconds"] = {
            "value": value, "recordedAt": age_at.isoformat(),
            "isCurrentRecalculatedValue": False,
        }
    return result



def reconcile_telemetry_answer(
    message: str, summary: dict[str, Any],
) -> tuple[str, bool]:
    """Reconcile textual freshness claims against typed, timestamped events.

    A previous age-counter sample cannot become the present age, and bounded
    event histories cannot prove total absence of physical transport telemetry.
    Preserve unrelated health, switch and command observations.
    """
    old_age = summary.get("storedDataAgeSeconds")
    if not isinstance(old_age, dict):
        old_age = {}
    last_time = str(summary.get("latestReturnedDeviceAttributedEventAt") or "")
    last_kind = str(summary.get("latestReturnedEventAttribute") or "")
    recorded_at = str(old_age.get("recordedAt") or "")
    saved = str(old_age.get("value") or "")
    authoritative_age = (
        f"Stored dataAgeSeconds={saved} was recorded at {recorded_at}; "
        "this is a historical driver value, not a current elapsed-time reading."
        if saved and recorded_at else
        "No fresh device-originated telemetry-age calculation was established."
    )
    authoritative_last = (
        f"The latest returned device-attributed state event was {last_kind} "
        f"at {last_time}; this does not establish actual physical telemetry "
        "or complete absence of later transport data."
    )
    guarded: list[str] = []
    changed = False
    for raw in str(message or "").splitlines(keepends=True):
        newline = "\n" if raw.endswith("\n") else ""
        line = raw[:-1] if newline else raw
        body = line.casefold()
        revised = line
        # Replace an unqualified sampled age presented as current.
        if saved and saved in line and (
            "data age" in body or "dataageseconds" in body
        ) and not re.search(r"(?i)\\b(?:recorded|stored|historical|previous)\\b", line):
            heading = re.match(r"^(\\s*[*-]\\s*\\*\\*[^*]+\\*\\*\\s*)", line)
            prefix = heading.group(1) if heading else ""
            revised = prefix + authoritative_age
        # Neither a driver-generated attribute update nor a bounded 20-row
        # history establishes that no actual device-originated packets arrived.
        elif (
            re.search(r"(?i)\\bno\\s+(?:new\\s+)?telemetry\\s+has\\s+been\\s+received\\b", line)
            or re.search(r"(?i)\\bhas\\s+not\\s+provided\\s+(?:a\\s+)?fresh\\s+update\\b", line)
            or re.search(r"(?i)\\bno\\s+telemetry\\s+(?:was|is)\\s+received\\b", line)
        ):
            heading = re.match(r"^(\\s*[*-]\\s*\\*\\*[^*]+\\*\\*\\s*)", line)
            prefix = heading.group(1) if heading else ""
            revised = prefix + authoritative_last
        if revised != line:
            changed = True
        guarded.append(revised + newline)
    return "".join(guarded), changed


def render_temporal_qualification(summary: dict[str, Any], message: str) -> str:
    """Add a necessary qualification without changing existing observations."""
    lines = [
        "**Time-source qualification:** The most recent returned "
        "device-attributed event is "
        f"{summary['latestReturnedDeviceAttributedEventAt']} "
        f"({summary['latestReturnedEventAttribute']}); "
        "such an event does not prove a physical connection."
    ]
    age = summary.get("storedDataAgeSeconds")
    if isinstance(age, dict):
        lines.append(
            f"The saved dataAgeSeconds={age['value']} was recorded at "
            f"{age['recordedAt']}; it is not a fresh elapsed-time measurement."
        )
    if summary.get("eventWithinPast24hOfRead") and (
        "no telemetry" in str(message or "").casefold()
        or "stopped reporting" in str(message or "").casefold()
    ):
        lines.append(
            "A device-attributed event is present within 24 hours of this "
            "read, so the returned records do not establish an unqualified "
            "24-hour absence of device events. Physical transport telemetry "
            "and end-to-end command acknowledgement remain unverified."
        )
    return " ".join(lines)


__all__ = [
    "assess_recorded_telemetry_freshness", "render_temporal_qualification",
    "reconcile_telemetry_answer",
]

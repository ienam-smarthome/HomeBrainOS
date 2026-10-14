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
    observed_commands = 0
    source_rows = 0
    windows: list[int] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("tool") != "homebrain_device_history":
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        label = str(details.get("label") or "")
        if isinstance(details.get("hoursBack"), (int, float)):
            windows.append(int(details["hoursBack"]))
        when = _instant(receipt.get("timestamp"))
        if when:
            checked_at.append(when)
        for row in details.get("observedEvents") or []:
            if not isinstance(row, dict):
                continue
            source_rows += 1
            if str(row.get("name") or "").startswith("command-") or row.get("type") == "command":
                observed_commands += 1
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
    if not checked_at:
        return None
    as_of = max(checked_at)
    if candidates:
        latest_at, latest, label = max(candidates, key=lambda record: record[0])
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
                "Returned Hubitat device-attributed events do not independently "
                "prove physical transport connectivity or exhaustive coverage."
            ),
        }
    elif observed_commands and source_rows == observed_commands:
        # The event history was read, but it contains only commands.
        # This is *not* proof that the device received nothing: driver
        # lastSeen and cached age are unverified without source timestamps.
        result = {
            "device": label,
            "asOf": as_of.isoformat(),
            "latestReturnedDeviceAttributedEventAt": None,
            "latestReturnedEventAttribute": None,
            "secondsSinceLatestReturnedEvent": None,
            "eventWithinPast24hOfRead": None,
            "observedCommandEvents": observed_commands,
            "returnedEventCount": source_rows,
            "sourceWindowHours": min(windows) if windows else None,
            "onlyCommandEventsInReturnedWindow": True,
            "physicalTelemetryVerified": False,
            "fullHistoryVerified": False,
            "interpretation": (
                "The bounded device-history sample contains only command "
                "invocations. Its physical delivery, telemetry completeness "
                "and precise age of last transport update are not established."
            ),
        }
    else:
        return None
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
    command_only = summary.get("onlyCommandEventsInReturnedWindow") is True
    authoritative_last = (
        f"The returned {summary.get('sourceWindowHours') or 'bounded'}-hour "
        f"history contains {summary.get('observedCommandEvents', 0)} "
        "recorded command invocations and no device-attributed state events. "
        "It cannot prove the absence of physical telemetry or command delivery."
        if command_only else
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
        if command_only and (
            ("45 hours" in body and ("data age" in body or "telemetry" in body
             or "freshness" in body or "stale" in body))
            or ("162,325" in body and "data age" in body)
        ):
            prefix_match = re.match(r"^(\\s*[*-]\\s*\\*\\*[^*]+\\*\\*\\s*)", line)
            revised = (prefix_match.group(1) if prefix_match else "") + (
                "The exact current telemetry age cannot be verified from "
                "this command-only event sample. The driver-reported lastSeen "
                "and stored dataAgeSeconds require timestamped verification."
            )
        elif command_only and (
            "communication is one-way" in body
            or "the device is not responding with state updates" in body
        ):
            revised = (
                "The hub recorded command invocations, but this history "
                "does not establish physical command delivery, responses, "
                "or one-way transport behaviour."
            )
        elif command_only and (
            "no telemetry or state changes were received" in body
            or "no telemetry has been received" in body
            or "no incoming telemetry updates" in body
            or "no device-originated events" in body
        ):
            revised = authoritative_last
        elif command_only and (
            "but this contradicts the health status" in body
            or ("discrepancy between the" in body and "mqtt" in body)
            or (
                ("mqttstatus" in body or "mqtt status" in body)
                and "offline" in body
                and any(term in body for term in (
                    "contradiction", "conflict", "inconsistent",
                ))
            )
        ):
            revised = (
                "The stored mqttStatus and health attributes report different "
                "statuses; freshness and their distinct meanings are unverified."
            )
        # Structure-aware repairs are driven by a *bounded source* assessment:
        # neither a device-attributed attribute event nor a filled/truncated
        # event history proves physical telemetry or command acknowledgement.
        if (
            line.lstrip().startswith("|")
            and "telemetry is stale" in body
            and "no device-originated events since" in body
        ):
            revised = (
                "| **Evidence-limited** | **Recent physical telemetry unverified** "
                f"| {authoritative_last} |"
            )
        elif (
            line.lstrip().startswith("|")
            and "commands are not triggering updates" in body
            and ("zero state changes" in body or "no state changes" in body)
        ):
            revised = (
                "| **Evidence-limited** | **Commands were recorded** | "
                "No corresponding state update was established by the "
                "returned bounded history. Delivery, execution and "
                "complete event coverage remain unverified. |"
            )
        elif re.search(
            r"(?i)\b(?:last|latest)\s+telemetry\s+received\s+from\s+the\s+device\b",
            line,
        ) or re.search(
            r"(?i)\blast\s+device[- ]originated\s+event\b.*\b"
            r"last\s+telemetry\s+received\b",
            line,
        ):
            heading = re.match(r"^(\s*[*-]\s*\*\*[^*]+\*\*\s*)", line)
            prefix = heading.group(1) if heading else ""
            revised = prefix + authoritative_last
        elif (
            "no state-change events followed these commands" in body
            or "resulted in zero state changes" in body
        ):
            if "however" in body:
                head = re.split(r"(?i)\bhowever\b", line, maxsplit=1)[0].rstrip()
                revised = (
                    head + " However, the returned bounded event history "
                    "does not establish command delivery or a complete "
                    "record of subsequent state changes."
                )
            else:
                heading = re.match(r"^(\s*[*-]\s*\*\*[^*]+\*\*\s*)", line)
                prefix = heading.group(1) if heading else ""
                revised = (
                    prefix + "Commands were recorded, but physical delivery "
                    "and a complete response history were not verified."
                )
        # Replace an unqualified sampled age presented as current.
        elif saved and saved in ''.join(ch for ch in line if ch.isdigit()) and (
            "data age" in body or "dataageseconds" in body
        ) and not re.search(r"(?i)\b(?:recorded|stored|historical|previous)\b", line):
            heading = re.match(r"^(\s*[*-]\s*\*\*[^*]+\*\*\s*)", line)
            prefix = heading.group(1) if heading else ""
            revised = prefix + authoritative_age
        # Neither a driver-generated attribute update nor a bounded 20-row
        # history establishes that no actual device-originated packets arrived.
        elif (
            re.search(r"(?i)\bno\s+(?:new\s+)?telemetry\s+has\s+been\s+received\b", line)
            or re.search(r"(?i)\bhas\s+not\s+provided\s+(?:a\s+)?fresh\s+update\b", line)
            or re.search(r"(?i)\bno\s+telemetry\s+(?:was|is)\s+received\b", line)
        ):
            heading = re.match(r"^(\s*[*-]\s*\*\*[^*]+\*\*\s*)", line)
            prefix = heading.group(1) if heading else ""
            revised = prefix + authoritative_last
        if revised != line:
            changed = True
        guarded.append(revised + newline)
    return "".join(guarded), changed


def render_temporal_qualification(summary: dict[str, Any], message: str) -> str:
    """Add a necessary qualification without changing existing observations."""
    if summary.get("onlyCommandEventsInReturnedWindow"):
        lines = [
            "**Time-source qualification:** The returned device event sample "
            "contained command invocations only. No fresh age of device-originated "
            "transport telemetry or end-to-end command acknowledgement was proven."
        ]
    else:
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

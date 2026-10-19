"""Typed positive command provenance and timezone-aware historical read bounds.

A mixed device-event page can contain directly observed command events even
without attribute=command-off. Command *recording* is distinguishable from
delivery, physical actuation, upstream cause and complete historical coverage.
This module is pure: no provider or MCP calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo

_LOCAL = ZoneInfo("Europe/London")
_DATE_CLOCK = re.compile(
    r"(?i)\b(?P<day>\d{1,2})\s+(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(?P<year>20\d{2})\b[\s\S]{0,105}?"
    r"\b(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)\s*(?P<zone>BST|GMT)\b"
)
_DEVICE_ID = re.compile(r"(?i)\bdevice\s*(?:id\s*)?[#:]?\s*(\d{2,9})\b")


def _at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        point = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return point if point.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def requested_event_boundary(prompt: str) -> datetime | None:
    """Resolve a UK historical wall-clock boundary; fail closed on DST mismatch."""
    match = _DATE_CLOCK.search(str(prompt or ""))
    if not match:
        return None
    try:
        month = datetime.strptime(match.group("month").title(), "%B").month
        local = datetime(
            int(match.group("year")), month, int(match.group("day")),
            int(match.group("hour")), int(match.group("minute")), tzinfo=_LOCAL,
        )
        expected = "BST" if local.utcoffset() == timedelta(hours=1) else "GMT"
        if match.group("zone").upper() != expected:
            return None
        return local
    except ValueError:
        return None


def history_window_instruction(prompt: str) -> str:
    """One deterministic clock conversion before the model chooses tools."""
    local = requested_event_boundary(prompt)
    if local is None:
        return ""
    utc = local.astimezone(timezone.utc)
    before, after = utc - timedelta(minutes=10), utc + timedelta(minutes=10)
    return (
        "HOST HISTORICAL TIME BOUNDARY (not event proof): User asks about "
        f"{local.strftime('%Y-%m-%d %H:%M %Z')} = "
        f"{utc.strftime('%Y-%m-%dT%H:%M:%SZ')}. "
        "For any relevant UTC-based logs and device-event source, choose "
        f"an incident window such as {before.strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"to {after.strftime('%Y-%m-%dT%H:%M:%SZ')}. "
        "Never pass the BST wall-clock time as a UTC 'Z' time. "
        "If the source lacks time-window filtering, explicitly qualify coverage."
    )


def _args(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("arguments")
    if not isinstance(value, dict):
        return {}
    return value.get("args", value) if isinstance(value.get("args"), dict) else value


def mixed_command_events(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Only typed command rows from a successful, target-scoped Hubitat read."""
    if (
        not isinstance(row, dict) or row.get("success") is not True
        or row.get("mutates") is True
        or row.get("effect") not in (None, "read")
        or str(row.get("sub_tool") or (row.get("arguments") or {}).get("tool") or "")
           != "hub_list_device_events"
    ):
        return []
    if not str(_args(row).get("deviceId") or "").isdigit():
        return []
    details = row.get("details")
    if not isinstance(details, dict):
        return []
    results = []
    for key in ("observedEvents", "events", "commandEvents", "boundaryEvents"):
        batch = details.get(key)
        if not isinstance(batch, list):
            continue
        for event in batch[:200]:
            if not isinstance(event, dict):
                continue
            name = str(event.get("name") or "").casefold()
            if name not in ("command-on", "command-off"):
                continue
            if str(event.get("type") or "").casefold() not in ("", "command"):
                continue
            if _at(event.get("date")) is None:
                continue
            results.append(event)
    return results


def focused_command_observation(prompt: str, evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Identify a unique recorded app command, not a verified physical effect."""
    target = requested_event_boundary(prompt)
    if target is None:
        return None
    target_utc = target.astimezone(timezone.utc)
    explicitly_named_ids = set(_DEVICE_ID.findall(prompt))
    matches: list[tuple[str, str, str, str]] = []
    for row in evidence:
        if not isinstance(row, dict):
            continue
        events = mixed_command_events(row)
        if not events:
            continue
        device_id = str(_args(row).get("deviceId") or "")
        if explicitly_named_ids and device_id not in explicitly_named_ids:
            continue
        for item in events:
            at = _at(item.get("date"))
            if at is None or abs((at.astimezone(timezone.utc) - target_utc).total_seconds()) > 90:
                continue
            issuer = item.get("producedBy")
            if not isinstance(issuer, dict):
                continue
            app_id = issuer.get("appId")
            if not str(app_id or "").isdigit():
                continue
            action = str(item.get("name") or "").removeprefix("command-").casefold()
            # The original user intent must mention this action, not a model guess.
            if not re.search(r"\b" + re.escape(action) + r"\b", str(prompt), re.I):
                continue
            matches.append((device_id, action, str(app_id), at.isoformat()))
    if not matches:
        return None
    # Multiple issuers or multiple target devices make attribution ambiguous.
    unique = set(matches)
    if len({(d,a,app) for d,a,app,_ in unique}) != 1:
        return None
    chosen = min(unique, key=lambda rec: abs(
        (_at(rec[3]).astimezone(timezone.utc)-target_utc).total_seconds()
    ))
    return {
        "deviceId": chosen[0],
        "command": chosen[1],
        "recordedIssuerAppId": chosen[2],
        "recordedCommandTimestamp": chosen[3],
        "source": "same-turn Hubitat device-event command record",
        "commandRecorded": True,
        "deliveryVerified": False,
        "physicalActuationVerified": False,
        "upstreamTriggerVerified": False,
    }


def incident_log_window_coverage(
    prompt: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Check whether any successful app-log *query* contains the local incident."""
    boundary = requested_event_boundary(prompt)
    if boundary is None:
        return None
    center = boundary.astimezone(timezone.utc)
    scoped = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        op = str(row.get("sub_tool") or (row.get("arguments") or {}).get("tool") or "")
        if op != "hub_get_logs":
            continue
        args = _args(row)
        if not str(args.get("appId") or "").isdigit():
            continue
        start, end = _at(args.get("since")), _at(args.get("until"))
        if start is None or end is None:
            continue
        scoped.append({
            "appId": str(args["appId"]),
            "since": start.isoformat(), "until": end.isoformat(),
            "includesRequestedEvent": start <= center <= end,
        })
    if not scoped:
        return None
    contains = any(item["includesRequestedEvent"] for item in scoped)
    return {
        "correctTimeWindowChecked": contains,
        "queriedWindows": scoped[:5],
        "requestedEventUTC": center.isoformat(),
        "note": (
            "A successful app-log read outside the historical event window "
            "does not establish the absence of logs around that event."
            if not contains else
            "An in-window log read is bounded evidence; empty logs do not prove "
            "an automation did not execute."
        ),
    }


def calibrate_command_causality(
    message: str, recorded: dict[str, Any] | None,
    log_window: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    """Preserve observed issuer but remove unsupported exclusivity/ACK claims."""
    text = str(message or "")
    fixes: list[str] = []
    if recorded:
        patterns = (
            (r"(?i)\bthe evidence establishes that this was an automated action rather than a physical or external interaction\b",
             "the records identify a Hubitat app issuing an OFF command; independent physical and external actions were not exhaustively checked"),
            (r"(?i)\bthe device responded to this command within approximately \d+\s*ms\b",
             "Hubitat recorded a switch-state event shortly after the command; physical acknowledgement was not independently verified"),
            (r"(?im)^\s*\*\s*\*\*Physical Interaction \(Contradicted\):\*\*.*$",
             "* **Physical interaction (not independently verified):** The observed app command does not exclude separate physical interaction."),
            (r"(?im)^\s*\*\s*\*\*External/Cloud Integration \(Unsupported\):\*\*.*$",
             "* **External integration (not independently verified):** The observed command producer identifies a Hubitat app, not every possible upstream trigger."),
        )
        for expression, correction in patterns:
            text, n = re.subn(expression, correction, text)
            if n:
                fixes.append("upstream_or_physical_overclaim")
        text += (
            "\n\n**Verified versus unverified:** Hubitat recorded "
            f"a `command-{recorded['command']}` for device {recorded['deviceId']} "
            f"at {recorded['recordedCommandTimestamp']}, produced by app "
            f"{recorded['recordedIssuerAppId']}. This verifies the recorded "
            "Hubitat command issuer, not the automation's preceding trigger, "
            "MQTT delivery, physical switch actuation or the later offline cause."
        )
    if log_window and not log_window["correctTimeWindowChecked"]:
        text, n = re.subn(
            r"(?i)(?:a\s+)?targeted log read for App\s+\d+\s+returned\s+no\s+"
            r"entries\s+for\s+the\s+window\s+surrounding\s+the\s+event",
            "an app-log query returned no entries, but its time window did "
            "not include the requested incident",
            text,
        )
        if n:
            fixes.append("misaligned_app_log_claim")
        text += (
            "\n\n**Log-window correction:** The completed app-log query "
            "did not cover the requested event time "
            f"({log_window['requestedEventUTC']} UTC). Its empty result "
            "cannot exclude automation execution logs during that incident. "
            "A read covering the correct UTC window is still needed."
        )
    return text, list(dict.fromkeys(fixes))


__all__ = [
    "requested_event_boundary", "history_window_instruction",
    "mixed_command_events", "focused_command_observation",
    "incident_log_window_coverage", "calibrate_command_causality",
]

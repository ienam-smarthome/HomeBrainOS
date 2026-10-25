"""Evidence-window integrity for historical incidents spanning calendar dates.

No model-written fact is a source. This module normalizes explicit local clocks
to UTC, inspects typed event receipts, and refuses to turn an incomplete
latest-N page into evidence that an older event never occurred. It does not
route tool calls or create/modify automations.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo

_LOCAL = ZoneInfo("Europe/London")
_MONTHS = {datetime(2024, i, 1).strftime("%B").lower(): i for i in range(1, 13)}
_CLOCK_DATE = re.compile(
    r"(?i)\b(?P<hour>(?:[01]?\d|2[0-3])):(?P<minute>[0-5]\d)"
    r"(?:\:[0-5]\d)?\s+(?:on\s+)?(?P<day>[0-3]?\d)\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)(?:\s+(?P<year>20\d{2}))?\b"
)


def _instant(raw: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(raw or "").strip().replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def requested_interval(request: str) -> tuple[datetime, datetime] | None:
    """Parse two explicit clock/date anchors with a shared year, not a guessed date.

    Reject repeated fall-back-hour times without an explicit UTC offset: a
    physical incident cannot be reconstructed by arbitrarily selecting fold=0.
    Both returned instants are UTC; date ordering is actual, not wall-clock.
    """
    matches = list(_CLOCK_DATE.finditer(str(request or "")))
    if len(matches) != 2:
        return None
    years = {int(m.group("year")) for m in matches if m.group("year")}
    if len(years) != 1:
        return None
    year = next(iter(years))
    points = []
    try:
        for match in matches:
            dt = datetime(
                int(match.group("year") or year),
                _MONTHS[match.group("month").lower()],
                int(match.group("day")), int(match.group("hour")),
                int(match.group("minute")), tzinfo=_LOCAL,
            )
            if dt.replace(fold=0).utcoffset() != dt.replace(fold=1).utcoffset():
                return None
            points.append(dt.astimezone(timezone.utc))
    except (ValueError, OverflowError):
        return None
    if points[1] <= points[0]:
        return None
    return points[0], points[1]


def incident_window_instruction(request: str) -> str:
    window = requested_interval(request)
    if not window:
        return ""
    begin, end = window
    return (
        "HOST VERIFIED CALENDAR WINDOW (NOT EVIDENCE AN EVENT OCCURRED): "
        f"requested UK local start {begin.astimezone(_LOCAL).isoformat()} "
        f"and end {end.astimezone(_LOCAL).isoformat()}; canonical UTC "
        f"since={begin.isoformat().replace('+00:00', 'Z')}, "
        f"until={end.isoformat().replace('+00:00', 'Z')}. "
        "Use this exact interval for target-scoped event/command and app-log "
        "reads when supported. Do not substitute a location-event query for "
        "device history. A latest-N page whose oldest row is newer than "
        "the requested interval cannot prove historical events were absent."
    )


def _read_args(receipt: dict[str, Any]) -> dict[str, Any]:
    args = receipt.get("arguments") or {}
    if isinstance(args, dict) and isinstance(args.get("args"), dict):
        return args["args"]
    return args if isinstance(args, dict) else {}


def assess_retained_incident(
    request: str, evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Identify a historical gap from target-matched, typed device event rows.

    The assessment proves only the available source's temporal reach, never
    the absence of an ON, OFF, command, sensor veto, or automation execution.
    """
    window = requested_interval(request)
    if not window:
        return None
    begin, end = window
    target_ids = set()
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("evidence_kind") != "targeted_device_lookup":
            continue
        reported = (row.get("details") or {}).get("reportedDeviceState") or {}
        device_id = str(reported.get("deviceId") or "")
        label = str(reported.get("label") or "")
        if device_id.isdigit() and label and label.casefold() in request.casefold():
            target_ids.add(device_id)
    if len(target_ids) != 1:
        return None
    target_id = next(iter(target_ids))
    points: dict[str, datetime] = {}
    label = ""
    truncated = False
    unverified_integrity = False
    target_receipts = 0
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("tool") != "homebrain_device_history":
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict) or details.get("attribute") != "switch":
            continue
        candidate_label = str(details.get("label") or "")
        if not candidate_label or candidate_label.casefold() not in request.casefold():
            continue
        label = candidate_label
        target_receipts += 1
        truncated |= bool(details.get("observedEventsTruncated"))
        unverified_integrity |= details.get("historySourceIntegrityVerified") is False
        for item in details.get("observedEvents") or []:
            if not isinstance(item, dict) or item.get("name") != "switch":
                continue
            instant = _instant(item.get("date"))
            if instant:
                points[instant.isoformat()] = instant
    if target_receipts == 0 or not points:
        return None
    earliest = min(points.values())
    in_window = sum(begin <= point <= end for point in points.values())
    return {
        "subject": label, "deviceId": target_id,
        "startUtc": begin.isoformat(), "endUtc": end.isoformat(),
        "startLocal": begin.astimezone(_LOCAL).isoformat(),
        "endLocal": end.astimezone(_LOCAL).isoformat(),
        "oldestRetainedUtc": earliest.isoformat(),
        "oldestRetainedLocal": earliest.astimezone(_LOCAL).isoformat(),
        "recordedSwitchRowsInWindow": in_window,
        "retainedSwitchRows": len(points),
        "latestPageDoesNotReachWindow": earliest > end,
        "historyTruncated": truncated,
        "integrityUnverified": unverified_integrity,
        "absenceEstablished": False,
    }


def calibrate_historical_incident_answer(
    request: str, evidence: list[dict[str, Any]], draft: str, *,
    causal: bool,
) -> tuple[str, dict[str, Any] | None]:
    """Only replace a causal verdict when the target's historic window is unseen.

    A verified alternative source, e.g. a timestamped journal reconstruction,
    must not be discarded. Even an ungrounded model conclusion never proves
    source absence. Replacements state facts and limitations without inventing
    a new most-likely culprit.
    """
    if not causal:
        return draft, None
    scope = assess_retained_incident(request, evidence)
    if not scope or not scope["latestPageDoesNotReachWindow"]:
        return draft, scope
    # A separate verified, target-matched focal/journal record may reconstruct
    # the event even when native latest-N history has already evicted it.
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("evidence_kind") not in {
            "focal_archived_state_history", "focal_exact_state_history",
        }:
            continue
        details = row.get("details") or {}
        if (str(details.get("deviceId") or "") == scope["deviceId"]
                and (details.get("sourceVerifiedOn") is True
                     or details.get("observedBoundaryVerified") is True)):
            return draft, scope
    first = datetime.fromisoformat(scope["oldestRetainedLocal"])
    begin = datetime.fromisoformat(scope["startLocal"])
    end = datetime.fromisoformat(scope["endLocal"])
    summary = (
        "**Historical cause not established from the retained events.** "
        f"The requested incident for {scope['subject']} runs from "
        f"{begin:%d %B %Y, %H:%M} to {end:%d %B %Y, %H:%M} (UK time). "
        f"The oldest target switch event returned is {first:%d %B %Y, %H:%M:%S} "
        f"({first:%z}), after the requested end. The returned "
        f"{scope['retainedSwitchRows']} switch rows do not cover that incident. "
        "This does not prove a missing ON event, a controller-state loss "
        "or a timer failure. System health events, when separately verified, "
        "do not establish the cause of a device-specific fault. "
        "Controller/sensor inactivity, missing notifications and execution "
        "delays remain possible but undistinguished by these retained records. "
        "Check a timestamped archive of the target, relevant input sensors, "
        "and the controlling app's command/decision logs for this exact window. "
        "No automation or device was modified."
    )
    return summary, scope


__all__ = [
    "requested_interval", "incident_window_instruction",
    "assess_retained_incident", "calibrate_historical_incident_answer",
]

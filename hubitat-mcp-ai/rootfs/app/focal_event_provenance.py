"""Resolve the requested historical event using independent, scoped sources.

Do not conflate the newest OFF state with the newest VERIFIED MANUAL OFF.
Physical button, controller-app command, and light state must match in time.
Use native source offsets to interpret date/time requests; API filters use UTC.
Current settings, historical actions and user expectations are separate facts.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
import re

_MONTHS = {name: index for index, name in enumerate(
    ("january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"), 1
)}
_CLOCK = re.compile(
    r"\b(?:at|around|approximately|about)\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\b",
    re.I,
)
_DAY = re.compile(
    r"\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+(\d{4})\b", re.I,
)


def aware(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def off_candidates(data: dict[str, Any]) -> list[datetime]:
    values: set[datetime] = set()
    temporal = data.get("temporalAnalysis") or {}
    if isinstance(temporal, dict):
        for key in ("intervals", "observedIntervals"):
            for row in temporal.get(key) or []:
                if not isinstance(row, dict) or row.get("clippedAtWindowEnd"):
                    continue
                stamp = aware(row.get("end"))
                if stamp:
                    values.add(stamp)
    for key in ("boundaryEvents", "observedEvents", "correlationEvents"):
        for row in data.get(key) or []:
            if not isinstance(row, dict) or str(row.get("value") or "").lower() != "off":
                continue
            stamp = aware(row.get("date") or row.get("timestamp"))
            if stamp:
                values.add(stamp)
    return sorted(values, reverse=True)


def explicit_requested_instant(prompt: str, source_local: str | None) -> datetime | None:
    """Never interpret a UK wall-clock timestamp as UTC by default.

    Apply the native event's *explicit offset* only when grounded; no host
    timezone guessing, particularly around daylight-saving transitions.
    """
    day = _DAY.search(str(prompt))
    clock = _CLOCK.search(str(prompt))
    if not day or not clock or not source_local:
        return None
    try:
        tz = datetime.fromisoformat(source_local).tzinfo
        if tz is None:
            return None
        dt = datetime(
            int(day.group(3)), _MONTHS[day.group(2).lower()], int(day.group(1)),
            int(clock.group(1)), int(clock.group(2)), int(clock.group(3) or 0),
            tzinfo=tz,
        )
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def physical_button_observations(data: dict[str, Any], device_id: str) -> list[dict[str, Any]]:
    """Native pushed events only; journal collector-received is weaker."""
    rows = (data.get("observedEvents") or data.get("correlationEvents")
            or data.get("events") or [])
    result = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("name") or "") != "pushed":
            continue
        stamp = aware(row.get("date") or row.get("timestamp"))
        source = row.get("producedBy") or {}
        if (stamp is None or not isinstance(source, dict)
                or str(source.get("id") or "") != str(device_id)
                or str(row.get("type") or "").lower() != "physical"):
            continue
        result.append({
            "deviceId": str(device_id), "buttonNumber": str(row.get("value") or ""),
            "occurredAt": stamp.isoformat(),
            "source": "native physical button event",
        })
    return result


def _command_pairs(
    data: dict[str, Any], off: datetime,
    presses: list[dict[str, Any]], *, tolerance: float = 2.0,
) -> list[dict[str, Any]]:
    correlated = []
    for row in data.get("commandEvents") or []:
        if not isinstance(row, dict) or str(row.get("name") or "").lower() != "command-off":
            continue
        command = aware(row.get("date") or row.get("timestamp"))
        if command is None or not 0 <= (off - command).total_seconds() <= tolerance:
            continue
        producer = row.get("producedBy") or {}
        if not isinstance(producer, dict) or not producer.get("id"):
            continue
        for press in presses:
            pushed = aware(press.get("occurredAt"))
            if pushed is None or not 0 <= (command - pushed).total_seconds() <= tolerance:
                continue
            correlated.append({
                "button": press,
                "commandAt": command.isoformat(),
                "commandProducer": {
                    "id": str(producer["id"]),
                    "label": str(producer.get("label") or "")[:80],
                    "type": str(producer.get("type") or ""),
                },
                "buttonToCommandMs": round((command-pushed).total_seconds()*1000, 3),
                "commandToStateMs": round((off-command).total_seconds()*1000, 3),
                "causalAssociation": "time-linked physical push, app command and OFF state",
                "hardwareEventObserved": True,
                "automationLockoutExecutionVerified": False,
            })
    return sorted(correlated, key=lambda x: x["buttonToCommandMs"])[:3]


def select_focal_off(
    data: dict[str, Any], prompt: str, *,
    physical_presses: list[dict[str, Any]] | None = None,
    source_local: str | None = None,
) -> dict[str, Any]:
    """Keep latest state OFF distinct from latest *verified* manual OFF.

    If a specific clock/date is requested but the source offset is unknown,
    fail closed instead of silently targeting today's 'latest' event.
    """
    off_states = off_candidates(data)
    presses = physical_presses or []
    clock_requested = bool(_CLOCK.search(str(prompt)) and _DAY.search(str(prompt)))
    target = explicit_requested_instant(prompt, source_local)
    if clock_requested and target is None:
        return {
            "status": "unresolved-request-clock", "latestObservedOff": (
                off_states[0].isoformat() if off_states else None
            ), "selectedOff": None, "manualOffVerified": False,
            "physicalButtonCommandChain": [], "selectionBasis": "source-offset-required",
        }
    scope = off_states
    if target is not None:
        scope = [x for x in off_states if abs((x-target).total_seconds()) <= 3]
    chains = [
        (off, matches) for off in scope
        if (matches := _command_pairs(data, off, presses))
    ]
    manual_requested = bool(
        re.search(r"\bmanual(?:ly)?\b", str(prompt), re.I)
        and re.search(r"\boff\b", str(prompt), re.I)
    )
    if chains and manual_requested:
        selected, links = chains[0]
        basis, manual = "latest-confirmed-physical-button-command-off", True
    elif scope:
        selected, links = scope[0], []
        basis, manual = (
            "requested-explicit-event-without-manual-proof" if target is not None
            else "latest-observed-off-manual-unverified"
        ), False
    else:
        selected, links = None, []
        basis, manual = "requested-event-not-observed", False
    return {
        "status": "selected" if selected else "unresolved",
        "latestObservedOff": off_states[0].isoformat() if off_states else None,
        "latestVerifiedManualOff": chains[0][0].isoformat() if chains else None,
        "selectedOff": selected.isoformat() if selected else None,
        "manualOffVerified": manual,
        "physicalButtonCommandChain": links,
        "selectionBasis": basis,
        "newerNonManualOffObserved": bool(
            selected and off_states and off_states[0] > selected
        ),
        "explicitTargetUtc": target.isoformat() if target else None,
        "candidateOffCount": len(off_states),
    }


def current_config_facts(config: dict[str, Any] | None) -> dict[str, Any]:
    """Extract only typed, persisted values from an explicit settings read.

    A rendered status summary is not an authoritative settings read.
    Avoid extracting private settings beyond the requested duration/mode.
    """
    result: dict[str, Any] = {
        "source": "current persisted app settings",
        "settingsRead": False,
        "configuredDurationSeconds": None,
        "configuredDurationMinutes": None,
        "triggerMode": None,
        "notHistoricalConfigurationProof": True,
    }
    if not isinstance(config, dict):
        return result
    settings = config.get("settings")
    if not isinstance(settings, dict):
        app = config.get("app") or {}
        settings = app.get("settings") if isinstance(app, dict) else None
    if not isinstance(settings, dict):
        return result
    result["settingsRead"] = True
    duration = settings.get("motionOffLockoutMinutes")
    if isinstance(duration, dict):
        duration = duration.get("value")
    if duration is not None and re.fullmatch(r"\d{1,6}", str(duration).strip()):
        minutes = int(str(duration).strip())
        result["configuredDurationMinutes"] = minutes
        result["configuredDurationSeconds"] = minutes * 60
    mode = settings.get("motionOffLockoutTrigger")
    if isinstance(mode, dict):
        mode = mode.get("value")
    if isinstance(mode, str) and mode.strip():
        result["triggerMode"] = mode.strip()[:64]
    return result


__all__ = [
    "off_candidates", "explicit_requested_instant", "physical_button_observations",
    "select_focal_off", "current_config_facts",
]

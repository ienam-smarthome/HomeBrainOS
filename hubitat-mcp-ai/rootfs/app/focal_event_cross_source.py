"""Bounded native-event / collector-journal correlation for a requested event.

The native device-event feed has separate retention/cardinality limits for
state and command streams. An older command and physical press may remain
visible even after its state transition falls off the newest-N switch page.
Journal timestamps are when HomeBrain COLLECTED an event, not necessarily
when the hardware event happened. Never relabel those as authoritative native
device-event times or historical automation execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import re

from focal_event_provenance import aware, off_candidates


def _event_utc(record: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        value = record.get(key)
        if value:
            stamp = aware(value)
            if stamp is not None:
                return stamp
    return None


def _journal_light_off(
    journal: list[dict[str, Any]], light_id: str,
    command: datetime, *, max_lag_seconds: float,
) -> dict[str, Any] | None:
    observations = []
    for entry in journal:
        if (
            not isinstance(entry, dict) or entry.get("kind") != "light"
            or str(entry.get("deviceId") or "") != str(light_id)
        ):
            continue
        for row in entry.get("observations") or []:
            if (
                not isinstance(row, dict)
                or str(row.get("value") or "").casefold() != "off"
                or str(row.get("timestampBasis") or "") != "collector-received"
            ):
                continue
            stamp = _event_utc(row, "observedAt")
            if stamp is None:
                continue
            delta = (stamp - command).total_seconds()
            if 0 <= delta <= max_lag_seconds:
                observations.append((delta, stamp))
    if not observations:
        return None
    lag, stamp = min(observations)
    return {
        "collectorReceivedAtUtc": stamp.isoformat(timespec="milliseconds"),
        "millisecondsAfterNativeCommand": round(lag * 1000, 3),
        "timestampBasis": "collector-received",
        "originalDeviceEventClockKnown": False,
        "provesNativeStateTimestamp": False,
        "supportsOffObservation": True,
    }


def correlate_requested_focal_sources(
    light_history: dict[str, Any],
    physical_presses: list[dict[str, Any]],
    journal: list[dict[str, Any]],
    *,
    anchor_utc: str,
    light_device_id: str,
    command_tolerance_seconds: float = 3.0,
    button_tolerance_seconds: float = 2.0,
    collector_lag_seconds: float = 5.0,
) -> dict[str, Any]:
    """Link independently captured sources while preserving their proof level.

    Return no claims when a trustworthy UTC anchor is absent. Do not infer
    which button app should own a lockout: keep the command's actual producer.
    """
    anchor = aware(anchor_utc)
    result: dict[str, Any] = {
        "schema": "focal-cross-source-v1",
        "requestedEventUtc": anchor.isoformat() if anchor else None,
        "nativeButtonCommandVerified": False,
        "nativeLightStateObserved": False,
        "journalLightOffObserved": False,
        "lockoutExecutionVerified": False,
        "journalSourceClockIsCollectorReceipt": True,
        "nativeCommandNotEqualNativeState": True,
        "historicalConfigurationProven": False,
        "candidate": None,
    }
    if anchor is None:
        return result
    native_off = next(
        (x for x in off_candidates(light_history)
         if abs((x-anchor).total_seconds()) <= command_tolerance_seconds),
        None,
    )
    result["nativeLightStateObserved"] = native_off is not None
    result["nativeLightOffAtUtc"] = native_off.isoformat() if native_off else None

    commands = []
    for row in light_history.get("commandEvents") or []:
        if not isinstance(row, dict) or str(row.get("name") or "").casefold() != "command-off":
            continue
        stamp = _event_utc(row, "date", "timestamp")
        if stamp is None or abs((stamp-anchor).total_seconds()) > command_tolerance_seconds:
            continue
        producer = row.get("producedBy") or {}
        if not isinstance(producer, dict) or not producer.get("id"):
            continue
        commands.append((abs((stamp-anchor).total_seconds()), stamp, producer))

    candidates = []
    for _, command, producer in commands:
        for press in physical_presses:
            if not isinstance(press, dict):
                continue
            pushed = _event_utc(press, "occurredAt")
            if pushed is None:
                continue
            delta = (command-pushed).total_seconds()
            if not 0 <= delta <= button_tolerance_seconds:
                continue
            expected_number = re.search(
                r"\bbutton\s+(\d+)\s+pushed\b",
                str(producer.get("label") or ""), re.I,
            )
            if expected_number and expected_number.group(1) != str(
                press.get("buttonNumber") or ""
            ):
                continue
            off = _journal_light_off(
                journal, str(light_device_id), command,
                max_lag_seconds=collector_lag_seconds,
            )
            native_state_matches = bool(
                native_off is not None
                and 0 <= (native_off-command).total_seconds() <= collector_lag_seconds
            )
            candidate = {
                "physicalButtonDeviceId": str(press.get("deviceId") or ""),
                "physicalButtonNumber": str(press.get("buttonNumber") or ""),
                "nativePhysicalPressAtUtc": pushed.isoformat(timespec="milliseconds"),
                "nativeOffCommandAtUtc": command.isoformat(timespec="milliseconds"),
                "commandProducerAppId": str(producer.get("id") or ""),
                "commandProducerLabel": str(producer.get("label") or "")[:80],
                "buttonToCommandMilliseconds": round(delta * 1000, 3),
                "nativeStateConfirmed": native_state_matches,
                "journalLightOff": off,
                "evidenceLevel": (
                    "native-physical-command-state"
                    if native_state_matches else
                    "native-physical-command-plus-journal-observation"
                    if off is not None else
                    "native-physical-and-command-only"
                ),
                "lockoutEffectEstablished": False,
            }
            candidates.append((
                0 if native_state_matches else 1 if off is not None else 2,
                abs((command-anchor).total_seconds()), delta,
                candidate,
            ))
    if candidates:
        _, _, _, selected = min(
            candidates, key=lambda x: (x[0], x[1], x[2])
        )
        result["candidate"] = selected
        result["nativeButtonCommandVerified"] = True
        result["journalLightOffObserved"] = bool(selected["journalLightOff"])
        result["nativeLightStateObserved"] = bool(
            result["nativeLightStateObserved"]
        )
        result["claimBoundary"] = (
            "Native physical button event and native app OFF command are "
            "independently time-linked. A journal OFF is collector-received, "
            "not a native source-clock state transition; no app lockout "
            "decision or suppression is verified by this correlation."
        )
    else:
        result["claimBoundary"] = (
            "No independent native physical-button-to-command pair has been "
            "established for the requested focal event."
        )
    return result


__all__ = ["correlate_requested_focal_sources"]

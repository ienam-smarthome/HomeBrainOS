"""Source-bounded publication for read-only telemetry explanations.

The model authors the answer. Only unsupported categorical assertions are
reconciled against typed, same-request evidence. No MCP or model calls.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from telemetry_clock_consistency import assess_telemetry_clock_consistency

_PHYSICAL_CERTAIN = re.compile(
    r"\b(?:device|sensor|plug|endpoint)\s+is\s+"
    r"(?:definitively\s+|certainly\s+|physically\s+)?"
    r"(?:offline|disconnected|dead|not\s+communicating)\b"
    r"|\b(?:device|sensor|plug|endpoint)\s+(?:has\s+)?"
    r"(?:stopped\s+communicating|lost\s+power)\b",
    re.I,
)
_DRIVER_MECHANISM = re.compile(
    r"\b(?:watchdog|healthStatus|health\s+status|driver|internal\s+timer)\b"
    r".{0,190}?\b(?:fires?|trigger(?:s|ed)?|monitors?|calculat(?:es|ed|ion)|"
    r"marks?|timeout|threshold|every\s+\d+|poll(?:s|ing)?)\b"
    r"|\b(?:live\s+calculation|internal\s+watchdog)\b"
    r"|\b(?:mqttStatus|mqtt\s+status|broker\s+status)\b.{0,140}?"
    r"\b(?:is\s+(?:a\s+)?stale|is\s+(?:a\s+)?cached|"
    r"only\s+changes|only\s+updates|last\s+known)\b",
    re.I,
)
_CAUSE_CERTAIN = re.compile(
    r"\b(?:discrepancy|conflict|mismatch|difference)\s+"
    r"is\s+(?:(?:caused|explained)\s+by|due\s+to)\b",
    re.I,
)
_WATCHDOG_MECHANISM = re.compile(
    r"\bwatchdog\b.{0,180}\b"
    r"(?:fired|fires|triggered|every|timeout|threshold|without\s+data|"
    r"reconnect(?:ion)?|mark(?:s|ed)|\d+\s+(?:hours?|minutes?|seconds?))\b",
    re.I,
)
_LAST_SEEN_PHYSICAL = re.compile(
    r"\blastSeen\b.{0,190}?\b(?:definitiv\w*|actually|physical\w*"
    r"|last\s+(?:piece|packet|time)|last\s+contact|last\s+telemetry)\b",
    re.I,
)
_DATA_AGE_PHYSICAL = re.compile(
    r"\bdataAgeSeconds\b.{0,190}?\b"
    r"(?:actual|physical\w*|last\s+(?:piece|packet|telemetry)"
    r"|received\s+(?:approximate|around|about))\b",
    re.I,
)
_NO_DISCONNECT = re.compile(
    r"\b(?:no\s+(?:such\s+)?(?:disconnect|disconnection)\s+"
    r"(?:message|event|notification)\s+(?:was|has\s+been)\s+(?:received|seen|recorded)"
    r"|never\s+(?:received|saw|recorded)\s+(?:a\s+)?disconnect"
    r"|because\s+no\s+such\s+message\s+was\s+received)\b",
    re.I,
)
_QUALIFIED = re.compile(
    r"\b(?:could|might|may|possibly|hypothes\w*|unverified|unproven"
    r"|not\s+(?:known|established|verified)|cannot\s+(?:confirm|prove))\b",
    re.I,
)


def _read_attrs(evidence: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], str]:
    for row in evidence:
        if not isinstance(row, Mapping) or row.get("success") is not True:
            continue
        if row.get("effect") != "read" or row.get("mutates") is not False:
            continue
        details = row.get("details")
        state = details.get("reportedDeviceState") if isinstance(details, Mapping) else None
        if not isinstance(state, Mapping):
            continue
        attrs = state.get("reportedAttributes")
        ident = str(state.get("deviceId") or "")
        if isinstance(attrs, Mapping) and ident.isdecimal() and int(ident) > 0:
            return dict(attrs), ident
    return {}, ""


def _has_mqtt_disconnect(evidence: Sequence[Mapping[str, Any]], ident: str) -> bool:
    """A positive event refutes no-disconnect even in a bounded history."""
    if not ident:
        return False
    for row in evidence:
        if not isinstance(row, Mapping) or row.get("success") is not True:
            continue
        if row.get("effect") != "read" or row.get("mutates") is not False:
            continue
        details = row.get("details")
        events = details.get("observedEvents") if isinstance(details, Mapping) else None
        if not isinstance(events, list):
            continue
        for event in events[:200]:
            if not isinstance(event, Mapping):
                continue
            producer = event.get("producedBy")
            if (isinstance(producer, Mapping)
                    and str(producer.get("id")) == ident
                    and str(producer.get("type")).casefold() == "device"
                    and str(event.get("name")).casefold() == "mqttstatus"
                    and str(event.get("value")).casefold() == "disconnected"):
                return True
    return False


def guard_telemetry_source_claims(
    message: str,
    evidence: Sequence[Mapping[str, Any]],
    coverage: Any,
) -> tuple[str, list[str]]:
    """Reconcile only source-impossible certainties on scoped telemetry reads."""
    original = str(message or "")
    if (not isinstance(coverage, Mapping)
            or coverage.get("domain") != "device_telemetry"
            or not original.strip()):
        return original, []
    attrs, ident = _read_attrs(evidence)
    if not attrs or not ident:
        return original, []
    authority = coverage.get("sourceAuthority")
    authority = authority if isinstance(authority, Mapping) else {}
    target_id = str(authority.get("targetDeviceId") or "")
    if target_id and target_id != ident:
        # Another target's health state cannot authorise a correction here.
        return original, []
    depth = coverage.get("incidentReasoningDepth")
    depth = depth if isinstance(depth, Mapping) else {}
    driver_verified = (
        authority.get("verifiedInstalledDriverBehaviour") is True
        and depth.get("driverMethodBehaviourVerified") is True
    )
    physical_verified = (
        authority.get("physicalCauseEstablished") is True
        and authority.get("independentBrokerPacketsVerified") is True
    )
    clock = assess_telemetry_clock_consistency(list(evidence))
    clock_conflict = bool(clock and clock.get("sourcesAgree") is False)
    disconnected = _has_mqtt_disconnect(evidence, ident)
    health, mqtt = attrs.get("healthStatus"), attrs.get("mqttStatus")
    reported_state = (
        f"Hubitat reports healthStatus={health!s} and mqttStatus={mqtt!s}; "
        "these saved attributes do not independently verify endpoint "
        "connectivity or broker message delivery."
        if health is not None and mqtt is not None else
        "The reported device-health and transport attributes do not "
        "independently establish physical endpoint connectivity."
    )
    if disconnected:
        reported_state += (
            " Bounded device history also includes MQTT disconnect reports; "
            "an absence of disconnect messages has not been established."
        )
    clock_note = ""
    if clock_conflict:
        clock_note = (
            "The stored lastSeen implies approximately "
            f"{clock['metadataAgeHoursAtRead']} hours at read time, "
            "whereas dataAgeSeconds reports approximately "
            f"{clock['reportedDataAgeHours']} hours. They disagree; "
            "neither verifies last physical-telemetry contact."
        )
    elif clock and clock.get("physicalTelemetryProven") is not True:
        clock_note = (
            "Stored lastSeen and reported dataAgeSeconds are Hubitat metadata; "
            "neither independently verifies the time of the last physical "
            "device-originated telemetry packet."
        )
    driver_note = (
        "The installed driver's status-update and watchdog implementation "
        "were not verified by source. Event and log reads alone cannot "
        "establish which method or timeout caused the reported state."
    )
    notes = {
        "physical": reported_state,
        "driver": driver_note,
        "clock": clock_note,
        "disconnect": (
            "The bounded device event history contains an MQTT disconnect "
            "report; this does not independently verify current broker "
            "traffic or endpoint responsiveness."
            if disconnected else
            "A bounded event history cannot prove no MQTT disconnect "
            "message was received."
        ),
    }
    issues: list[str] = []
    used_notes: set[str] = set()
    lines: list[str] = []
    for source_line in original.splitlines(keepends=True):
        line = source_line.rstrip("\r\n")
        ending = source_line[len(line):]
        if not line.strip():
            lines.append(source_line)
            continue
        key = ""
        physical_match = _PHYSICAL_CERTAIN.search(line)
        physical_preceding = (
            line[max(0, physical_match.start() - 42):physical_match.start()]
            if physical_match is not None else ""
        )
        physical_qualified = bool(_QUALIFIED.search(physical_preceding))
        if not physical_verified and physical_match and not physical_qualified:
            key = "physical"
        elif clock_note and (
            _LAST_SEEN_PHYSICAL.search(line) or _DATA_AGE_PHYSICAL.search(line)
        ):
            key = "clock"
        elif (not driver_verified and
              (_DRIVER_MECHANISM.search(line) or _WATCHDOG_MECHANISM.search(line)
               or _CAUSE_CERTAIN.search(line))
              and not _QUALIFIED.search(line)):
            key = "driver"
        elif _NO_DISCONNECT.search(line):
            key = "disconnect"
        if not key or not notes[key]:
            lines.append(source_line)
            continue
        if key not in used_notes:
            prefix = re.match(r"^(\s*(?:[-*•]\s*)?)", line).group(1)
            lines.append(prefix + notes[key] + ending)
            used_notes.add(key)
        issues.append("telemetry_" + key + "_claim_unverified")
    return "".join(lines), list(dict.fromkeys(issues))


__all__ = ["guard_telemetry_source_claims"]

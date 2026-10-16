"""Corroborate timestamps of reported device metadata without inferring delivery.

A Hubitat device's stored lastSeen text and dataAgeSeconds may represent
different update pipelines. This is an evidence-quality check, not a claim
that physical telemetry, electrical power, or MQTT delivery was verified.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from zoneinfo import ZoneInfo


def _parse_last_seen(raw: Any) -> datetime | None:
    value = str(raw or "").strip()
    if not value or len(value) > 90:
        return None
    match = re.fullmatch(
        r"(?:[A-Za-z]{3}\s+)?([A-Za-z]{3}\s+\d{1,2}\s+"
        r"\d{2}:\d{2}:\d{2})\s+(BST|GMT)\s+(\d{4})", value
    )
    if not match:
        return None
    try:
        naive = datetime.strptime(
            f"{match.group(1)} {match.group(3)}",
            "%b %d %H:%M:%S %Y",
        )
        aware = naive.replace(tzinfo=ZoneInfo("Europe/London"))
        # Fail closed on a timezone abbreviation inconsistent with that date.
        if aware.tzname() != match.group(2):
            return None
        return aware
    except (ValueError, OverflowError):
        return None


def _parse_observed_at(raw: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def assess_telemetry_clock_consistency(
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compare overlapping as-of and age claims, not a hypothetical live age."""
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        state = details.get("reportedDeviceState")
        if not isinstance(state, dict):
            continue
        attrs = state.get("reportedAttributes")
        if not isinstance(attrs, dict):
            continue
        source_time = _parse_last_seen(attrs.get("lastSeen"))
        observed = _parse_observed_at(state.get("observedAt"))
        try:
            age = float(attrs.get("dataAgeSeconds"))
        except (TypeError, ValueError):
            continue
        if not (source_time and observed and 0 <= age <= 10**9):
            continue
        delta = (observed - source_time).total_seconds()
        if delta < 0:
            continue
        tolerance = max(15 * 60, age * .1)
        consistent = abs(delta - age) <= tolerance
        return {
            "deviceId": str(state.get("deviceId") or "")[:24],
            "metadataLastSeen": source_time.isoformat(),
            "metadataAgeHoursAtRead": round(delta / 3600, 1),
            "reportedDataAgeHours": round(age / 3600, 1),
            "sourcesAgree": consistent,
            "physicalTelemetryProven": False,
            "physicalPowerProvenByMqttStatus": False,
        }
    return None


def render_telemetry_clock_qualification(check: dict[str, Any]) -> str:
    if check.get("sourcesAgree") is True:
        return (
            "**Telemetry provenance:** The stored lastSeen date and reported "
            "data-age value are approximately consistent, but both are Hubitat "
            "metadata and neither alone verifies physical responsiveness."
        )
    return (
        "**Telemetry timing conflict:** The stored lastSeen timestamp implies "
        f"approximately {check['metadataAgeHoursAtRead']} hours at the read, "
        f"whereas dataAgeSeconds reports {check['reportedDataAgeHours']} hours. "
        "These metadata values disagree and may reflect different clocks or "
        "reporting pipelines; do not use either as a verified physical "
        "last-contact timestamp. A reported MQTT 'connected' status alone "
        "cannot establish that the device is powered or accepting commands."
    )


__all__ = [
    "assess_telemetry_clock_consistency",
    "render_telemetry_clock_qualification",
]

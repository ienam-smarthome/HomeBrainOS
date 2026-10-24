"""Source-scoped, bounded extraction of repeated watchdog no-data evidence."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

_WATCHDOG = re.compile(
    r"watchdog\s+fired\s+after\s+(\d{1,9})s\s+without\s+data",
    re.I,
)


def summarize_device_watchdog(
    evidence: list[dict[str, Any]], device_id: str,
) -> dict[str, Any] | None:
    """Read only logs explicitly filtered to the exact device ID.

    `logCount` can exceed the rows embedded in public receipts. Extract only
    actual supplied rows; don't imply the full log page was processed.
    """
    ident = str(device_id or "")
    if not ident.isdigit():
        return None
    records: list[tuple[str, int]] = []
    matched_receipts = 0
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("sub_tool") != "hub_get_logs":
            continue
        args = receipt.get("arguments") or {}
        if not isinstance(args, dict):
            continue
        if isinstance(args.get("args"), dict):
            args = args["args"]
            if isinstance(args.get("args"), dict):
                args = args["args"]
        if str(args.get("deviceId") or "") != ident:
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict) or not isinstance(details.get("logs"), list):
            continue
        matched_receipts += 1
        for row in details["logs"][:100]:
            if not isinstance(row, dict):
                continue
            message = str(row.get("message") or "")
            if not message.startswith(f"dev|{ident}|"):
                continue
            match = _WATCHDOG.search(message)
            date = str(row.get("date") or "")
            if match and date and len(date) <= 40:
                records.append((date, int(match.group(1))))
    if not matched_receipts or not records:
        return None
    unique = sorted(set(records))
    return {
        "deviceId": ident,
        "sampledWarnings": len(unique),
        "oldestSample": unique[0][0],
        "latestSample": unique[-1][0],
        "oldestSecondsWithoutData": unique[0][1],
        "latestSecondsWithoutData": unique[-1][1],
        "latestGapHours": round(unique[-1][1] / 3600, 2),
        "indicatesRepeatedNoData": len(unique) > 1,
        "physicalCauseEstablished": False,
        "recoveryConfirmed": False,
        "receiptCoverageComplete": False,
    }



def correlate_elapsed_watchdog_with_device_events(
    evidence: list[dict[str, Any]], device_id: str,
) -> dict[str, Any] | None:
    """Find *observed* event alignment with a stable elapsed-time counter.

    A repeated log statement 'fired after Ns without data' lets us calculate
    the counter's apparent reference time without assuming that the counter
    measures a physical packet. Align only same-device typed event rows.
    Hubitat's native log dates omit their timezone, so compare local wall
    times only and disclose the assumption. Never equate a match with
    physical connectivity, causal ordering or driver implementation.
    """
    ident = str(device_id or "")
    if not ident.isdigit():
        return None
    references: list[datetime] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("sub_tool") != "hub_get_logs":
            continue
        args = receipt.get("arguments") or {}
        for _ in range(3):
            if not isinstance(args, dict) or not isinstance(args.get("args"), dict):
                break
            args = args["args"]
        if not isinstance(args, dict) or str(args.get("deviceId") or "") != ident:
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        for row in (details.get("logs") or [])[:150]:
            if not isinstance(row, dict):
                continue
            message = str(row.get("message") or "")
            if not message.startswith(f"dev|{ident}|"):
                continue
            match = _WATCHDOG.search(message)
            if not match:
                continue
            try:
                log_clock = datetime.fromisoformat(str(row.get("date") or ""))
                seconds = int(match.group(1))
                if log_clock.tzinfo is not None or seconds <= 0:
                    continue
                references.append(log_clock - timedelta(seconds=seconds))
            except (ValueError, OverflowError):
                continue
    # Repeated independent warning timestamps are necessary to establish
    # consistency: one warning alone might be malformed or a false match.
    unique = sorted(set(references))
    if len(unique) < 2:
        return None
    spread = (unique[-1] - unique[0]).total_seconds()
    if spread > 2.0:
        return None
    anchor = unique[len(unique) // 2]
    candidates = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        events = details.get("observedEvents")
        if not isinstance(events, list):
            continue
        for event in events[:200]:
            if not isinstance(event, dict):
                continue
            producer = event.get("producedBy") or {}
            if not isinstance(producer, dict) or str(producer.get("id") or "") != ident:
                continue
            raw_stamp = event.get("date")
            try:
                timestamp = datetime.fromisoformat(str(raw_stamp or ""))
            except ValueError:
                continue
            # Same local clock is a hypothesis, not verified by these receipts.
            wall_time = timestamp.replace(tzinfo=None)
            delta = abs((wall_time - anchor).total_seconds())
            if delta <= 2.0:
                candidates.append((
                    delta,
                    str(event.get("name") or event.get("attribute") or ""),
                    str(event.get("value") or ""),
                    str(raw_stamp),
                ))
    if not candidates:
        return None
    match = min(candidates)
    return {
        "deviceId": ident,
        "referenceTimeLocal": anchor.isoformat(sep=" ", timespec="milliseconds"),
        "referenceSpreadSeconds": round(spread, 3),
        "sampledDistinctWarningTimes": len(unique),
        "matchingEvent": {
            "attribute": match[1][:80], "value": match[2][:120],
            "timestamp": match[3][:64],
        },
        "differenceSeconds": round(match[0], 3),
        "clockAlignmentAssumed": True,
        "counterMeaningVerified": False,
        "devicePacketTimeVerified": False,
        "rootCauseVerified": False,
    }


def render_elapsed_watchdog_correlation(correlation: dict[str, Any]) -> str:
    event = correlation["matchingEvent"]
    return (
        "**Watchdog timing correlation:** Across "
        f"{correlation['sampledDistinctWarningTimes']} sampled warnings, "
        "subtracting each logged elapsed-no-data duration yields a stable "
        f"reference around {correlation['referenceTimeLocal']} "
        f"(spread {correlation['referenceSpreadSeconds']:.3f} s). "
        "This coincides (within "
        f"{correlation['differenceSeconds']:.3f} s) with the recorded "
        f"{event['attribute']}={event['value']} event at {event['timestamp']}. "
        "The calculation assumes Hubitat log wall times and device-event "
        "local times use the same clock. This may identify when a software "
        "watchdog reference was initialised or reset; it does NOT verify the "
        "last physical packet, a broker connection, or the reason for the "
        "counter value. Driver method analysis is needed before concluding."
    )


def render_device_watchdog(summary: dict[str, Any]) -> str:
    message = (
        "**Watchdog execution evidence:** "
        f"{summary['sampledWarnings']} source-scoped warning(s) in the "
        "provided log excerpt. "
        f"At {summary['latestSample']}, the watchdog reported "
        f"{summary['latestSecondsWithoutData']:,} seconds "
        f"(about {summary['latestGapHours']:.2f} hours) without data."
    )
    if summary["indicatesRepeatedNoData"]:
        message += (
            f" Earlier sampled warnings begin at {summary['oldestSample']} "
            f"with {summary['oldestSecondsWithoutData']:,} seconds. "
            "The sequence supports repeated no-data detection and recovery "
            "attempts, not successful reconnection."
        )
    return (
        message
        + " This does not independently identify physical power, broker, "
          "network or driver failure. The log excerpt and historical "
          "collection are not guaranteed complete."
    )


__all__ = ["summarize_device_watchdog", "render_device_watchdog", "correlate_elapsed_watchdog_with_device_events", "render_elapsed_watchdog_correlation"]

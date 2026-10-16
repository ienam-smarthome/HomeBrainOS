"""Source-scoped, bounded extraction of repeated watchdog no-data evidence."""
from __future__ import annotations

import re
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


__all__ = ["summarize_device_watchdog", "render_device_watchdog"]

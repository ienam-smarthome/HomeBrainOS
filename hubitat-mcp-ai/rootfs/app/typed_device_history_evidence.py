"""Normalized, target-scoped Hubitat event evidence for device health investigations.

Prefer successful direct deviceId-scoped hub_list_device_events receipts, which
may contain both command invocations and state events, over summaries extracted
from model prose. Query scope, freshness, source integrity and producer type are
distinct proof classes. This module never asserts physical command delivery.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def _args(receipt: dict[str, Any]) -> dict[str, Any]:
    supplied = receipt.get("arguments") or {}
    if not isinstance(supplied, dict):
        return {}
    nested = supplied.get("args")
    return nested if isinstance(nested, dict) else supplied


def _kind(event: dict[str, Any]) -> str:
    name = str(event.get("name") or "")
    if name.startswith("command-") or event.get("type") == "command":
        return "command"
    return "state"


def _producer_label(event: dict[str, Any]) -> str:
    producer = event.get("producedBy")
    if not isinstance(producer, dict):
        return "unattributed"
    return str(producer.get("label") or producer.get("name") or "unattributed")


def _target_label(evidence: list[dict[str, Any]], target_id: str) -> str:
    # The target identity is resolved from a successful ID-filtered device
    # lookup, not from an arbitrary name embedded in a state event.
    for row in evidence:
        if (not isinstance(row, dict) or row.get("success") is not True
                or row.get("sub_tool") != "hub_list_devices"):
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        candidates = details.get("devices") or []
        if isinstance(candidates, list):
            for match in candidates:
                if isinstance(match, dict) and str(match.get("id") or "") == target_id:
                    return str(match.get("label") or match.get("name") or "")
        requested = str(_args(row).get("labelFilter") or "").strip()
        if requested and row.get("summary") == "1 targeted device candidates":
            return requested
    return ""


def normalize_target_device_history(
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Extract one correctly scoped authoritative event page.

    If different devices were inspected, do not silently combine them.
    Prefer the widest checked window with the greatest number of returned
    records for that target. Event count does NOT indicate complete history.
    """
    candidates: list[tuple[int, int, dict[str, Any], list[dict[str, Any]]]] = []
    for receipt in evidence:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("sub_tool") != "hub_list_device_events"):
            continue
        args = _args(receipt)
        target_id = str(args.get("deviceId") or "").strip()
        if not target_id.isdigit():
            continue
        # Exclude switch-only or command-only attribute queries: this evidence
        # class requires an unfiltered mixed history for source comparison.
        if str(args.get("attribute") or "").strip():
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        if details.get("deviceId") not in (None, "", target_id):
            continue
        rows = details.get("observedEvents")
        if not isinstance(rows, list):
            rows = details.get("events")
        if not isinstance(rows, list):
            continue
        count = len([row for row in rows if isinstance(row, dict)])
        hours = int(args.get("hoursBack") or 0) if str(args.get("hoursBack") or "").isdigit() else 0
        candidates.append((hours, count, receipt, rows))
    if not candidates:
        return None

    scoped_ids = {
        str(_args(c[2]).get("deviceId") or "")
        for c in candidates
    }
    # Never confuse investigations spanning multiple targets with evidence
    # scoped to a single device; callers must select a device explicitly.
    if len(scoped_ids) != 1:
        return None
    hours, _, receipt, source = max(candidates, key=lambda c: (c[0], c[1]))
    target_id = next(iter(scoped_ids))
    checked_at = _timestamp(receipt.get("timestamp"))
    commands, states = [], []
    for event in source:
        if not isinstance(event, dict):
            continue
        event_at = _timestamp(event.get("date") or event.get("timestamp"))
        if _kind(event) == "command":
            commands.append({
                "command": str(event.get("name") or "command"),
                "date": event_at.isoformat() if event_at else None,
                "producer": _producer_label(event),
            })
        else:
            producer = event.get("producedBy") or {}
            if not isinstance(producer, dict):
                producer = {}
            # These are *Hubitat-recorded* events, not confirmed hardware
            # MQTT/Zigbee frames, even when attributed to a device ID.
            source_id = str(producer.get("deviceId") or producer.get("id") or "")
            states.append({
                "attribute": str(event.get("name") or "unknown"),
                "value": event.get("value"),
                "date": event_at.isoformat() if event_at else None,
                "producer": _producer_label(event),
                "deviceAttributed": (
                    source_id == target_id and (
                        producer.get("type") in (None, "", "device")
                    )
                ),
            })
    latest = max((e for e in states if e["date"]), key=lambda e: e["date"], default=None)
    age = next((
        {
            "value": state["value"],
            "recordedAt": state["date"],
            "isFreshMeasurement": False,
        } for state in sorted(
            states, key=lambda e: e["date"] or "", reverse=True,
        ) if state["attribute"] == "dataAgeSeconds"
    ), None)
    detail = receipt.get("details") or {}
    truncated = detail.get("observedEventsTruncated") is True
    groups: dict[tuple[str, str], int] = {}
    for item in commands:
        key = (item["producer"], item["command"])
        groups[key] = groups.get(key, 0) + 1
    return {
        "deviceId": target_id,
        "deviceLabel": _target_label(evidence, target_id),
        "queryWindowHours": hours or None,
        "receiptCheckedAt": checked_at.isoformat() if checked_at else None,
        "returnedEvents": len(commands) + len(states),
        "commandCount": len(commands),
        "stateEventCount": len(states),
        "truncated": truncated,
        "sourceIntegrityVerified": detail.get("historySourceIntegrityVerified") is True,
        "latestReturnedStateEvent": latest,
        "historicalDataAgeSeconds": age,
        "commandGroups": [
            {"producer": producer, "command": name, "count": count}
            for (producer, name), count in sorted(
                groups.items(), key=lambda kv: (-kv[1], kv[0])
            )
        ],
        "commandTimes": [row["date"] for row in commands if row["date"]],
        "acknowledgementVerified": False,
        "physicalCommunicationVerified": False,
        "eventHistoryComplete": False,
        "scope": "target-device-mixed-bounded-event-page",
    }


def render_target_device_evidence_answer(
    evidence: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    """Stable factual projection; do not promote model causal speculation."""
    label = summary.get("deviceLabel") or "Device " + str(summary["deviceId"])
    window = summary.get("queryWindowHours")
    window_text = f"{window}-hour" if window else "bounded"
    lines = [
        f"### Investigation: {label}",
        f"**Event evidence:** Hubitat returned {summary['returnedEvents']} "
        f"records for device {summary['deviceId']} in a {window_text} query: "
        f"{summary['commandCount']} command invocations and "
        f"{summary['stateEventCount']} state/attribute events.",
    ]
    latest = summary.get("latestReturnedStateEvent")
    if isinstance(latest, dict):
        lines.append(
            "**Latest returned state event:** "
            f"{latest['attribute']}={latest.get('value')} at "
            f"{latest.get('date') or 'an unverified timestamp'}, reported by "
            f"{latest.get('producer') or 'an unverified source'}. "
            "This is a recorded Hubitat event, not independent proof of "
            "a live physical MQTT/Zigbee packet."
        )
    else:
        lines.append(
            "**State history:** No state or attribute event was found in "
            "the returned bounded records. This is not proof that physical "
            "telemetry never arrived."
        )
    age = summary.get("historicalDataAgeSeconds")
    if isinstance(age, dict):
        lines.append(
            f"**Stored telemetry age:** dataAgeSeconds={age['value']} "
            f"was recorded at {age['recordedAt']}, not freshly recalculated."
        )
    else:
        lines.append(
            "**Telemetry age:** A fresh age of the last physical packet "
            "has not been established by the returned event records. "
            "Cached lastSeen/dataAgeSeconds attributes require their "
            "original measurement timestamps."
        )
    lines.append("**Recorded command sources:**")
    for group in summary.get("commandGroups") or []:
        name = str(group["command"]).removeprefix("command-")
        lines.append(
            f"- {group['producer']}: {group['count']} recorded {name}() "
            "invocation" + ("" if group["count"] == 1 else "s")
        )
    lines.append(
        "**Command outcomes:** Command invocations are recorded. No "
        "end-to-end device acknowledgement or command delivery was "
        "independently verified in these sources; the absence of a "
        "matching state-change record does not prove failed execution."
    )
    matching_logs = [
        row for row in evidence
        if isinstance(row, dict) and row.get("success") is True
        and row.get("sub_tool") == "hub_get_logs"
        and str(_args(row).get("deviceId") or "") == str(summary["deviceId"])
    ]
    if matching_logs:
        lines.append(
            "**Device-scoped logs:** A device-ID-filtered log query was "
            "performed. Findings are limited to its requested period."
        )
    else:
        lines.append(
            "**Device-scoped logs:** No verified log read filtered to this "
            "device ID was found. Unfiltered and app-name-matching logs "
            "cannot establish the device's full error or watchdog history."
        )
    if summary.get("truncated"):
        lines.append(
            "**History integrity:** The returned event page is explicitly "
            "truncated. Older events and command/response boundaries may "
            "be omitted."
        )
    else:
        lines.append(
            "**History integrity:** This bounded result has not been "
            "independently verified as a complete history."
        )
    lines.append(
        "**Assessment:** Device health and cached connectivity attributes "
        "should be interpreted as reported values, not physical status "
        "confirmed by this event stream. Current reachability, precise "
        "telemetry freshness and the cause of any outage remain unverified."
    )
    return "\n\n".join(lines)


__all__ = [
    "normalize_target_device_history",
    "render_target_device_evidence_answer",
]

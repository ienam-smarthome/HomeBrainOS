"""Normalized, target-scoped Hubitat event evidence for device health investigations.

Prefer successful direct deviceId-scoped hub_list_device_events receipts, which
may contain both command invocations and state events, over summaries extracted
from model prose. Query scope, freshness, source integrity and producer type are
distinct proof classes. This module never asserts physical command delivery.
"""
from __future__ import annotations

from device_watchdog_evidence import (
    summarize_device_watchdog, render_device_watchdog,
    correlate_elapsed_watchdog_with_device_events,
    render_elapsed_watchdog_correlation,
)

from skill_decision_summary import telemetry_skill_conclusion

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
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



def _join_derived_event_rows(
    evidence: list[dict[str, Any]],
    direct: dict[str, Any],
    target_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Associate a direct ID-scoped query with its immediate derived result.

    The direct receipt may omit large event arrays while its paired,
    deterministic homebrain_device_history receipt preserves them. Require
    a resolved target label, the direct source event count, the same history
    window and near-adjacent read times. Never join a different device's
    history or unrelated prior source data.
    """
    label = _target_label(evidence, target_id)
    direct_time = _timestamp(direct.get("timestamp"))
    hours = str(_args(direct).get("hoursBack") or "")
    summary = str(direct.get("summary") or "")
    count_match = re.fullmatch(
        r"(\d+)\s+device events for '([^']+)'", summary
    )
    if (
        not label or direct_time is None or count_match is None
        or count_match.group(2).casefold() != label.casefold()
    ):
        return None
    expected_count = int(count_match.group(1))
    if expected_count <= 0:
        return None
    matches = []
    for row in evidence:
        if (
            not isinstance(row, dict)
            or row.get("success") is not True
            or row.get("tool") != "homebrain_device_history"
        ):
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict):
            continue
        derived_label = str(details.get("label") or "")
        if derived_label.casefold() != label.casefold():
            continue
        if hours and str(details.get("hoursBack") or "") != hours:
            continue
        rows = details.get("observedEvents")
        if (
            not isinstance(rows, list)
            or len(rows) != expected_count
            or not all(isinstance(item, dict) for item in rows)
        ):
            continue
        time = _timestamp(row.get("timestamp"))
        if time is None:
            continue
        delta = (time - direct_time).total_seconds()
        if 0 <= delta <= 10.0:
            matches.append((delta, rows, details))
    # Conflicting matches cannot be resolved by choosing the most
    # convenient source. One immediate derived receipt is required.
    if len(matches) != 1:
        return None
    return matches[0][1], matches[0][2]



def _reported_target_health(
    evidence: list[dict[str, Any]], target_id: str,
) -> dict[str, Any] | None:
    """Read only ID-matching snapshots from successful targeted live lookups."""
    matches = []
    for receipt in evidence:
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is not True
            or receipt.get("sub_tool") != "hub_list_devices"
        ):
            continue
        details = receipt.get("details") or {}
        state = details.get("reportedDeviceState") if isinstance(details, dict) else None
        if (
            isinstance(state, dict)
            and str(state.get("deviceId") or "") == target_id
            and state.get("source") == "targeted-hubitat-device-state"
        ):
            matches.append(state)
    return dict(matches[-1]) if matches else None



def normalize_target_device_history(
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Extract one correctly scoped authoritative event page.

    If different devices were inspected, do not silently combine them.
    Prefer the widest checked window with the greatest number of returned
    records for that target. Event count does NOT indicate complete history.
    """
    candidates: list[tuple[int, int, dict[str, Any], list[dict[str, Any]], dict[str, Any], bool]] = []
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
        joined = False
        if not isinstance(rows, list):
            paired = _join_derived_event_rows(
                evidence, receipt, target_id,
            )
            if paired is None:
                continue
            rows, details = paired
            joined = True
        count = len([row for row in rows if isinstance(row, dict)])
        hours = int(args.get("hoursBack") or 0) if str(args.get("hoursBack") or "").isdigit() else 0
        candidates.append((hours, count, receipt, rows, details, joined))
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
    hours, _, receipt, source, source_details, was_joined = max(
        candidates, key=lambda c: (c[0], c[1])
    )
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
    detail = source_details
    truncated = detail.get("observedEventsTruncated") is True
    groups: dict[tuple[str, str], int] = {}
    for item in commands:
        key = (item["producer"], item["command"])
        groups[key] = groups.get(key, 0) + 1
    return {
        "deviceId": target_id,
        "deviceLabel": _target_label(evidence, target_id),
        "reportedDeviceState": _reported_target_health(evidence, target_id),
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
        "joinedDerivedHistory": was_joined,
        "eventSource": ("verified-direct-derived-receipt-pair" if was_joined
                        else "direct-id-scoped-event-receipt"),
    }



def reported_telemetry_consistency(reported: dict[str, Any]) -> str | None:
    """Flag contradictions in cached attributes without claiming transport status."""
    values = reported.get("reportedAttributes") or {}
    if not isinstance(values, dict):
        return None
    last_seen = str(values.get("lastSeen") or "")
    raw_age = values.get("dataAgeSeconds")
    read_at = _timestamp(reported.get("observedAt"))
    if not last_seen or raw_age is None or read_at is None:
        return None
    try:
        age = float(raw_age)
        # Hubitat's driver exposes human-formatted local BST/GMT dates here.
        cleaned = re.sub(r"\s+(BST|GMT)\s+", " ", last_seen)
        observed_local = datetime.strptime(cleaned, "%a %b %d %H:%M:%S %Y")
        observed_local = observed_local.replace(tzinfo=ZoneInfo("Europe/London"))
        age_from_seen = (read_at - observed_local).total_seconds()
    except (ValueError, TypeError, OverflowError):
        return None
    if age < 0 or age_from_seen < 0:
        return "Cached telemetry timestamps appear inconsistent (future/negative age)."
    disagreement = abs(age - age_from_seen)
    if disagreement <= 300:
        return None
    return (
        "Cached telemetry timestamps disagree: lastSeen implies "
        f"approximately {age_from_seen / 3600:.1f} hours before this read, "
        f"while dataAgeSeconds implies {age / 3600:.1f} hours "
        f"(difference {disagreement / 3600:.1f} hours). "
        "These fields may use different update/reference times; "
        "neither establishes a fresh device-originated packet."
    )


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
    ]
    skill_verdict = telemetry_skill_conclusion(summary)
    if skill_verdict:
        lines.append(skill_verdict)
    lines += [
        f"**Event evidence:** Hubitat returned {summary['returnedEvents']} "
        f"records for device {summary['deviceId']} in a {window_text} query: "
        f"{summary['commandCount']} command invocations and "
        f"{summary['stateEventCount']} state/attribute events.",
    ]
    reported = summary.get("reportedDeviceState")
    if isinstance(reported, dict):
        values = reported.get("reportedAttributes") or {}
        if isinstance(values, dict) and values:
            fields = ", ".join(
                f"{key}={values[key]}" for key in (
                    "healthStatus", "mqttStatus", "switch",
                    "lastActivity", "lastSeen", "dataAgeSeconds",
                ) if key in values
            )
            if fields:
                lines.append(
                    "**Reported state at targeted Hubitat read "
                    f"({reported.get('observedAt') or 'time unverified'}):** "
                    + fields + ". These are saved driver attributes observed "
                    "at the read time, not independently verified physical "
                    "transport or original measurement timestamps."
                )
    if isinstance(reported, dict):
        consistency = reported_telemetry_consistency(reported)
        if consistency:
            lines.append("**Telemetry consistency:** " + consistency)
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
    groups = summary.get("commandGroups") or []
    if groups:
        lines.append("**Recorded command sources:**")
    for group in groups:
        name = str(group["command"]).removeprefix("command-")
        lines.append(
            f"- {group['producer']}: {group['count']} recorded {name}() "
            "invocation" + ("" if group["count"] == 1 else "s")
        )
    # Preserve the source-bounded absence and delivery qualification, but
    # never show an empty "Recorded command sources" section.
    if summary.get("commandCount"):
        lines.append(
            "**Command evidence:** Recorded commands cannot establish "
            "physical delivery, execution or response."
        )
    else:
        lines.append(
            "**Command evidence:** No command invocation was returned in "
            "this bounded sample; physical command delivery cannot be "
            "inferred or excluded from the available events."
        )
    matching_logs = [
        row for row in evidence
        if isinstance(row, dict) and row.get("success") is True
        and row.get("sub_tool") == "hub_get_logs"
        and str(_args(row).get("deviceId") or "") == str(summary["deviceId"])
    ]
    if matching_logs:
        counts = [
            (row.get("details") or {}).get("logCount")
            for row in matching_logs
        ]
        numeric = [n for n in counts if type(n) is int]
        if numeric and len(numeric) == len(matching_logs):
            total = sum(numeric)
            lines.append(
                f"**Device-scoped logs:** {total} entries returned from "
                "device-ID-filtered log queries. An empty bounded log window "
                "does not prove the device was working or failing."
            )
        else:
            lines.append(
                "**Device-scoped logs:** A device-ID-filtered log query was "
                "performed, but a verified entry count was not retained. "
                "Findings are limited to the queried period."
            )
    else:
        lines.append(
            "**Device-scoped logs:** No verified log read filtered to this "
            "device ID was found. Unfiltered and app-name-matching logs "
            "cannot establish the device's full error or watchdog history."
        )
    watchdog = summarize_device_watchdog(evidence, str(summary["deviceId"]))
    if watchdog is not None:
        lines.append(render_device_watchdog(watchdog))
        # Derive a counter-reference alignment only from multiple exact
        # device-scoped warning rows plus target-origin event timestamps.
        # This is a temporal clue, never a physical last-contact assertion.
        alignment = correlate_elapsed_watchdog_with_device_events(
            evidence, str(summary["deviceId"]),
        )
        if alignment is not None:
            lines.append(render_elapsed_watchdog_correlation(alignment))
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
    if skill_verdict:
        lines.append(
            "**Most useful next checks (read-only):** Inspect the device or "
            "gateway's source-side telemetry/broker status and original "
            "last-packet timestamp, then compare it with the Hubitat driver "
            "attributes. Check physical power/network reachability separately. "
            "Avoid sending commands to test reachability without permission."
        )
    return "\n\n".join(lines)


__all__ = [
    "normalize_target_device_history",
    "render_target_device_evidence_answer",
    "reported_telemetry_consistency",
]

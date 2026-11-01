"""Read-only, cross-episode correlation of source-timed inputs and commands.

This module is deliberately not a causal attribution oracle. A controller
listener and a preceding source-reported sensor transition support a temporal
pattern, not the internal execution branch or physical actuation. The source
scope, device identity and app producer stay explicit at every step.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any


_MAX_ROWS = 120
_MAX_LAG_SECONDS = 120.0
_CLUSTER_TOLERANCE_SECONDS = 1.5
_MIN_REPEATS = 3
_SENSOR_ATTRIBUTES = {"motion", "presence", "occupancy"}
_INACTIVE = {"inactive", "not present", "absent", "clear", "unoccupied", "off"}


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _id(value: Any) -> str:
    raw = str(value or "").strip()
    return raw if raw.isascii() and raw.isdecimal() and 1 <= len(raw) <= 12 else ""


def _arguments(receipt: dict[str, Any]) -> dict[str, Any]:
    args = receipt.get("arguments")
    if not isinstance(args, dict):
        return {}
    if isinstance(args.get("args"), dict):
        return args["args"]
    return args


def _events(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    details = receipt.get("details")
    if not isinstance(details, dict):
        return []
    # Boundary events can contain a verified transition evicted from the
    # limited observedEvents view; deduplicate across both receipts and pages.
    events = []
    for name in ("events", "boundaryEvents", "observedEvents"):
        rows = details.get(name)
        if isinstance(rows, list):
            events.extend(row for row in rows[:_MAX_ROWS] if isinstance(row, dict))
    return events


def _producer_app_id(event: dict[str, Any]) -> str:
    producer = event.get("producedBy")
    if not isinstance(producer, dict):
        return ""
    # A triggered listener is NOT a command issuer.
    kind = str(producer.get("type") or "").casefold()
    if kind and kind != "app":
        return ""
    return _id(producer.get("appId") or producer.get("id"))


def _notified_app_ids(event: dict[str, Any]) -> set[str]:
    listeners = event.get("triggered")
    if not isinstance(listeners, list):
        return set()
    return {
        app_id for entry in listeners
        if isinstance(entry, dict)
        if (app_id := _id(entry.get("appId") or entry.get("id")))
    }


def _read_receipt(receipt: Any) -> bool:
    return (
        isinstance(receipt, dict)
        and receipt.get("success") is True
        and receipt.get("mutates") is not True
        and receipt.get("tool") in {"hub_read_devices", "homebrain_device_history"}
    )


def correlate_input_to_off_commands(receipts: Any) -> dict[str, Any]:
    """Find repeated, same-source sensor-to-issuer-command time associations.

    No inference from an absent event, app configuration or unrelated room
    name. An event is counted only with typed app command provenance and an
    explicit listener connection from the sensor history to that app.
    """
    none = {
        "schema": "cross-source-temporal-evidence/v1",
        "status": "no_repeated_source_linked_pattern",
        "patterns": [],
        "causalDecisionVerified": False,
        "physicalExecutionVerified": False,
        "historicalCoverageComplete": False,
    }
    if not isinstance(receipts, list):
        return none

    commands: dict[tuple[str, str, str], dict[str, Any]] = {}
    sensors: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for receipt in receipts:
        if not _read_receipt(receipt):
            continue
        args = _arguments(receipt)
        details = receipt.get("details")
        details = details if isinstance(details, dict) else {}
        device_id = _id(args.get("deviceId") or details.get("deviceId"))
        sensor_name = str(details.get("label") or args.get("name") or "").strip()
        attribute = str(details.get("attribute") or args.get("attribute") or "").casefold()
        for event in _events(receipt):
            stamp = _utc(event.get("date") or event.get("timestamp"))
            if stamp is None:
                continue
            event_name = str(event.get("name") or event.get("attribute") or "").casefold()
            if event_name == "command-off" and device_id:
                app_id = _producer_app_id(event)
                if app_id:
                    key = (device_id, app_id, stamp.isoformat())
                    commands[key] = {
                        "deviceId": device_id,
                        "appId": app_id,
                        "at": stamp,
                    }
                continue
            if event_name not in _SENSOR_ATTRIBUTES or attribute not in (
                "", *_SENSOR_ATTRIBUTES
            ):
                continue
            if str(event.get("value") or "").casefold() not in _INACTIVE:
                continue
            listener_ids = _notified_app_ids(event)
            if not listener_ids or not (sensor_name or device_id):
                continue
            sensor_key = device_id or sensor_name.casefold()
            for app_id in listener_ids:
                key = (sensor_key, event_name, app_id, stamp.isoformat())
                sensors[key] = {
                    "sensorId": device_id or None,
                    "sensorLabel": sensor_name or None,
                    "attribute": event_name,
                    "appId": app_id,
                    "at": stamp,
                }

    by_app: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sensor in sensors.values():
        by_app[sensor["appId"]].append(sensor)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for command in sorted(commands.values(), key=lambda item: item["at"]):
        eligible = [
            (float((command["at"] - sensor["at"]).total_seconds()), sensor)
            for sensor in by_app.get(command["appId"], ())
            if 0 <= (command["at"] - sensor["at"]).total_seconds()
            <= _MAX_LAG_SECONDS
        ]
        if not eligible:
            continue
        # A nearest observed input is only a temporal candidate; the pattern
        # requires repetitions at a consistent lag from the *same sensor*.
        for gap, sensor in eligible:
            source_key = sensor["sensorId"] or str(sensor["sensorLabel"]).casefold()
            groups[(command["deviceId"], command["appId"], source_key)].append({
                "sensorTimeUtc": sensor["at"].isoformat(),
                "commandTimeUtc": command["at"].isoformat(),
                "delaySeconds": round(gap, 3),
                "sensorId": sensor["sensorId"],
                "sensorLabel": sensor["sensorLabel"],
                "attribute": sensor["attribute"],
            })

    patterns = []
    for (target_id, app_id, sensor_key), raw in groups.items():
        # One sensor transition can yield many candidate matches in a bounded
        # page. For each observed command, count only one sensor per cluster.
        for seed in raw:
            clustered = [
                row for row in raw
                if abs(row["delaySeconds"] - seed["delaySeconds"])
                <= _CLUSTER_TOLERANCE_SECONDS
            ]
            unique = {}
            for row in clustered:
                command_time = row["commandTimeUtc"]
                if command_time not in unique or (
                    abs(row["delaySeconds"] - seed["delaySeconds"])
                    < abs(unique[command_time]["delaySeconds"]
                          - seed["delaySeconds"])
                ):
                    unique[command_time] = row
            matches = sorted(unique.values(), key=lambda row: row["commandTimeUtc"])
            if len(matches) < _MIN_REPEATS:
                continue
            # A multi-command burst is one episode, not repeated proof.
            command_times = [_utc(row["commandTimeUtc"]) for row in matches]
            if not all(
                (command_times[i] - command_times[i - 1]).total_seconds() >= 5
                for i in range(1, len(command_times))
            ):
                continue
            patterns.append({
                "deviceId": target_id,
                "appId": app_id,
                "sensorId": matches[0]["sensorId"],
                "sensorLabel": matches[0]["sensorLabel"],
                "inputAttribute": matches[0]["attribute"],
                "inputState": "inactive",
                "repeatCount": len(matches),
                "medianDelaySeconds": round(median(
                    row["delaySeconds"] for row in matches
                ), 3),
                "observedDelayRangeSeconds": [
                    min(row["delaySeconds"] for row in matches),
                    max(row["delaySeconds"] for row in matches),
                ],
                "pairs": matches[:12],
                "evidenceType": "repeated_source_linked_temporal_association",
                "triggerDecisionVerified": False,
            })
            break

    # Prefer the most replicated consistent episode; do not turn multiple
    # overlapping seed clusters into independent support.
    patterns.sort(
        key=lambda row: (-row["repeatCount"], row["deviceId"],
                         row["appId"], str(row["sensorLabel"] or ""))
    )
    if not patterns:
        return none
    return {
        **none,
        "status": "repeated_source_linked_pattern",
        "patterns": patterns[:5],
    }


def render_temporal_evidence_for_synthesis(report: Any) -> str:
    """Give the final model facts, competing interpretations and proof limits."""
    if not isinstance(report, dict) or not report.get("patterns"):
        return ""
    lines = [
        "HOST CROSS-SOURCE TEMPORAL EVIDENCE (bounded observed events, NOT "
        "a root-cause verdict):",
    ]
    for pattern in report["patterns"][:3]:
        lines.append(
            f"Target device {pattern['deviceId']}: app {pattern['appId']}"
            f" issued {pattern['repeatCount']} source-recorded OFF commands"
            f" each {pattern['medianDelaySeconds']:.3f}s median after"
            f" the same source-linked {pattern['inputAttribute']}"
            f" inactive report ({pattern['sensorLabel'] or pattern['sensorId']})."
            " Verified repeated temporal association, not verified app timer"
            " execution or physical switching."
        )
        for pair in pattern["pairs"][:8]:
            lines.append(
                f"  {pair['sensorTimeUtc']} -> "
                f"{pair['commandTimeUtc']} ({pair['delaySeconds']:.3f}s)"
            )
    lines.append(
        "Never exclude a motion/presence explanation on the basis of an empty "
        "different bounded history window. Do not invent a periodic heartbeat "
        "or fixed timer implementation from uneven command times. These pairs "
        "may concern later episodes than the user's focal incident: preserve "
        "its distinct evidence gap. Configured delay, every required sensor "
        "state and internal decision branch require their own verification."
    )
    return "\n".join(lines)


def reconcile_temporal_publication(message: str, report: Any) -> tuple[str, bool]:
    """Publish a scoped source-fact correction if a model omitted contrary data.

    This appends model-independent observation facts only. It never rewrites
    a model's unverified causal claim into a deterministic root-cause verdict.
    """
    draft = str(message or "")
    if not isinstance(report, dict) or not report.get("patterns"):
        return draft, False
    patterns = report["patterns"]
    # If the model already acknowledges the exact repeated sensor-command
    # association, leave its original prose alone.
    if (
        "source-linked" in draft.casefold()
        and "inactive" in draft.casefold()
        and "off command" in draft.casefold()
    ):
        return draft, False
    summary = []
    for item in patterns[:2]:
        summary.append(
            f"{item['repeatCount']} bounded reports from "
            f"{item['sensorLabel'] or item['sensorId']} preceded recorded"
            f" OFF commands issued by app {item['appId']} for device "
            f"{item['deviceId']} by {item['medianDelaySeconds']:.3f}s"
            " median (repeated source-linked time association)."
        )
    addition = (
        "\n\n**Additional cross-source evidence (not a causal verdict):** "
        + " ".join(summary)
        + " This supports the inactivity hypothesis for these observed "
          "episodes; it does not prove the timer branch, physical execution, "
          "or the cause of any different historical command. A periodic "
          "keep-off mechanism is not established by command cadence alone."
    )
    return draft + addition, True


__all__ = [
    "correlate_input_to_off_commands",
    "render_temporal_evidence_for_synthesis",
    "reconcile_temporal_publication",
]

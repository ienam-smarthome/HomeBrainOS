"""Compact current-turn evidence ledger for final model synthesis.

The model already receives full tool payloads during reasoning.  The ledger is a
small, deterministic reminder of which evidence sources actually succeeded in the
current request so final synthesis cannot accidentally claim that a checked source
was not provided after context compaction or a long investigative turn.

It intentionally records source presence and bounded facts only.  A CHECKED source
does not imply that the source established causation.
"""

from __future__ import annotations

import re
from typing import Any


_MAX_LEDGER_LINES = 12
_MAX_EVENT_HINTS = 6


def _inner_args(receipt: dict[str, Any]) -> dict[str, Any]:
    arguments = receipt.get("arguments")
    if not isinstance(arguments, dict):
        return {}
    inner = arguments.get("args")
    return inner if isinstance(inner, dict) else arguments


def _history_identity(receipt: dict[str, Any]) -> tuple[str, str]:
    details = receipt.get("details")
    details = details if isinstance(details, dict) else {}
    args = _inner_args(receipt)
    label = str(
        details.get("label")
        or args.get("name")
        or args.get("labelFilter")
        or ""
    ).strip()
    attribute = str(
        details.get("attribute")
        or args.get("attribute")
        or ""
    ).strip()
    return label, attribute


def _temporal_suffix(receipt: dict[str, Any]) -> str:
    details = receipt.get("details")
    if not isinstance(details, dict):
        return ""
    temporal = details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return ""
    bits: list[str] = []
    count = temporal.get("intervalCount")
    duration = temporal.get("totalActiveDuration")
    if count is not None:
        bits.append(f"{count} interval{'s' if count != 1 else ''}")
    if duration:
        bits.append(f"total {duration}")
    reliability = str(temporal.get("durationReliability") or "").strip()
    if reliability:
        bits.append(f"reliability={reliability}")

    intervals = temporal.get("boundedIntervals")
    if isinstance(intervals, list) and intervals:
        interval_hints: list[str] = []
        for interval in intervals[:6]:
            if not isinstance(interval, dict):
                continue
            start = str(interval.get("startNatural") or interval.get("start") or "").strip()
            end = str(interval.get("endNatural") or interval.get("end") or "").strip()
            span = str(interval.get("duration") or "").strip()
            if start and end:
                hint = f"{start} -> {end}"
                if span:
                    hint += f" ({span})"
                interval_hints.append(hint)
        if interval_hints:
            suffix = "; ".join(interval_hints)
            if len(intervals) > 6 or temporal.get("boundedIntervalsTruncated"):
                suffix += f"; +{max(0, len(intervals) - 6)} more"
            bits.append(f"bounded intervals: {suffix}")
    return "; ".join(bits)


def _location_event_hints(receipt: dict[str, Any]) -> str:
    details = receipt.get("details")
    if not isinstance(details, dict):
        return ""
    rows = details.get("events")
    if not isinstance(rows, list):
        return ""
    hints: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        value = str(row.get("value") or "").strip()
        date = str(row.get("date") or "").strip()
        if not (name or value):
            continue
        label = "=".join(part for part in (name, value) if part)
        if date:
            label += f" @ {date}"
        hints.append(label)
        if len(hints) >= _MAX_EVENT_HINTS:
            break
    return "; ".join(hints)


def _source_category(receipt: dict[str, Any]) -> str | None:
    tool = str(receipt.get("tool") or "")
    sub_tool = str(receipt.get("sub_tool") or "")
    kind = str(receipt.get("evidence_kind") or "")
    args = _inner_args(receipt)

    if tool == "homebrain_device_history":
        return "device_history"
    if kind == "authoritative_device_event_history":
        return "raw_device_history"
    if tool == "homebrain_location_events" or kind == "authoritative_location_event_history":
        return "location_history"
    if sub_tool == "hub_get_logs" or tool == "hub_get_logs":
        return "logs"
    if (
        "rule" in sub_tool.casefold()
        or sub_tool in {"hub_get_app_config", "hub_list_apps"}
        or "rule" in tool.casefold()
    ):
        return "rules_apps"
    if tool == "homebrain_filter_devices":
        return "device_filter"
    if (
        args.get("resource") == "hubitat://context"
        or kind == "authoritative_state_snapshot"
    ):
        return "live_context"
    return None


def checked_source_categories(receipts: list[dict[str, Any]]) -> set[str]:
    """Return successful source classes used by the current request."""

    categories: set[str] = set()
    device_histories = 0
    for receipt in receipts:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        category = _source_category(receipt)
        if category is None:
            continue
        categories.add(category)
        if category == "device_history":
            device_histories += 1
    # "related_sensor_history" means there was more than the subject history.
    # We deliberately do not infer that the extra device is actually a motion
    # sensor; the category only means additional device history was checked.
    if device_histories >= 2:
        categories.add("related_device_history")
    return categories


def _ledger_lines(receipts: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    # Prefer local deterministic history receipts over their raw upstream partner.
    local_history_labels = {
        _history_identity(receipt)[0].casefold()
        for receipt in receipts
        if isinstance(receipt, dict)
        and receipt.get("success") is True
        and receipt.get("tool") == "homebrain_device_history"
        and _history_identity(receipt)[0]
    }

    for receipt in receipts:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        category = _source_category(receipt)
        if category is None:
            continue

        if category == "raw_device_history":
            args = _inner_args(receipt)
            # Raw receipts often lack the label and duplicate a local history
            # receipt. Keep them only when no local wrapper receipt represents
            # the same evidence class.
            if local_history_labels:
                continue
            identity = str(args.get("deviceId") or "")
            key = (category, identity, "")
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- CHECKED device event history for deviceId={identity or '?'}: "
                f"{receipt.get('summary') or 'successful read'}"
            )
            continue

        if category == "device_history":
            label, attribute = _history_identity(receipt)
            key = (category, label.casefold(), attribute.casefold())
            if key in seen:
                continue
            seen.add(key)
            suffix = _temporal_suffix(receipt)
            details = receipt.get("details") or {}
            observed = details.get("observedEventNames")
            if suffix:
                summary = suffix
            elif isinstance(observed, list) and observed:
                summary = (
                    "generic history read; observed event names="
                    + ", ".join(str(name) for name in observed[:8])
                )
            else:
                summary = str(receipt.get("summary") or "successful history read")
            subject = label or "named device"
            if attribute:
                subject += f" ({attribute})"
            else:
                subject += " (attribute not explicitly selected)"
            lines.append(f"- CHECKED device history: {subject}: {summary}")
            continue

        if category == "location_history":
            key = (category, "", "")
            if key in seen:
                # Prefer the raw receipt carrying bounded event details. If the
                # first line came from the wrapper, replace it when details arrive.
                hints = _location_event_hints(receipt)
                if hints:
                    for idx, line in enumerate(lines):
                        if line.startswith("- CHECKED location/mode history:"):
                            count = (receipt.get("details") or {}).get("count")
                            prefix = (
                                f"- CHECKED location/mode history: {count} events"
                                if count is not None
                                else "- CHECKED location/mode history"
                            )
                            lines[idx] = f"{prefix}; examples: {hints}"
                            break
                continue
            seen.add(key)
            details = receipt.get("details")
            details = details if isinstance(details, dict) else {}
            count = details.get("count")
            summary = (
                f"{count} events" if count is not None
                else str(receipt.get("summary") or "successful read")
            )
            hints = _location_event_hints(receipt)
            if hints:
                summary += f"; examples: {hints}"
            lines.append(f"- CHECKED location/mode history: {summary}")
            continue

        if category == "logs":
            args = _inner_args(receipt)
            scope = str(
                args.get("deviceId")
                or args.get("appId")
                or args.get("source")
                or "requested scope"
            )
            key = (category, scope, "")
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- CHECKED native/log evidence ({scope}): "
                f"{receipt.get('summary') or 'successful read'}"
            )
            continue

        if category == "rules_apps":
            key = (category, str(receipt.get("sub_tool") or receipt.get("tool")), "")
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- CHECKED rule/app evidence via "
                f"{receipt.get('sub_tool') or receipt.get('tool')}: "
                f"{receipt.get('summary') or 'successful read'}"
            )
            continue

        if category == "device_filter":
            args = _inner_args(receipt)
            field = str(args.get("attribute") or "devices")
            value = str(args.get("value") or args.get("comparison_value") or "")
            key = (category, field, value)
            if key in seen:
                continue
            seen.add(key)
            suffix = f" {field}={value}" if value else f" {field}"
            lines.append(
                f"- CHECKED device discovery/filter:{suffix}: "
                f"{receipt.get('summary') or 'successful read'}"
            )
            continue

        if category == "live_context":
            key = (category, "", "")
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- CHECKED live device context: "
                f"{receipt.get('summary') or 'successful read'}"
            )

        if len(lines) >= _MAX_LEDGER_LINES:
            break

    return lines[:_MAX_LEDGER_LINES]


def build_current_turn_evidence_ledger(
    receipts: list[dict[str, Any]],
) -> str | None:
    """Render a compact final-synthesis ledger when multiple evidence classes exist."""

    categories = checked_source_categories(receipts)
    material = categories & {
        "device_history",
        "related_device_history",
        "location_history",
        "logs",
        "rules_apps",
        "device_filter",
        "live_context",
    }
    # A single ordinary device-history answer already has a strong direct
    # synthesis path. Avoid adding prompt overhead unless the request gathered
    # multiple evidence classes or related-device histories.
    if len(material) < 2 and "related_device_history" not in material:
        return None

    lines = _ledger_lines(receipts)
    if not lines:
        return None
    return (
        "HOST CURRENT-TURN EVIDENCE LEDGER\n"
        "The following sources were successfully checked in THIS request. "
        "CHECKED means the data was provided to you; it does not mean the source "
        "proved causation. Never say a CHECKED source was not provided, unavailable, "
        "or not checked. Distinguish: (1) what the subject history recorded, "
        "(2) direct provenance/log or rule/app evidence when present, "
        "(3) mode/location correlation, (4) related-device/sensor correlation, "
        "and (5) what remains unproven. Prefer direct provenance over temporal "
        "correlation and do not turn correlation into causation.\n"
        + "\n".join(lines)
    )


__all__ = [
    "build_current_turn_evidence_ledger",
    "checked_source_categories",
]

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
from datetime import datetime
from typing import Any

from location_correlation import nearest_location_correlations, render_location_correlation
from natural_datetime import normalize_iso_offset


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


def _parsed_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None


def _boundary_event_hints(details: dict[str, Any], temporal: dict[str, Any]) -> list[str]:
    """Return concrete subject events close to observed interval boundaries."""

    intervals = temporal.get("observedIntervals")
    events = details.get("boundaryEvents")
    if not isinstance(events, list):
        events = details.get("observedEvents")
    if not isinstance(intervals, list) or not isinstance(events, list):
        return []

    boundaries: list[datetime] = []
    for interval in intervals:
        if not isinstance(interval, dict):
            continue
        for key in ("start", "end"):
            parsed = _parsed_time(interval.get(key))
            if parsed is not None:
                boundaries.append(parsed)
    if not boundaries:
        return []

    hints: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        event_time = _parsed_time(event.get("date"))
        if event_time is None:
            continue
        nearest = min(abs((event_time - boundary).total_seconds()) for boundary in boundaries)
        if nearest > 8.0:
            continue
        name = str(event.get("name") or "").strip()
        value = str(event.get("value") or "").strip()
        description = str(event.get("description") or "").strip()
        key = (event_time.isoformat(), name, value)
        if key in seen:
            continue
        seen.add(key)
        rendered = f"{event.get('date')}: " + (
            "=".join(part for part in (name, value) if part) or "event"
        )
        if description and description.casefold() not in rendered.casefold():
            rendered += f" [{description}]"
        rendered += f" (boundary delta {nearest:.3f}s)"
        hints.append(rendered)
        if len(hints) >= 10:
            break
    return hints


def _temporal_suffix(receipt: dict[str, Any]) -> str:
    """Render bounded state intervals or event-style provenance rows."""

    details = receipt.get("details")
    if not isinstance(details, dict):
        return ""

    bits: list[str] = []
    temporal = details.get("temporalAnalysis")
    if isinstance(temporal, dict):
        count = temporal.get("intervalCount")
        duration = temporal.get("totalActiveDuration")
        if count is not None:
            bits.append(f"{count} interval{'s' if count != 1 else ''}")
        if duration:
            bits.append(f"total {duration}")
        reliability = str(temporal.get("durationReliability") or "").strip()
        if reliability:
            bits.append(f"reliability={reliability}")
        intervals = temporal.get("observedIntervals")
        if isinstance(intervals, list) and intervals:
            rendered: list[str] = []
            for item in intervals[:8]:
                if not isinstance(item, dict):
                    continue
                start = str(item.get("startNatural") or item.get("start") or "?")
                end = str(item.get("endNatural") or item.get("end") or "?")
                duration_text = str(item.get("duration") or "").strip()
                span = f"{start} -> {end}"
                if duration_text:
                    span += f" ({duration_text})"
                rendered.append(span)
            if rendered:
                suffix = " + more" if temporal.get("observedIntervalsTruncated") else ""
                bits.append("observed=[" + "; ".join(rendered) + "]" + suffix)
        boundary_events = _boundary_event_hints(details, temporal)
        if boundary_events:
            bits.append("boundaryEvents=[" + "; ".join(boundary_events) + "]")

        if temporal.get("unboundedActiveInterval"):
            open_start = str(
                temporal.get("openActiveStartNatural")
                or temporal.get("openActiveStart")
                or "unknown start"
            ).strip()
            state = str(temporal.get("activeState") or "active").strip() or "active"
            qualifier = (
                "ongoing-window open interval"
                if temporal.get("openActiveInterval")
                else "unbounded interval at window end"
            )
            bits.append(
                f"{qualifier}: recorded {state} transition at {open_start} has no "
                "observed closing transition; do not infer its duration"
            )

        # When no bounded active interval exists, boundary evidence is naturally
        # empty. Preserve the actual rows that fell inside the requested window so
        # synthesis can still distinguish commands from state transitions without
        # reaching back into conversation history or an unbounded latest-N list.
        if not (isinstance(intervals, list) and intervals):
            window_events = details.get("windowEvents")
            if isinstance(window_events, list) and window_events:
                rendered_window: list[str] = []
                for item in window_events[:10]:
                    if not isinstance(item, dict):
                        continue
                    date = str(item.get("date") or "?").strip()
                    name = str(item.get("name") or "").strip()
                    value = str(item.get("value") or "").strip()
                    description = str(item.get("description") or "").strip()
                    event = "=".join(
                        part for part in (name, value) if part
                    ) or "event"
                    if description and description.casefold() not in event.casefold():
                        event += f" [{description}]"
                    rendered_window.append(f"{date}: {event}")
                if rendered_window:
                    suffix = (
                        " + more"
                        if details.get("windowEventsTruncated")
                        else ""
                    )
                    bits.append(
                        "windowEvents=["
                        + "; ".join(rendered_window)
                        + "]"
                        + suffix
                    )

    # Event-style histories such as pushed/held/released do not have binary
    # temporalAnalysis. Keep their concrete timestamp/value/description rows in
    # the final synthesis brief instead of reducing them to "object fields".
    if not isinstance(temporal, dict):
        events = details.get("observedEvents")
        if isinstance(events, list) and events:
            rendered_events: list[str] = []
            for item in events[:8]:
                if not isinstance(item, dict):
                    continue
                date = str(item.get("date") or "?").strip()
                name = str(item.get("name") or "").strip()
                value = str(item.get("value") or "").strip()
                description = str(item.get("description") or "").strip()
                event = "=".join(part for part in (name, value) if part) or "event"
                if description and description.casefold() not in event.casefold():
                    event += f" [{description}]"
                rendered_events.append(f"{date}: {event}")
            if rendered_events:
                suffix = " + more" if details.get("observedEventsTruncated") else ""
                bits.append("events=[" + "; ".join(rendered_events) + "]" + suffix)
    return "; ".join(bits)

def _location_event_hints(
    receipt: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> str:
    details = receipt.get("details")
    if not isinstance(details, dict):
        return ""
    rows = details.get("events")
    if not isinstance(rows, list):
        return ""
    hints: list[str] = []

    # Final synthesis cares more about location events temporally adjacent to the
    # subject's observed transitions than simply the newest location events.
    # Preserve those correlations first, then fill any remaining hint slots in
    # the upstream newest-first order.
    correlations = nearest_location_correlations(
        evidence,
        max_delta_seconds=15.0,
        limit=_MAX_EVENT_HINTS,
    )
    correlated_dates = {
        str(item.get("eventDate") or "").strip()
        for item in correlations
        if str(item.get("eventDate") or "").strip()
    }
    for item in correlations:
        hints.append("NEAR SUBJECT TRANSITION: " + render_location_correlation(item))

    for row in rows:
        if len(hints) >= _MAX_EVENT_HINTS:
            break
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        value = str(row.get("value") or "").strip()
        date = str(row.get("date") or "").strip()
        if date and date in correlated_dates:
            continue
        if not (name or value):
            continue
        label = "=".join(part for part in (name, value) if part)
        if date:
            label += f" @ {date}"
        hints.append(label)
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
            summary = suffix or str(receipt.get("summary") or "successful history read")
            subject = label or "named device"
            if attribute:
                subject += f" ({attribute})"
            lines.append(f"- CHECKED device history: {subject}: {summary}")
            continue

        if category == "location_history":
            key = (category, "", "")
            if key in seen:
                # Prefer the raw receipt carrying bounded event details. If the
                # first line came from the wrapper, replace it when details arrive.
                hints = _location_event_hints(receipt, receipts)
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
            hints = _location_event_hints(receipt, receipts)
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
            details = receipt.get("details")
            log_hints: list[str] = []
            if isinstance(details, dict) and isinstance(details.get("logs"), list):
                for row in details.get("logs")[:4]:
                    if not isinstance(row, dict):
                        continue
                    date = str(row.get("date") or "?").strip()
                    source = str(row.get("source") or "").strip()
                    message = str(row.get("message") or "").strip()
                    rendered = " | ".join(
                        part for part in (date, source, message) if part
                    )
                    if rendered:
                        log_hints.append(rendered)
            summary = str(receipt.get("summary") or "successful read")
            if log_hints:
                summary += "; nearby rows=[" + "; ".join(log_hints) + "]"
            lines.append(
                f"- CHECKED native/log evidence ({scope}): {summary}"
            )
            continue

        if category == "rules_apps":
            key = (category, str(receipt.get("sub_tool") or receipt.get("tool")), "")
            if key in seen:
                continue
            seen.add(key)
            source_name = str(receipt.get("sub_tool") or receipt.get("tool") or "")
            qualifier = (
                " [CONFIGURATION/NAVIGATION ONLY — not execution proof]"
                if source_name in {"hub_get_app_config", "hub_list_apps"}
                else ""
            )
            lines.append(
                f"- CHECKED rule/app evidence via {source_name}: "
                f"{receipt.get('summary') or 'successful read'}{qualifier}"
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


def _single_history_window_audit_needed(
    receipts: list[dict[str, Any]],
) -> bool:
    """Whether one history source still needs a compact audit ledger.

    A zero-interval semantic window can still contain command/custom rows. Those
    facts are easy to lose behind the normal newest-first tool excerpt, so retain
    a compact ledger even though only one evidence class was checked.
    """

    histories = [
        receipt
        for receipt in receipts
        if isinstance(receipt, dict)
        and receipt.get("success") is True
        and receipt.get("tool") == "homebrain_device_history"
        and isinstance(receipt.get("details"), dict)
    ]
    if len(histories) != 1:
        return False
    details = histories[0]["details"]
    temporal = details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return False
    try:
        interval_count = int(temporal.get("intervalCount"))
    except (TypeError, ValueError):
        return False
    # An unbounded active transition is itself an auditable temporal fact:
    # a recorded active row exists but no observed closing row does. Preserve a
    # single-source ledger for it even if the compact windowEvents channel is
    # absent, because the open-start metadata is carried in temporalAnalysis.
    if temporal.get("unboundedActiveInterval"):
        return True

    window_events = details.get("windowEvents")
    return (
        interval_count == 0
        and isinstance(window_events, list)
        and any(isinstance(item, dict) for item in window_events)
    )


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
    # multiple evidence classes/related histories, or the sole history source
    # established zero intervals but retained in-window rows that still need an
    # auditable compact proof for final synthesis.
    single_window_audit = _single_history_window_audit_needed(receipts)
    if (
        len(material) < 2
        and "related_device_history" not in material
        and not single_window_audit
    ):
        return None

    lines = _ledger_lines(receipts)
    if not lines:
        return None
    return (
        "HOST CURRENT-TURN EVIDENCE LEDGER\n"
        "HOST CURRENT-TURN EVIDENCE BRIEF\n"
        "The following sources were successfully checked in THIS request. "
        "CHECKED means the data was provided to you; it does not mean the source "
        "proved causation. Never say a CHECKED source was unavailable or not checked. "
        "Use this brief as the factual spine of the answer rather than letting one "
        "source (for example a duration calculation) displace the user's actual "
        "question. For a why/cause investigation: lead with the best-supported "
        "explanation and its confidence; reconstruct a chronological timeline by "
        "correlating timestamps across sources; distinguish direct provenance from "
        "automation effects and from weaker temporal correlation; identify any "
        "remaining unexplained transitions; and state uncertainty where evidence "
        "coverage is incomplete. Do not infer a person's identity or a physical "
        "press unless event metadata supports that wording. Prefer direct provenance "
        "over temporal correlation and never turn correlation into causation.\n"
        + "\n".join(lines)
    )


__all__ = [
    "build_current_turn_evidence_ledger",
    "checked_source_categories",
]

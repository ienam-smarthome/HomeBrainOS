"""Deterministic enrichment for model-driven device-history reads.

The model is allowed to omit a state attribute when asking for a named device's
history.  Semantic history questions still need deterministic interval evidence,
so this module repairs only what can be established from the returned event rows:

* widen an attribute-less semantic history read to the local 50-row ceiling;
* infer a state-pair attribute only when exactly one supported binary attribute is
  present in the returned rows; and
* never synthesize a predecessor from a later event: page completeness is not
  evidence that the device event stream contains every physical transition.

No user-question grammar lives here and no causal conclusion is inferred.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from typing import Any

from history_temporal_analysis import (
    analyze_state_intervals,
    analyze_state_intervals_in_window,
    boundary_event_evidence,
    window_event_evidence,
)
from history_time_windows import active_history_window_request
from mcp_client import MCPToolResult
from natural_datetime import normalize_iso_offset


DEVICE_HISTORY_TOOL = "homebrain_device_history"
_STATE_PAIRS: dict[str, tuple[str, str]] = {
    "switch": ("on", "off"),
    "contact": ("open", "closed"),
    "motion": ("active", "inactive"),
    "lock": ("unlocked", "locked"),
    "valve": ("open", "closed"),
}


def prepare_history_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Use the full bounded page for semantic history when no attribute was given."""

    prepared = deepcopy(arguments)
    if name != DEVICE_HISTORY_TOOL or prepared.get("attribute"):
        return prepared
    if active_history_window_request() is None:
        return prepared
    try:
        current_limit = int(prepared.get("limit") or 0)
    except (TypeError, ValueError):
        current_limit = 0
    prepared["limit"] = max(50, current_limit)
    return prepared


def _event_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None


def _events(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in data.get("events") or [] if isinstance(item, dict)]


def _binary_attribute(events: list[dict[str, Any]]) -> str | None:
    candidates: set[str] = set()
    for event in events:
        name = str(event.get("name") or event.get("attribute") or "").casefold()
        pair = _STATE_PAIRS.get(name)
        value = str(event.get("value") or "").casefold()
        if pair is not None and value in pair:
            candidates.add(name)
    return next(iter(candidates)) if len(candidates) == 1 else None


def _filtered(events: list[dict[str, Any]], attribute: str) -> list[dict[str, Any]]:
    key = attribute.casefold()
    return [
        event
        for event in events
        if str(event.get("name") or event.get("attribute") or "").casefold() == key
    ]


def _window_datetimes(window: dict[str, Any]) -> tuple[datetime, datetime] | None:
    start = _event_datetime(window.get("start"))
    end = _event_datetime(window.get("end"))
    if start is None or end is None or end <= start:
        return None
    return start, end


def _analysis_for(
    attribute: str,
    events: list[dict[str, Any]],
    data: dict[str, Any],
) -> dict[str, Any] | None:
    window = data.get("timeWindow")
    if not isinstance(window, dict):
        return analyze_state_intervals(attribute, events)
    bounds = _window_datetimes(window)
    if bounds is None:
        return None
    start, end = bounds
    return analyze_state_intervals_in_window(
        attribute,
        events,
        start=start,
        end=end,
        window_label=str(window.get("label") or "requested window"),
        source_complete_to_start=bool(window.get("sourceCompleteToStart")),
        window_ongoing=bool(window.get("ongoing")),
        source_integrity_verified=bool(data.get("historySourceIntegrityVerified")),
    )


def inferred_state_retry_arguments(
    name: str,
    original_arguments: dict[str, Any],
    result: MCPToolResult,
) -> dict[str, Any] | None:
    """Return one deterministic scoped-history retry for a causal subject.

    Attribute-less semantic history can infer a binary state only after reading
    a mixed event page. On high-churn devices that page can contain a recent
    switch=off row while the older switch=on boundary has already been crowded
    out by metering/RTT telemetry. If the page is full, the inferred attribute is
    binary, and no bounded interval was established, retry the same canonical
    device once with that exact attribute and the local 50-row ceiling.

    The caller decides whether the request is causal. This helper is structural
    only and never infers intent from prompt wording.
    """

    if name != DEVICE_HISTORY_TOOL or result.is_error:
        return None
    if str(original_arguments.get("attribute") or "").strip():
        return None
    data = result.data
    if not isinstance(data, dict) or data.get("attributeInferred") is not True:
        return None
    attribute = str(data.get("attribute") or "").strip().casefold()
    if attribute not in _STATE_PAIRS:
        return None
    temporal = data.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return None
    try:
        interval_count = int(temporal.get("intervalCount") or 0)
    except (TypeError, ValueError):
        interval_count = 0
    if interval_count > 0:
        return None

    try:
        requested_limit = int(original_arguments.get("limit") or 20)
    except (TypeError, ValueError):
        requested_limit = 20
    requested_limit = max(1, min(50, requested_limit))
    try:
        source_count = int(data.get("sourceEventCount") or 0)
    except (TypeError, ValueError):
        source_count = 0
    if source_count < requested_limit:
        return None

    canonical_name = str(
        data.get("label")
        or data.get("requested")
        or original_arguments.get("name")
        or ""
    ).strip()
    if not canonical_name:
        return None

    retry = deepcopy(original_arguments)
    retry["name"] = canonical_name
    retry["attribute"] = attribute
    retry["limit"] = 50
    if "hours_back" not in retry and data.get("hoursBack") is not None:
        try:
            retry["hours_back"] = int(data.get("hoursBack"))
        except (TypeError, ValueError):
            pass
    return retry


def enrich_history_result(name: str, result: MCPToolResult) -> MCPToolResult:
    """Return a history result with every deterministic derivation available."""

    if name != DEVICE_HISTORY_TOOL or result.is_error or not isinstance(result.data, dict):
        return result
    data = deepcopy(result.data)
    events = _events(data)
    attribute = str(data.get("attribute") or "").strip().casefold()

    if not attribute:
        inferred = _binary_attribute(events)
        if inferred is not None:
            attribute = inferred
            filtered = _filtered(events, attribute)
            data["attribute"] = attribute
            data["attributeInferred"] = True
            data["analysisEventCount"] = len(filtered)
            temporal = _analysis_for(attribute, filtered, data)
            if temporal is not None:
                data["temporalAnalysis"] = temporal

    # Preserve every bounded source row that actually falls inside the requested
    # temporal window independently of interval construction. This remains useful
    # when an unverified stream yields zero bounded intervals but still contains
    # command/state rows the final answer may reference.
    time_window = data.get("timeWindow")
    existing_window_rows = data.get("windowEvents")
    if (
        isinstance(time_window, dict)
        and not isinstance(existing_window_rows, list)
    ):
        window_rows = window_event_evidence(events, time_window)
        if window_rows:
            data["windowEvents"] = window_rows

    # Boundary evidence must be derived after every deterministic history
    # enrichment step. Attribute-less semantic history is common; in that path
    # DeviceHistoryService cannot know the interval boundaries yet because the
    # binary state attribute is inferred here. Selecting boundary rows only in
    # the service therefore silently misses exactly the histories that rely on
    # post-fetch inference.
    temporal = data.get("temporalAnalysis")
    if isinstance(temporal, dict):
        boundary_rows = boundary_event_evidence(events, temporal)
        if boundary_rows:
            data["boundaryEvents"] = boundary_rows

    if data == result.data:
        return result
    return MCPToolResult(
        name=result.name,
        arguments=result.arguments,
        raw=result.raw,
        text=json.dumps(data, ensure_ascii=False, default=str),
        data=data,
        is_error=result.is_error,
    )


__all__ = [
    "DEVICE_HISTORY_TOOL",
    "enrich_history_result",
    "inferred_state_retry_arguments",
    "prepare_history_arguments",
]

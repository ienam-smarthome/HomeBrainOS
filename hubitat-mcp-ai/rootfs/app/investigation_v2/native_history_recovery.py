"""Normalize *model-chosen* READ history scopes against the user incident.

A missing deviceId can be filled only from the unique host-verified subject.
An explicit calendar date can constrain an event READ with timezone-padded UTC
bounds; padding is NOT a claim that the hub uses UTC. No writes, no new tool
selection, no promotion of inferred device IDs, and no source completeness
claim. All normalized args still pass the normal manifest/effect/schema gates.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping
import re

from .temporal_scope import explicit_incident_window

_EXPLICIT_DAY = re.compile(
    r"\b(?:\d{1,2}\s+(?:january|february|march|april|may|june|july|"
    r"august|september|october|november|december)\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2})\b", re.I
)


def requested_history_bounds(question: str) -> dict[str, Any] | None:
    """Conservatively cover all global timezones, pending hub timezone proof."""
    if not _EXPLICIT_DAY.search(question):
        return None
    # UTC is a reference *calculation*, not an assumption about local hub
    # time. Add one full day either side so all IANA offsets are covered.
    window = explicit_incident_window(question, zone_name="UTC")
    if window is None:
        return None
    start = datetime.fromisoformat(window.start_utc) - timedelta(days=1)
    end = datetime.fromisoformat(window.end_utc) + timedelta(days=1)
    return {
        "since": start.isoformat(),
        "until": end.isoformat(),
        "source": "explicit_user_calendar_date",
        "hub_timezone_verified": False,
        "window_is_padded": True,
    }


def normalize_selected_history_read(
    gateway: str, arguments: Mapping[str, Any], *,
    focus_ids: set[str], verified_device_ids: set[str],
    question: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Repair only an already model-selected, uniquely scoped event READ.

    Keep the original gateway, operation, and any explicit time window. An
    unscoped hub/location mode or an app-scoped read must never be silently
    changed into device history. Caller still validates effect and contracts.
    """
    original = dict(arguments)
    if not (gateway.startswith("hub_read_")
            and original.get("tool") == "hub_list_device_events"
            and isinstance(original.get("args"), Mapping)):
        return original, None
    inner = dict(original["args"])
    if inner.get("mode") is not None or inner.get("appId") is not None:
        return original, None
    patch: dict[str, Any] = {}
    if (inner.get("deviceId") is None and len(focus_ids) == 1
            and focus_ids <= verified_device_ids):
        inner["deviceId"] = next(iter(focus_ids))
        patch["verified_device_id_inserted"] = True
    if (str(inner.get("deviceId")) not in verified_device_ids
            or str(inner.get("deviceId")) not in focus_ids):
        return original, None
    # An explicit absolute interval chosen by the model has priority.
    # A relative hoursBack is not an absolute interval and might exclude
    # the user's dated incident, even if it successfully returns many rows.
    # Preserve hoursBack if it covers the *padded* requested window.
    if (inner.get("since") is None and inner.get("until") is None
            and inner.get("cursor") is None):
        bound = requested_history_bounds(question)
        if bound is not None:
            hours = inner.get("hoursBack")
            covers = False
            if type(hours) in (int, float) and 0 < hours <= 168:
                requested_start = datetime.fromisoformat(bound["since"])
                lookback_start = datetime.now(requested_start.tzinfo) - timedelta(hours=hours)
                covers = lookback_start <= requested_start
            if not covers:
                inner.pop("hoursBack", None)
                inner["since"] = bound["since"]
                inner["until"] = bound["until"]
                # A small default page is not enough for a multi-day
                # padded incident range.
                old_limit = inner.get("limit")
                if old_limit is None or (type(old_limit) is int
                                         and 1 <= old_limit < 100):
                    inner["limit"] = 100
                patch["historical_window"] = bound
                if hours is not None:
                    patch["noncovering_relative_window_replaced"] = True
    if not patch:
        return original, None
    original["args"] = inner
    return original, {
        "model_selected_operation": "hub_list_device_events",
        "source": "host_verified_scope_normalization",
        "read_only": True,
        "device_id": str(inner["deviceId"]),
        **patch,
    }


__all__ = ["requested_history_bounds", "normalize_selected_history_read"]

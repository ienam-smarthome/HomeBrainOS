"""Request-local duplicate read-source admission for read-only investigations.

One physical Hubitat source page can reach the model twice: once through the
native location-history gateway and again via the deterministic local wrapper.
Suppress ONLY the latter when the native read was already successful for the
same or wider bounded time window and page size. Other source classes are
untouched. This module cannot establish absence of historical events or cause.
"""
from __future__ import annotations

from typing import Any, Mapping


def _leaf(row: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    raw = row.get("arguments")
    if not isinstance(raw, dict):
        return "", {}
    args = raw.get("args")
    leaf = raw.get("tool") or row.get("sub_tool") or ""
    return str(leaf), args if isinstance(args, dict) else raw


def _safe_window(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        v = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return v if 1 <= v <= 720 else None


def _safe_limit(value: Any, *, default: int) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return None
    try:
        v = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return v if 1 <= v <= 1000 else None


def duplicate_location_projection_reason(
    request: str,
    receipts: list[dict[str, Any]],
    name: str,
    arguments: dict[str, Any],
) -> str | None:
    """Skip a second projection of the *same* already read location page.

    This is intentionally one-way: a native location event page is the raw
    source, and the subsequent local projection of an equal/smaller unfiltered
    page cannot add another event class. Never block the first read, an exact
    scoped device history, longer/deeper pages, or a filtered projection.
    The request must actually be a read-only investigation; caller enforces it.
    """
    if name != "homebrain_location_events":
        return None
    if any(
        key not in ("hours_back", "hoursBack", "limit")
        and value not in (None, "", [], {})
        for key, value in arguments.items()
    ):
        return None
    target_window = _safe_window(arguments.get("hours_back", arguments.get("hoursBack")))
    target_limit = _safe_limit(arguments.get("limit"), default=20)
    if target_window is None or target_limit is None:
        return None
    for row in receipts:
        if not isinstance(row, dict):
            continue
        if (
            row.get("success") is not True
            or row.get("mutates") is True
            or row.get("effect") not in (None, "read")
            or row.get("tool") != "hub_read_devices"
        ):
            continue
        leaf, args = _leaf(row)
        if leaf != "hub_list_device_events":
            continue
        # An unscoped native location-event read has neither deviceId nor
        # attribute. A scoped device/mode/filtered query is never a duplicate.
        if any(args.get(k) not in (None, "", [], {}) for k in (
            "deviceId", "deviceIds", "attribute", "filter",
            "cursor", "start", "end", "since", "until",
        )):
            continue
        native_window = _safe_window(args.get("hoursBack", args.get("hours_back")))
        native_limit = _safe_limit(args.get("limit"), default=20)
        if (native_window is not None and native_limit is not None
                and native_window >= target_window
                and native_limit >= target_limit):
            return "native-location-page-already-read"
    return None


__all__ = ["duplicate_location_projection_reason"]

from __future__ import annotations

import re
from typing import Any, Iterable

from fallback_router import _device_id, _label, _normalise
from fast_fallback_extended_reads import FastFallbackRouter as ExtendedReadsRouter, _rows
from fast_fallback_live import live_attributes
from fast_fallback_speech import normalise_spoken_device_name
from mcp_client import MCPToolResult
from presenter import display_payload, first_value, normalise_text, safe_debug


_PRAYERS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Fajr", ("fajr", "fajar"), "🌙"),
    ("Sunrise", ("sunrise", "shuruq", "ishraq"), "🌅"),
    ("Dhuhr", ("dhuhr", "dhur", "zuhr", "zohar"), "☀️"),
    ("Asr", ("asr",), "☁️"),
    ("Maghrib", ("maghrib", "magrib"), "🌆"),
    ("Isha", ("isha", "ishaa"), "🌌"),
)

_ALIAS_TO_NAME = {
    alias: name
    for name, aliases, _icon in _PRAYERS
    for alias in aliases
}
_ICON_BY_NAME = {name: icon for name, _aliases, icon in _PRAYERS}
_ORDER = [name for name, _aliases, _icon in _PRAYERS]

_SINGLE_PRAYER_RE = re.compile(
    r"^(?:what\s+time\s+(?:is|does)|when\s+(?:is|does)|tell\s+me\s+(?:the\s+)?)\s*"
    r"(fajr|fajar|sunrise|shuruq|ishraq|dhuhr|dhur|zuhr|zohar|asr|maghrib|magrib|isha|ishaa)"
    r"(?:\s+(?:start|begin|starts|begins))?(?:\s+(?:today|tonight))?[?.!]*$",
    re.IGNORECASE,
)

_SINGLE_PRAYER_TIME_RE = re.compile(
    r"^(fajr|fajar|sunrise|shuruq|ishraq|dhuhr|dhur|zuhr|zohar|asr|maghrib|magrib|isha|ishaa)"
    r"(?:\s+(?:prayer))?\s+time(?:\s+(?:today|tonight))?[?.!]*$",
    re.IGNORECASE,
)

_ALL_PRAYER_RE = re.compile(
    r"^(?:show|list|display|give\s+me|what\s+are|what(?:'s|\s+is))\s+"
    r"(?:today(?:'s)?\s+)?(?:pray|prayer)\s+times(?:\s+today)?[?.!]*$",
    re.IGNORECASE,
)

_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _canonical_prayer(value: str) -> str | None:
    return _ALIAS_TO_NAME.get(_normalise(value))


def _time_text(value: Any) -> str | None:
    match = _TIME_RE.search(normalise_text(value))
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def extract_prayer_times(value: Any) -> dict[str, str]:
    """Extract the standard daily prayer times from attributes, HTML or events."""
    found: dict[str, str] = {}

    for item in _walk(value):
        if not isinstance(item, dict):
            continue
        for key, raw in item.items():
            canonical = _canonical_prayer(str(key))
            if canonical and canonical not in found:
                parsed = _time_text(raw)
                if parsed:
                    found[canonical] = parsed

    chunks: list[str] = []
    for item in _walk(value):
        if isinstance(item, str) and item.strip():
            chunks.append(normalise_text(item))
    text = " ".join(chunks)

    for name, aliases, _icon in _PRAYERS:
        if name in found:
            continue
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        match = re.search(
            rf"\b(?:{alias_pattern})\b[^0-9]{{0,30}}([01]?\d|2[0-3]):([0-5]\d)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            found[name] = f"{int(match.group(1)):02d}:{match.group(2)}"

    return {name: found[name] for name in _ORDER if name in found}


class FastFallbackRouter(ExtendedReadsRouter):
    """Fast prayer-time answers sourced from the selected Pray times device."""

    async def answer(self, query: str) -> dict[str, Any]:
        if "event" not in _normalise(query):
            requested = self._requested_prayer(query)
            if requested is not False:
                return await self._prayer_times(requested)
        return await super().answer(query)

    @staticmethod
    def _requested_prayer(query: str) -> str | None | bool:
        text = str(query or "").strip()
        match = _SINGLE_PRAYER_RE.match(text) or _SINGLE_PRAYER_TIME_RE.match(text)
        if match:
            return _canonical_prayer(match.group(1))
        if _ALL_PRAYER_RE.match(text):
            return None
        return False

    async def _find_prayer_device(
        self,
    ) -> tuple[MCPToolResult, dict[str, Any] | None, list[str]]:
        live = await self._live_devices()
        candidates = self._device_rows(live.data)
        match, alternatives = self._match_device("Pray times", candidates)
        return live, match, alternatives

    async def _prayer_times(self, requested: str | None) -> dict[str, Any]:
        live, match, alternatives = await self._find_prayer_device()
        if not match:
            message = "I could not find one selected MCP device named Pray times."
            if alternatives:
                message += " Closest matches: " + ", ".join(alternatives[:5]) + "."
            response = self._response(message, "fallback-prayer-times-device-not-found", False, live)
            response["alternatives"] = alternatives[:5]
            return response

        attributes = live_attributes(match)
        times = extract_prayer_times(attributes)
        source_result: MCPToolResult = live
        source = "currentStates"
        updated = first_value(match, "lastActivity", "lastUpdated", "date", "timestamp")

        if requested not in times if requested else len(times) < 4:
            events = await self._read_tool(
                "hub_list_device_events",
                {"deviceId": _device_id(match), "hoursBack": 48},
            )
            event_rows = _rows(events.data, ("events", "items"))
            event_times = extract_prayer_times(event_rows)
            if len(event_times) > len(times) or (requested and requested in event_times):
                times = event_times
                source_result = events
                source = "recent device event"
                if event_rows:
                    updated = first_value(
                        event_rows[0],
                        "date",
                        "timestamp",
                        "time",
                        "createdAt",
                    )

        return self._prayer_response(
            result=source_result,
            times=times,
            requested=requested,
            source=source,
            updated=updated,
            matched_device=match,
        )

    def _prayer_response(
        self,
        *,
        result: MCPToolResult,
        times: dict[str, str],
        requested: str | None,
        source: str,
        updated: Any = None,
        matched_device: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        label = _label(matched_device or {}) or "Pray times"
        if not times:
            response = self._response(
                f"{label} did not return recognisable Fajr, Sunrise, Dhuhr, Asr, Maghrib or Isha times.",
                "fallback-prayer-times-unavailable",
                False,
                result,
            )
            response["technical"] = safe_debug(
                {
                    "source": source,
                    "updated": updated,
                    "device": matched_device,
                    "raw": result.data,
                }
            )
            return response

        if requested:
            selected = times.get(requested)
            if selected:
                message = f"{requested} is at {selected} today."
                shown = {requested: selected}
                subtitle = f"Today's {requested} time"
            else:
                message = f"I found prayer-time data, but {requested} was not included in it."
                shown = times
                subtitle = "Available prayer times"
        else:
            message = "Today's prayer times: " + ", ".join(
                f"{name} {time}" for name, time in times.items()
            ) + "."
            shown = times
            subtitle = "Today's times from the Pray times device"

        items = [
            {
                "icon": _ICON_BY_NAME.get(name, "🕌"),
                "title": name,
                "value": time,
                "subtitle": "Today",
            }
            for name, time in shown.items()
        ]
        display = display_payload(
            "prayer-times",
            requested or "Prayer times",
            subtitle=subtitle,
            metrics=[
                {
                    "label": name,
                    "value": time,
                    "icon": _ICON_BY_NAME.get(name, "🕌"),
                }
                for name, time in shown.items()
            ],
            items=items,
            note=(
                f"Read from {label} {source}."
                + (f" Updated {normalise_text(updated)}." if updated not in (None, "") else "")
            ),
        )
        response = self._response(message, "fallback-prayer-times", True, result)
        response["display"] = display
        response["prayer_times"] = times
        response["requested_prayer"] = requested
        response["technical"] = safe_debug(
            {
                "source": source,
                "updated": updated,
                "device_id": _device_id(matched_device or {}),
                "device_label": label,
                "prayer_times": times,
            }
        )
        return response

    async def _device_events(self, requested_name: str) -> dict[str, Any]:
        if normalise_spoken_device_name(requested_name) != normalise_spoken_device_name("Pray times"):
            return await super()._device_events(requested_name)

        live, match, alternatives = await self._find_prayer_device()
        if not match:
            return await super()._device_events(requested_name)

        events = await self._read_tool(
            "hub_list_device_events",
            {"deviceId": _device_id(match), "hoursBack": 24},
        )
        rows = _rows(events.data, ("events", "items"))
        times = extract_prayer_times(rows)
        updated = (
            first_value(rows[0], "date", "timestamp", "time", "createdAt")
            if rows
            else None
        )
        if times:
            return self._prayer_response(
                result=events,
                times=times,
                requested=None,
                source="most recent event",
                updated=updated,
                matched_device=match,
            )
        return await super()._device_events(requested_name)


__all__ = ["FastFallbackRouter", "extract_prayer_times"]

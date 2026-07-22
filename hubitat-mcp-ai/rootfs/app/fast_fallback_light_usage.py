from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_live import _looks_like_light, live_attributes
from fast_fallback_multi_control import FastFallbackRouter as MultiControlRouter
from light_usage_calculation import calculate_on_time, duration_text, switch_events
from presenter import display_payload, safe_debug


_PATTERNS = (
    r"^(?:show )?(?:the )?(?:total |combined )?lights? on time(?:(?: for)? today)?$",
    r"^how (?:long|much time) (?:have )?(?:all )?(?:the )?lights? (?:been )?on today$",
    r"^(?:show|calculate|get|give me) (?:the )?(?:total |combined )?(?:daily )?lights? (?:on time|usage) (?:for )?today$",
    r"^(?:which|what) lights? (?:were|have been) on (?:the )?longest today$",
)


def is_light_usage_today_query(query: str) -> bool:
    text = _normalise(query).strip(" .!?")
    return any(re.match(pattern, text, re.IGNORECASE) for pattern in _PATTERNS)


class FastFallbackRouter(MultiControlRouter):
    """Calculate today's combined light usage from Hubitat switch events."""

    async def answer(self, query: str) -> dict[str, Any]:
        if is_light_usage_today_query(query):
            return await self._light_usage_today()
        return await super().answer(query)

    async def _light_usage_today(self) -> dict[str, Any]:
        now = datetime.now().astimezone()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        live = await self._live_devices("Switch")
        lights = [
            item for item in self._device_rows(live.data)
            if _looks_like_light(item) and _device_id(item)
        ]
        lights.sort(key=lambda item: (_normalise(self._room_name(item)), _normalise(_label(item))))

        if not lights:
            answer = self._response(
                "No selected Hubitat lights were found, so today's light-on time cannot be calculated.",
                "fallback-light-usage-today-empty",
                True,
                live,
            )
            answer["display"] = display_payload(
                "light-usage-today",
                "Today's light usage",
                subtitle="No selected lights",
                metrics=[{"label": "Lights", "value": "0", "icon": "💡"}],
                note="Only lights selected in MCP Rule Server can be included.",
            )
            return answer

        semaphore = asyncio.Semaphore(4)

        async def read(item: dict[str, Any]) -> tuple[dict[str, Any], Any, str | None]:
            async with semaphore:
                try:
                    result = await self.client.call_tool(
                        "hub_list_device_events",
                        {"deviceId": _device_id(item), "hoursBack": 36},
                    )
                    if result.is_error:
                        return item, result, result.text or "event history read failed"
                    return item, result, None
                except Exception as exc:
                    return item, None, str(exc) or exc.__class__.__name__

        reads = await asyncio.gather(*(read(item) for item in lights))
        usage: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for item, result, error in reads:
            label = _label(item) or f"Device {_device_id(item)}"
            if error or result is None:
                errors.append({"device": label, "error": error or "No result"})
                continue
            calculated = calculate_on_time(
                switch_events(result.data, now.tzinfo),
                day_start,
                now,
                _normalise(live_attributes(item).get("switch")),
            )
            usage.append(
                {
                    "id": _device_id(item),
                    "label": label,
                    "room": self._room_name(item) or "No room assigned",
                    **calculated,
                }
            )

        if not usage:
            answer = self._response(
                "Today's light-on time is unavailable because Hubitat returned no usable switch-event history.",
                "fallback-light-usage-today-unavailable",
                False,
                live,
            )
            answer["route"] = "mcp-fast"
            answer["display"] = display_payload(
                "light-usage-today-unavailable",
                "Light usage unavailable",
                subtitle="Historical switch events could not be read",
                metrics=[
                    {"label": "Lights", "value": str(len(lights)), "icon": "💡"},
                    {"label": "Event reads", "value": "0", "icon": "🕘"},
                    {"label": "Cloud", "value": "Not used", "icon": "🛡️"},
                ],
                note="; ".join(f"{item['device']}: {item['error']}" for item in errors[:6]),
            )
            answer["technical"] = safe_debug(
                {
                    "period_start": day_start.isoformat(),
                    "period_end": now.isoformat(),
                    "selected_light_count": len(lights),
                    "errors": errors,
                    "cloud_fallback_blocked": True,
                }
            )
            return answer

        usage.sort(key=lambda item: (-float(item["seconds"]), str(item["label"]).lower()))
        active = [item for item in usage if float(item["seconds"]) > 0]
        incomplete = [item for item in usage if item.get("incomplete")]
        total_seconds = sum(float(item["seconds"]) for item in usage)

        items: list[dict[str, Any]] = []
        lines: list[str] = []
        for item in active[:30]:
            notes = list(item.get("notes") or [])
            items.append(
                {
                    "icon": "💡",
                    "title": str(item["label"]),
                    "value": duration_text(float(item["seconds"]), True),
                    "subtitle": str(item["room"]) + (" · Incomplete: " + "; ".join(notes) if notes else ""),
                    "tone": "warning" if notes else None,
                }
            )
            lines.append(
                f"- {item['label']}: {duration_text(float(item['seconds']))}"
                + (" (history incomplete)" if notes else "")
            )

        if active:
            message = (
                f"Combined light-on time today is {duration_text(total_seconds)} across {len(active)} "
                f"light{'s' if len(active) != 1 else ''}. This is bulb-hours: overlapping lights "
                "are added together, so it is not wall-clock elapsed time.\n"
                + "\n".join(lines)
                + f"\nLongest individual on-time: {active[0]['label']} at "
                + duration_text(float(active[0]["seconds"]))
                + "."
            )
        else:
            message = "No complete light-on intervals were recorded from midnight to now."
        if incomplete:
            message += (
                f"\n{len(incomplete)} light event log{'s are' if len(incomplete) != 1 else ' is'} "
                "incomplete. Uncertain intervals were not estimated or added."
            )
        if errors:
            message += f"\nEvent history for {len(errors)} selected light{'s' if len(errors) != 1 else ''} was unavailable and excluded."

        answer = self._response(message, "fallback-light-usage-today", True, live)
        answer["route"] = "mcp-fast"
        answer["display"] = display_payload(
            "light-usage-today",
            "Today's light usage",
            subtitle=f"Midnight to {now.strftime('%H:%M')}",
            metrics=[
                {"label": "Combined bulb-hours", "value": duration_text(total_seconds, True), "icon": "⏱️"},
                {"label": "Lights with usage", "value": str(len(active)), "icon": "💡"},
                {"label": "Incomplete logs", "value": str(len(incomplete) + len(errors)), "icon": "⚠️"},
            ],
            items=items,
            note=(
                "Calculated from Hubitat switch on/off events. Individual durations are added, "
                "so simultaneous lights count separately. AI does not calculate the result."
            ),
        )
        answer.update(
            {
                "metric": "combined-bulb-hours",
                "combined_seconds": total_seconds,
                "lights_with_usage": len(active),
                "incomplete_logs": len(incomplete) + len(errors),
                "usage": usage,
            }
        )
        answer["technical"] = safe_debug(
            {
                "period_start": day_start.isoformat(),
                "period_end": now.isoformat(),
                "metric": "combined-bulb-hours",
                "selected_light_count": len(lights),
                "event_reads_succeeded": len(usage),
                "event_reads_failed": len(errors),
                "combined_seconds": total_seconds,
                "light_usage": usage,
                "errors": errors,
                "calculation": "Python paired Hubitat switch events; uncertain intervals were excluded.",
                "cloud_fallback_blocked": True,
            }
        )
        return answer


__all__ = ["FastFallbackRouter", "is_light_usage_today_query"]

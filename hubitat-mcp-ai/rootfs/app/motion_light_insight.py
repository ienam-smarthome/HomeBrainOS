from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

from device_intelligence_index import (
    _attributes,
    _label,
    _looks_like_light,
    _normalise,
    _room_name,
)
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_MOTION_LIGHT_QUERY = re.compile(
    r"^(?:find|show|list|check)\s+(?:the\s+)?active\s+(?:motion|motion sensors?)"
    r"(?:\s+and)?\s+(?:tell|show|list)?\s*(?:me\s+)?(?:which\s+)?(?:nearby\s+)?"
    r"lights?\s+(?:are\s+)?off[?.!]*$"
    r"|^(?:which|what)\s+lights?\s+are\s+off\s+(?:near|nearby|in\s+rooms?\s+with)\s+"
    r"active\s+(?:motion|motion sensors?)[?.!]*$",
    re.IGNORECASE,
)


def _state(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", value.get("currentValue", value.get("currentState")))
    return _normalise(value)


class MotionLightInsightService:
    """Relate active motion to off lights using exact Hubitat room membership."""

    def __init__(
        self,
        application: Any,
        device_index: Any,
        *,
        ai_timeout_seconds: float = 20.0,
    ) -> None:
        self.application = application
        self.device_index = device_index
        self.ai_timeout_seconds = max(8.0, min(60.0, float(ai_timeout_seconds)))

    @staticmethod
    def matches(query: str) -> bool:
        return bool(_MOTION_LIGHT_QUERY.match(str(query or "").strip()))

    async def answer(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        devices = list(await self.device_index.enriched_devices(force=True))
        states_read = sum(1 for item in devices if _attributes(item))

        if devices and states_read == 0:
            message = (
                "I could not verify motion or light states because Hubitat returned "
                "device records without readable live attributes. I have not treated "
                "the missing states as inactive motion or lights off."
            )
            return {
                "success": False,
                "route": "mcp-motion-light-state-unavailable",
                "intent": "active-motion-nearby-lights",
                "message": message,
                "evidence_source": "Hubitat MCP",
                "display": display_payload(
                    "motion-light-insight",
                    "Active motion and nearby lights",
                    subtitle="Live state scan unavailable",
                    metrics=[
                        {"label": "Active motion", "value": "—", "icon": "🏃"},
                        {"label": "Nearby lights off", "value": "—", "icon": "💡"},
                    ],
                    note=(
                        "Nearby means the same assigned Hubitat room. Missing states were "
                        "not converted into zero counts."
                    ),
                ),
                "states_read": states_read,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }

        active_motion: list[dict[str, str]] = []
        off_lights_by_room: dict[str, list[str]] = {}
        room_labels: dict[str, str] = {}

        for item in devices:
            if item.get("disabled") is True:
                continue
            attrs = _attributes(item)
            room = _room_name(item)
            room_key = _normalise(room)
            if room_key and room:
                room_labels.setdefault(room_key, room)

            if _state(attrs.get("motion")) == "active":
                active_motion.append(
                    {
                        "device": _label(item) or "Unnamed motion sensor",
                        "room": room,
                        "room_key": room_key,
                    }
                )

            groups = set()
            group_resolver = getattr(self.device_index, "_groups", None)
            if callable(group_resolver):
                try:
                    groups = set(group_resolver(item))
                except Exception:
                    groups = set()
            is_light = "light" in groups or _looks_like_light(item)
            if is_light and _state(attrs.get("switch")) == "off" and room_key:
                off_lights_by_room.setdefault(room_key, []).append(
                    _label(item) or "Unnamed light"
                )

        active_motion.sort(
            key=lambda item: (_normalise(item.get("room")), _normalise(item.get("device")))
        )
        active_room_keys = sorted(
            {item["room_key"] for item in active_motion if item["room_key"]}
        )
        nearby_off: list[dict[str, Any]] = []
        for room_key in active_room_keys:
            lights = sorted(
                dict.fromkeys(off_lights_by_room.get(room_key, [])),
                key=str.lower,
            )
            nearby_off.append(
                {
                    "room": room_labels.get(room_key, room_key.title()),
                    "lights_off": lights,
                }
            )

        deterministic = self._deterministic(active_motion, nearby_off)
        ai_message: str | None = None
        ai_error: str | None = None
        model: str | None = None
        ai_provider: str | None = None

        if active_motion:
            try:
                ai_message, model, ai_provider = await asyncio.wait_for(
                    self._natural_answer(
                        query,
                        active_motion,
                        nearby_off,
                        deterministic,
                    ),
                    timeout=self.ai_timeout_seconds + 1.0,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                ai_error = str(exc) or exc.__class__.__name__

        message = ai_message or deterministic
        items: list[dict[str, Any]] = []
        for room_key in active_room_keys:
            room = room_labels.get(room_key, room_key.title())
            sensors = [
                item["device"] for item in active_motion if item["room_key"] == room_key
            ]
            items.append(
                {
                    "group": room,
                    "icon": "🏃",
                    "title": ", ".join(sensors),
                    "value": "Active",
                    "subtitle": "Live motion in this Hubitat room",
                    "tone": "success",
                }
            )
            lights = off_lights_by_room.get(room_key, [])
            if lights:
                for light in sorted(dict.fromkeys(lights), key=str.lower):
                    items.append(
                        {
                            "group": room,
                            "icon": "💡",
                            "title": light,
                            "value": "Off",
                            "subtitle": "Same Hubitat room as active motion",
                        }
                    )
            else:
                items.append(
                    {
                        "group": room,
                        "icon": "✅",
                        "title": "No nearby off light found",
                        "value": "",
                        "subtitle": "No off light is assigned to this room",
                    }
                )

        unassigned_motion = [
            item["device"] for item in active_motion if not item["room_key"]
        ]
        if unassigned_motion:
            for sensor in unassigned_motion:
                items.append(
                    {
                        "group": "No room assigned",
                        "icon": "🏷️",
                        "title": sensor,
                        "value": "Active",
                        "subtitle": "A nearby light cannot be inferred without a room",
                        "tone": "warning",
                    }
                )

        off_count = sum(len(item["lights_off"]) for item in nearby_off)
        display = display_payload(
            "motion-light-insight",
            "Active motion and nearby lights",
            subtitle="Nearby = same assigned Hubitat room",
            metrics=[
                {
                    "label": "Active sensors",
                    "value": str(len(active_motion)),
                    "icon": "🏃",
                },
                {
                    "label": "Active rooms",
                    "value": str(len(active_room_keys)),
                    "icon": "🚪",
                },
                {
                    "label": "Nearby lights off",
                    "value": str(off_count),
                    "icon": "💡",
                },
            ],
            items=items,
            note=(
                "Motion and switch values are verified Hubitat MCP states. HomeBrain "
                "does not infer physical distance; nearby means the same assigned room."
                + (
                    " AI wording failed, so the deterministic comparison is shown."
                    if ai_error
                    else ""
                )
            ),
        )
        display["summary"] = message

        return {
            "success": True,
            "route": (
                "ollama+motion-light-insight"
                if ai_message
                else "mcp-motion-light-insight-ai-fallback"
                if active_motion
                else "mcp-motion-light-insight"
            ),
            "intent": "active-motion-nearby-lights",
            "message": message,
            "model": model,
            "answered_by": "Ollama" if ai_message else "HomeBrain comparison",
            "ai_provider": ai_provider,
            "ai_attempted": bool(active_motion),
            "ai_used": bool(ai_message),
            "ai_status": (
                "used" if ai_message else "fallback" if active_motion else "not-attempted"
            ),
            "evidence_source": "Hubitat MCP",
            "display": display,
            "active_motion": active_motion,
            "nearby_off_lights": nearby_off,
            "states_read": states_read,
            "synthesis_error": ai_error,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "active_motion": active_motion,
                    "nearby_off_lights": nearby_off,
                    "states_read": states_read,
                    "model": model,
                    "ai_provider": ai_provider,
                    "ollama_synthesis_error": ai_error,
                }
            ),
        }

    @staticmethod
    def _deterministic(
        active_motion: list[dict[str, str]],
        nearby_off: list[dict[str, Any]],
    ) -> str:
        if not active_motion:
            return "No motion sensors currently report active motion."

        sensor_text = ", ".join(
            f"{item['device']} ({item['room'] or 'no room assigned'})"
            for item in active_motion
        )
        off_entries = [
            f"{item['room']}: {', '.join(item['lights_off'])}"
            for item in nearby_off
            if item["lights_off"]
        ]
        if off_entries:
            off_text = "; ".join(off_entries)
            return (
                f"Active motion is reported by {sensor_text}. Lights that are off in "
                f"those same Hubitat rooms: {off_text}."
            )
        return (
            f"Active motion is reported by {sensor_text}. I found no light currently "
            "off in the same assigned Hubitat rooms."
        )

    async def _natural_answer(
        self,
        query: str,
        active_motion: list[dict[str, str]],
        nearby_off: list[dict[str, Any]],
        deterministic: str,
    ) -> tuple[str, str, str]:
        ollama = self.application.ollama
        health = await ollama.health()
        if not health.get("online"):
            raise RuntimeError(health.get("error") or "Ollama is offline")
        installed = list(health.get("models") or [])
        resolver = getattr(ollama, "_resolve_routine_model", None)
        model = (
            resolver(installed)
            if callable(resolver)
            else str(getattr(ollama, "model", ""))
        )
        body = await ollama._chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are HomeBrain. Answer using only the verified Hubitat evidence. "
                        "Nearby means the same assigned Hubitat room, not physical distance. "
                        "Name the active motion sensors and list only lights whose verified "
                        "switch state is off in those active rooms. Be concise and do not "
                        "invent occupancy, causes or unreported device states."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {query}\n"
                        f"Active motion: {json.dumps(active_motion, ensure_ascii=False, separators=(',', ':'))}\n"
                        f"Off lights in active rooms: {json.dumps(nearby_off, ensure_ascii=False, separators=(',', ':'))}\n"
                        f"Reliable fallback: {deterministic}"
                    ),
                },
            ],
            tools=None,
            timeout_seconds=self.ai_timeout_seconds,
            num_ctx=min(int(getattr(ollama, "num_ctx", 2048)), 2048),
            num_predict=130,
            temperature=0.1,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty motion/light answer")
        actual_model = str(body.get("_homebrain_model_used") or model).strip()
        provider = str(body.get("_homebrain_provider") or "Local Ollama").strip()
        return content, actual_model, provider


def install_motion_light_insight(
    application: Any,
    device_index: Any,
    *,
    ai_timeout_seconds: float = 20.0,
) -> MotionLightInsightService:
    original_ask: AskHandler = application.ask
    service = MotionLightInsightService(
        application,
        device_index,
        ai_timeout_seconds=ai_timeout_seconds,
    )

    async def ask_with_motion_light_insight(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if service.matches(query):
            answer = await service.answer(query)
            answer.setdefault("version", application.VERSION)
            return answer
        return await original_ask(request)

    application.ask = ask_with_motion_light_insight
    application.motion_light_insight = service
    return service


__all__ = [
    "MotionLightInsightService",
    "_MOTION_LIGHT_QUERY",
    "install_motion_light_insight",
]

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from device_intelligence_index import _attributes, _label, _normalise, _room_name
from presenter import display_payload, safe_debug


_TEMPERATURE_COMPARE_QUERY = re.compile(
    r"^(?:compare|analyse|analyze)\s+(?:the\s+)?(?:bedroom|bedrooms|room)\s+"
    r"temperatures?(?:\s+and\s+(?:explain|describe|tell\s+me\s+about)\s+"
    r"(?:the\s+)?differences?)?[?.!]*$"
    r"|^(?:which\s+bedroom\s+is\s+(?:warmest|coldest)|"
    r"why\s+are\s+(?:the\s+)?bedroom\s+temperatures?\s+different)[?.!]*$",
    re.IGNORECASE,
)

_BEDROOM_NUMBERS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
}


def _value(raw: Any) -> Any:
    if isinstance(raw, dict):
        for key in ("value", "currentValue", "currentState"):
            if raw.get(key) not in (None, ""):
                return raw[key]
    return raw


def _number(raw: Any) -> float | None:
    raw = _value(raw)
    try:
        match = re.search(r"-?\d+(?:\.\d+)?", str(raw or ""))
        return float(match.group(0)) if match else None
    except Exception:
        return None


def _inferred_room(value: str) -> str:
    match = re.search(
        r"\bbedroom\s*([0-9]+|one|two|three|four|five|six)\b",
        str(value or ""),
        re.I,
    )
    if not match:
        return ""
    token = match.group(1).lower()
    return f"Bedroom {_BEDROOM_NUMBERS.get(token, token)}"


class TemperatureInsightService:
    """Compare verified room temperatures, then optionally ask Ollama to explain.

    This route deliberately skips the general MCP planner. The device index already
    contains the authoritative temperature readings, so Ollama receives a small,
    bounded evidence packet and performs one wording/reasoning pass only.
    """

    def __init__(
        self,
        application: Any,
        device_index: Any,
        *,
        timeout_seconds: float = 25.0,
    ) -> None:
        self.application = application
        self.device_index = device_index
        self.timeout_seconds = max(8.0, min(60.0, float(timeout_seconds)))

    @staticmethod
    def matches(query: str) -> bool:
        return bool(_TEMPERATURE_COMPARE_QUERY.match(str(query or "").strip()))

    async def answer(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        devices = list(await self.device_index.enriched_devices())
        readings = self._room_readings(devices, query)
        deterministic = self._deterministic(readings)

        ai_message: str | None = None
        ai_error: str | None = None
        model = str(self.application.OPTIONS.get("ollama_model") or "").strip()
        if readings:
            try:
                ai_message, model = await asyncio.wait_for(
                    self._natural_answer(query, readings, deterministic),
                    timeout=self.timeout_seconds + 1.0,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                ai_error = str(exc) or exc.__class__.__name__

        ai_used = bool(ai_message)
        ai_attempted = bool(readings)
        message = ai_message or deterministic
        if readings:
            low = min(readings, key=lambda item: item["temperature"])
            high = max(readings, key=lambda item: item["temperature"])
            spread = high["temperature"] - low["temperature"]
            metrics = [
                {"label": "Rooms compared", "value": str(len(readings)), "icon": "🚪"},
                {"label": "Lowest", "value": f"{low['temperature']:g}°C", "icon": "❄️"},
                {"label": "Highest", "value": f"{high['temperature']:g}°C", "icon": "🔥"},
                {"label": "Difference", "value": f"{spread:g}°C", "icon": "↕️"},
            ]
        else:
            metrics = [{"label": "Readings", "value": "0", "icon": "🌡️"}]

        note = "Temperatures are verified Hubitat MCP states. Explanations are possibilities, not measured causes."
        if ai_error:
            note += " Ollama was attempted but did not finish, so the deterministic comparison is shown."

        display = display_payload(
            "temperature-comparison",
            "Bedroom temperature comparison",
            subtitle=(
                f"{len(readings)} representative live room readings"
                if readings
                else "No bedroom temperature readings were available"
            ),
            metrics=metrics,
            items=self._display_items(readings),
            note=note,
        )
        display["summary"] = message

        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": bool(readings),
            "route": (
                "ollama+temperature-insight"
                if ai_used
                else "mcp-temperature-insight-ai-fallback"
                if ai_attempted
                else "mcp-temperature-insight"
            ),
            "intent": "temperature-comparison",
            "message": message,
            "model": model or None,
            "answered_by": "Ollama" if ai_used else "HomeBrain comparison",
            "evidence_source": "Hubitat MCP",
            "display": display,
            "readings": readings,
            "ai_attempted": ai_attempted,
            "ai_used": ai_used,
            "ai_status": (
                "used" if ai_used else "fallback" if ai_attempted else "not-attempted"
            ),
            "synthesis_error": ai_error,
            "elapsed_ms": elapsed,
            "technical": safe_debug(
                {
                    "readings": readings,
                    "ollama_synthesis_error": ai_error,
                    "model": model,
                    "answered_by": "Ollama" if ai_used else "HomeBrain comparison",
                    "evidence_source": "Hubitat MCP",
                }
            ),
        }

    def _room_readings(
        self,
        devices: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        bedrooms_only = "bedroom" in _normalise(query)
        grouped: dict[str, list[dict[str, Any]]] = {}

        for item in devices:
            if item.get("disabled") is True:
                continue
            attrs = _attributes(item)
            temperature = _number(attrs.get("temperature"))
            if temperature is None:
                continue

            label = _label(item) or "Unnamed temperature device"
            assigned_room = _room_name(item)
            inferred_from_label = _inferred_room(label)

            if bedrooms_only:
                # Some Hubitat setups expose a category such as "Thermostat & TRV's"
                # in the room field. For bedroom comparisons, an explicit bedroom in
                # the device label is more trustworthy than that category. A genuine
                # assigned Bedroom room remains the fallback for generically named
                # devices such as "TRV" or "Room sensor".
                room = inferred_from_label or _inferred_room(assigned_room)
                if not room:
                    continue
            else:
                room = assigned_room or inferred_from_label or label

            grouped.setdefault(room, []).append(
                {
                    "room": room,
                    "device": label,
                    "temperature": temperature,
                    "score": self._source_score(label, room, attrs),
                }
            )

        selected: list[dict[str, Any]] = []
        for room, candidates in grouped.items():
            candidates.sort(
                key=lambda item: (-item["score"], item["device"].lower())
            )
            chosen = dict(candidates[0])
            chosen.pop("score", None)
            chosen["available_sources"] = len(candidates)
            chosen["alternate_sources"] = [
                {
                    "device": candidate["device"],
                    "temperature": candidate["temperature"],
                }
                for candidate in candidates[1:]
            ]
            selected.append(chosen)

        selected.sort(key=lambda item: _normalise(item["room"]))
        return selected

    @staticmethod
    def _display_items(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for reading in readings:
            room = reading["room"]
            representative = reading["temperature"]
            items.append(
                {
                    "icon": "🌡️",
                    "title": room,
                    "value": f"{representative:g}°C",
                    "subtitle": f"Representative: {reading['device']}",
                    "group": room,
                    "tone": None,
                }
            )
            for alternate in reading.get("alternate_sources") or []:
                difference = abs(float(alternate["temperature"]) - float(representative))
                label_text = _normalise(alternate["device"])
                icon = "♨️" if "trv" in label_text or "thermostat" in label_text else "🌡️"
                items.append(
                    {
                        "icon": icon,
                        "title": alternate["device"],
                        "value": f"{alternate['temperature']:g}°C",
                        "subtitle": "Additional sensor in this room",
                        "group": room,
                        "tone": "warning" if difference >= 1.5 else None,
                    }
                )
        return items

    @staticmethod
    def _source_score(
        label: str,
        room: str,
        attrs: dict[str, Any],
    ) -> int:
        text = _normalise(label)
        score = 0
        if "meter" in text:
            score += 8
        if "temperature" in text or "temp" in text:
            score += 6
        if "sensor" in text:
            score += 2
        if _normalise(room) and _normalise(room) in text:
            score += 2
        if "thermostat" in text or "trv" in text:
            score -= 3
        if any(term in text for term in ("battery", "humidity", "lux")):
            score -= 10
        if "temperature" in attrs:
            score += 1
        return score

    @staticmethod
    def _deterministic(readings: list[dict[str, Any]]) -> str:
        if not readings:
            return (
                "I could not find live bedroom temperature readings in the selected "
                "Hubitat MCP devices."
            )
        if len(readings) == 1:
            item = readings[0]
            return (
                f"Only {item['room']} has a usable representative reading: "
                f"{item['temperature']:g}°C, from {item['device']}. More than one room "
                "is needed for a comparison."
            )

        low = min(readings, key=lambda item: item["temperature"])
        high = max(readings, key=lambda item: item["temperature"])
        spread = high["temperature"] - low["temperature"]
        values = ", ".join(
            f"{item['room']} {item['temperature']:g}°C" for item in readings
        )
        if spread < 0.5:
            comparison = "The representative readings are effectively the same."
        elif spread < 1.5:
            comparison = f"The representative-room spread is small at {spread:g}°C."
        else:
            comparison = (
                f"{high['room']} is {spread:g}°C warmer than {low['room']} "
                "using the representative room sensors."
            )

        alternate_values: list[str] = []
        for item in readings:
            for alternate in item.get("alternate_sources") or []:
                alternate_values.append(
                    f"{item['room']} also has {alternate['device']} at "
                    f"{alternate['temperature']:g}°C"
                )
        alternate_text = (
            " Additional sensor readings: " + "; ".join(alternate_values) + "."
            if alternate_values
            else ""
        )

        return (
            f"Bedroom temperatures: {values}. {comparison}{alternate_text} Possible "
            "reasons include different heating demand, radiator proximity, sunlight, "
            "airflow, door position or sensor placement; the live readings do not "
            "prove one cause."
        )

    async def _natural_answer(
        self,
        query: str,
        readings: list[dict[str, Any]],
        deterministic: str,
    ) -> tuple[str, str]:
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
        evidence = [
            {
                "room": item["room"],
                "representative_temperature_c": item["temperature"],
                "representative_device": item["device"],
                "alternate_sensors": [
                    {
                        "device": alternate["device"],
                        "temperature_c": alternate["temperature"],
                    }
                    for alternate in item.get("alternate_sources") or []
                ],
            }
            for item in readings
        ]
        body = await ollama._chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are HomeBrain, a concise smart-home analyst. Compare only the "
                        "verified temperatures supplied. Count each room once using its "
                        "representative temperature. Alternate sensors belong to the same room "
                        "and must never be described as separate rooms. State each bedroom's "
                        "representative reading, then the coldest, warmest and exact room-to-room "
                        "difference. Mention any meaningful same-room sensor discrepancy, "
                        "especially a warmer TRV versus an ambient meter. Explain plausible "
                        "causes cautiously as possibilities, not facts. Do not claim knowledge "
                        "of windows, heating, occupancy or sensor placement unless supplied. "
                        "Use two or three short paragraphs."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {query}\n"
                        f"Verified readings: {json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}\n"
                        f"Reliable fallback wording: {deterministic}"
                    ),
                },
            ],
            tools=None,
            timeout_seconds=self.timeout_seconds,
            num_ctx=min(int(getattr(ollama, "num_ctx", 2048)), 2048),
            num_predict=170,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty temperature comparison")
        return content, model


__all__ = ["TemperatureInsightService", "_TEMPERATURE_COMPARE_QUERY"]

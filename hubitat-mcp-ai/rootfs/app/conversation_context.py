from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from device_intelligence_index import _attributes, _device_id, _label, _normalise, _room_name
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


_METRICS = {
    "hottest": ("temperature", max, "°C", "Highest temperature"),
    "warmest": ("temperature", max, "°C", "Highest temperature"),
    "coldest": ("temperature", min, "°C", "Lowest temperature"),
    "coolest": ("temperature", min, "°C", "Lowest temperature"),
    "lowest battery": ("battery", min, "%", "Lowest battery"),
    "weakest battery": ("battery", min, "%", "Lowest battery"),
    "highest battery": ("battery", max, "%", "Highest battery"),
    "most power": ("power", max, " W", "Highest power"),
    "highest power": ("power", max, " W", "Highest power"),
    "most humid": ("humidity", max, "%", "Highest humidity"),
    "highest humidity": ("humidity", max, "%", "Highest humidity"),
    "driest": ("humidity", min, "%", "Lowest humidity"),
    "lowest humidity": ("humidity", min, "%", "Lowest humidity"),
}

_ORDINALS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "fifth": 4,
    "5th": 4,
}

_STATE_WORDS = {
    "active": ("motion", "active"),
    "inactive": ("motion", "inactive"),
    "open": ("contact", "open"),
    "closed": ("contact", "closed"),
    "on": ("switch", "on"),
    "off": ("switch", "off"),
    "present": ("presence", "present"),
    "away": ("presence", "not present"),
}

_TYPE_INTENTS = {
    "fallback-lights-on": "light",
    "fallback-switches-on": "switch",
    "fallback-motion-active": "motion",
    "fallback-low-batteries": "battery",
}


@dataclass(slots=True)
class ContextDevice:
    device_id: str
    label: str
    room: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def response(self) -> dict[str, Any]:
        return {
            "id": self.device_id,
            "label": self.label,
            "room": self.room,
            "attributes": dict(self.attributes),
        }


@dataclass(slots=True)
class ConversationState:
    session_id: str
    updated_at: float
    expires_at: float
    last_query: str = ""
    last_resolved_query: str = ""
    last_device_type: str | None = None
    last_room: str | None = None
    devices: list[ContextDevice] = field(default_factory=list)
    last_intent: str | None = None

    def response(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "age_seconds": round(max(0.0, time.time() - self.updated_at), 2),
            "expires_in_seconds": round(max(0.0, self.expires_at - time.time()), 2),
            "last_query": self.last_query,
            "last_resolved_query": self.last_resolved_query,
            "last_device_type": self.last_device_type,
            "last_room": self.last_room,
            "last_intent": self.last_intent,
            "devices": [item.response() for item in self.devices],
        }


@dataclass(slots=True)
class ContextResolution:
    query: str
    answer: dict[str, Any] | None = None
    reason: str | None = None


class ConversationContextStore:
    """Short-lived, per-browser structured context for safe follow-up questions."""

    def __init__(
        self,
        device_index: Any,
        fallback: Any,
        *,
        ttl_seconds: float = 600.0,
        max_sessions: int = 128,
        max_group_control: int = 8,
    ) -> None:
        self.device_index = device_index
        self.fallback = fallback
        self.ttl_seconds = max(60.0, float(ttl_seconds))
        self.max_sessions = max(8, min(1000, int(max_sessions)))
        self.max_group_control = max(1, min(20, int(max_group_control)))
        self._items: dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def session_id(request: Any) -> str:
        value = str(getattr(request, "session_id", "") or "default").strip()
        return value[:160] or "default"

    async def get(self, session_id: str) -> ConversationState | None:
        key = str(session_id or "default")[:160]
        async with self._lock:
            self._purge_locked()
            return self._items.get(key)

    async def clear(self, session_id: str) -> bool:
        key = str(session_id or "default")[:160]
        async with self._lock:
            return self._items.pop(key, None) is not None

    async def clear_all(self) -> int:
        async with self._lock:
            count = len(self._items)
            self._items.clear()
            return count

    async def diagnostics(self, session_id: str) -> dict[str, Any]:
        state = await self.get(session_id)
        return {
            "success": True,
            "active": state is not None,
            "context": state.response() if state else None,
            "ttl_seconds": self.ttl_seconds,
            "active_sessions": len(self._items),
        }

    async def resolve(self, request: Any) -> ContextResolution:
        query = str(getattr(request, "query", "") or "").strip()
        state = await self.get(self.session_id(request))
        if not state or not query:
            return ContextResolution(query=query)

        comparison = self._comparison_metric(query)
        if comparison:
            answer = await self._comparison_answer(state, comparison)
            if answer:
                return ContextResolution(query=query, answer=answer, reason="context-comparison")

        filtered_state = self._state_filter(query)
        if filtered_state:
            if state.last_device_type == "motion" and filtered_state == "active":
                return ContextResolution(
                    query="Which motion sensors are active?",
                    reason="context-active-motion",
                )
            answer = await self._filtered_answer(state, filtered_state)
            if answer:
                return ContextResolution(query=query, answer=answer, reason="context-state-filter")

        room = self._room_follow_up(query)
        if room and state.last_device_type:
            answer = await self._room_answer(state, room)
            if answer:
                return ContextResolution(query=query, answer=answer, reason="context-room-follow-up")

        control = self._contextual_control(query)
        if control:
            action, target = control
            candidates = await self._current_context_devices(state)
            matched, plural = self._resolve_control_target(target, candidates)
            if len(matched) == 1:
                resolved = f"turn {action} {matched[0].label}"
                return ContextResolution(query=resolved, reason="context-single-device-control")
            if plural and matched:
                answer = await self._control_group(action, target, matched)
                return ContextResolution(query=query, answer=answer, reason="context-device-group-control")
            return ContextResolution(
                query=query,
                answer=self._clarification_answer(target, candidates, matched),
                reason="context-control-ambiguous",
            )

        return ContextResolution(query=query)

    async def capture(
        self,
        request: Any,
        answer: dict[str, Any],
        *,
        original_query: str,
        resolved_query: str,
    ) -> ConversationState:
        session_id = self.session_id(request)
        now = time.time()
        existing = await self.get(session_id)
        state = existing or ConversationState(
            session_id=session_id,
            updated_at=now,
            expires_at=now + self.ttl_seconds,
        )
        state.updated_at = now
        state.expires_at = now + self.ttl_seconds
        state.last_query = original_query
        state.last_resolved_query = resolved_query
        state.last_intent = str(answer.get("intent") or "") or None

        device_type = self._device_type_from_answer(answer)
        if device_type:
            state.last_device_type = device_type
        room = str(answer.get("room") or "").strip()
        if room:
            state.last_room = room

        captured = await self._devices_from_answer(answer)
        if captured:
            state.devices = captured[:60]
            rooms = {item.room for item in captured if item.room}
            if len(rooms) == 1:
                state.last_room = next(iter(rooms))

        async with self._lock:
            self._purge_locked()
            if len(self._items) >= self.max_sessions and session_id not in self._items:
                oldest = min(self._items.values(), key=lambda item: item.updated_at)
                self._items.pop(oldest.session_id, None)
            self._items[session_id] = state
        return state

    def _purge_locked(self) -> None:
        now = time.time()
        expired = [key for key, item in self._items.items() if item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    @staticmethod
    def _comparison_metric(query: str) -> str | None:
        q = _normalise(query)
        for phrase in sorted(_METRICS, key=len, reverse=True):
            if phrase in q and any(word in q for word in ("which", "what", "one", "device", "sensor")):
                return phrase
        return None

    @staticmethod
    def _state_filter(query: str) -> str | None:
        q = _normalise(query)
        patterns = (
            r"^(?:only\s+)?(?:show\s+)?(?:the\s+)?(active|inactive|open|closed|on|off|present|away)(?:\s+ones?)?$",
            r"^(?:show|list)\s+only\s+(?:the\s+)?(active|inactive|open|closed|on|off|present|away)(?:\s+ones?)?$",
        )
        for pattern in patterns:
            match = re.match(pattern, q)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _room_follow_up(query: str) -> str | None:
        q = str(query or "").strip()
        for pattern in (
            r"^(?:and\s+)?(?:what|how)\s+about\s+(?:the\s+)?(.+?)(?:\s+room)?[?.!]*$",
            r"^(?:and\s+)?(?:in|for)\s+(?:the\s+)?(.+?)(?:\s+room)?[?.!]*$",
        ):
            match = re.match(pattern, q, flags=re.I)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _contextual_control(query: str) -> tuple[str, str] | None:
        text = str(query or "").strip()
        patterns = (
            r"^(?:please\s+)?(?:turn|switch)\s+(on|off)\s+(.+?)[?.!]*$",
            r"^(?:please\s+)?(?:turn|switch)\s+(.+?)\s+(on|off)[?.!]*$",
        )
        for index, pattern in enumerate(patterns):
            match = re.match(pattern, text, flags=re.I)
            if not match:
                continue
            action = match.group(1 if index == 0 else 2).lower()
            target = match.group(2 if index == 0 else 1).strip()
            normal = _normalise(target)
            contextual = (
                normal in {"it", "that", "this", "the one", "this one", "that one", "them", "those", "these", "all of them"}
                or bool(re.search(r"\b(?:first|second|third|fourth|fifth|[1-5](?:st|nd|rd|th))\s+one\b", normal))
                or bool(re.search(r"\b(?:the|that|this)\s+.+\s+one$", normal))
            )
            if contextual:
                return action, target
        return None

    async def _current_context_devices(self, state: ConversationState) -> list[ContextDevice]:
        if not state.devices:
            return []
        indexed = await self._indexed_devices()
        by_id = {_device_id(item): item for item in indexed if _device_id(item)}
        refreshed: list[ContextDevice] = []
        for previous in state.devices:
            item = by_id.get(previous.device_id)
            if item:
                refreshed.append(self._context_device(item))
            else:
                refreshed.append(previous)
        return refreshed

    def _resolve_control_target(
        self,
        target: str,
        candidates: list[ContextDevice],
    ) -> tuple[list[ContextDevice], bool]:
        normal = _normalise(target)
        if normal in {"them", "those", "these", "all of them"}:
            return [item for item in candidates if "switch" in item.attributes], True
        if normal in {"it", "that", "this", "the one", "this one", "that one"}:
            return (candidates if len(candidates) == 1 else []), False

        for word, index in _ORDINALS.items():
            if re.search(rf"\b{re.escape(word)}\s+one\b", normal):
                return ([candidates[index]] if index < len(candidates) else []), False

        qualifier = re.sub(r"\b(?:the|that|this|one|device|sensor|light|switch|there)\b", " ", normal)
        qualifier = re.sub(r"\s+", " ", qualifier).strip()
        if not qualifier:
            return [], False
        compact = qualifier.replace(" ", "")
        matched = []
        for item in candidates:
            searchable = _normalise(f"{item.room} {item.label}")
            if qualifier in searchable or compact in searchable.replace(" ", ""):
                matched.append(item)
        return matched, False

    async def _control_group(
        self,
        action: str,
        target: str,
        devices: list[ContextDevice],
    ) -> dict[str, Any]:
        if len(devices) > self.max_group_control:
            return {
                "success": False,
                "route": "mcp-context",
                "intent": "context-group-confirmation-required",
                "confirmation_required": True,
                "message": (
                    f'“{target}” refers to {len(devices)} devices. For safety, name a room or '
                    "a smaller device group before controlling them."
                ),
            }
        if not devices or any("switch" not in item.attributes for item in devices):
            return {
                "success": False,
                "route": "mcp-context",
                "intent": "context-group-confirmation-required",
                "confirmation_required": True,
                "message": "The previous result includes devices that cannot all be safely switched. Please name the devices or room.",
            }
        source = await self.device_index.summary_result()
        indexed = await self._indexed_devices()
        wanted = {item.device_id for item in devices}
        rows = [item for item in indexed if _device_id(item) in wanted]
        answer = await self.fallback._control_group(
            "Previous devices",
            action,
            rows,
            source,
        )
        answer["route"] = "mcp-context"
        answer["context_resolved"] = True
        answer["context_target"] = target
        return answer

    def _clarification_answer(
        self,
        target: str,
        candidates: list[ContextDevice],
        matched: list[ContextDevice],
    ) -> dict[str, Any]:
        choices = matched or candidates
        labels = [item.label for item in choices[:5]]
        if labels:
            message = "Which device did you mean: " + ", ".join(labels[:-1])
            if len(labels) > 1:
                message += f", or {labels[-1]}?"
            else:
                message += "?"
        else:
            message = f'I do not have a recent device result that safely resolves “{target}”. Please name the device.'
        return {
            "success": False,
            "route": "mcp-context",
            "intent": "context-device-clarification",
            "confirmation_required": True,
            "message": message,
            "alternatives": labels,
        }

    async def _comparison_answer(
        self,
        state: ConversationState,
        metric_phrase: str,
    ) -> dict[str, Any] | None:
        key, chooser, unit, title = _METRICS[metric_phrase]
        devices = await self._scope_devices(state)
        values: list[tuple[float, ContextDevice]] = []
        for item in devices:
            value = self._number(item.attributes.get(key))
            if value is not None:
                values.append((value, item))
        if not values:
            return None
        winner_value = chooser(value for value, _ in values)
        winner = next(item for value, item in values if value == winner_value)
        ordered = sorted(values, key=lambda entry: entry[0], reverse=chooser is max)
        items = [
            {
                "icon": "📊",
                "title": item.label,
                "value": f"{value:g}{unit}",
                "subtitle": item.room or "No room assigned",
                "tone": "success" if item.device_id == winner.device_id else None,
            }
            for value, item in ordered[:8]
        ]
        message = f"{winner.label} is {metric_phrase} at {winner_value:g}{unit}."
        return {
            "success": True,
            "route": "mcp-context",
            "intent": f"context-comparison-{key}",
            "message": message,
            "device_label": winner.label,
            "display": display_payload(
                "context-comparison",
                title,
                subtitle=f"Compared {len(values)} recent devices",
                metrics=[{"label": title, "value": f"{winner_value:g}{unit}", "icon": "📊"}],
                items=items,
                note="Values were refreshed from the shared Hubitat device index.",
            ),
            "technical": safe_debug({"metric": key, "devices": [item.response() for _, item in ordered]}),
        }

    async def _filtered_answer(
        self,
        state: ConversationState,
        state_word: str,
    ) -> dict[str, Any] | None:
        attribute, expected = _STATE_WORDS[state_word]
        devices = await self._scope_devices(state)
        matched = [
            item
            for item in devices
            if _normalise(item.attributes.get(attribute)) == _normalise(expected)
        ]
        if not devices:
            return None
        items = [
            {
                "icon": "📱",
                "title": item.label,
                "value": str(item.attributes.get(attribute) or state_word).replace("_", " ").title(),
                "subtitle": item.room or "No room assigned",
            }
            for item in matched
        ]
        message = (
            f"{len(matched)} of the {len(devices)} recent devices are {state_word}."
            if matched
            else f"None of the {len(devices)} recent devices are {state_word}."
        )
        return {
            "success": True,
            "route": "mcp-context",
            "intent": f"context-filter-{state_word}",
            "message": message,
            "device_type": state.last_device_type,
            "display": display_payload(
                "context-device-filter",
                f"{state_word.title()} devices",
                subtitle=f"Filtered the previous {state.last_device_type or 'device'} result",
                metrics=[
                    {"label": state_word.title(), "value": str(len(matched)), "icon": "🔎"},
                    {"label": "Previous result", "value": str(len(devices)), "icon": "📱"},
                ],
                items=items,
                note="The previous result was refreshed from Hubitat before filtering.",
            ),
        }

    async def _room_answer(
        self,
        state: ConversationState,
        requested_room: str,
    ) -> dict[str, Any] | None:
        indexed = await self._indexed_devices()
        room_target = _normalise(requested_room)
        compact = room_target.replace(" ", "")
        rooms = sorted({_room_name(item) for item in indexed if _room_name(item)})
        matched_rooms = [
            room for room in rooms
            if _normalise(room) == room_target or _normalise(room).replace(" ", "") == compact
        ]
        if len(matched_rooms) != 1:
            return None
        room = matched_rooms[0]
        devices = [
            self._context_device(item)
            for item in indexed
            if _normalise(_room_name(item)) == _normalise(room)
            and state.last_device_type in self.device_index._groups(item)
        ]
        attribute = self._primary_attribute(state.last_device_type)
        items = [
            {
                "icon": "📱",
                "title": item.label,
                "value": self._format_value(attribute, item.attributes.get(attribute)),
                "subtitle": room,
            }
            for item in devices
        ]
        message = (
            f"{room} has {len(devices)} {state.last_device_type} device{'' if len(devices) == 1 else 's'} in the selected MCP devices."
        )
        return {
            "success": True,
            "route": "mcp-context",
            "intent": "context-room-follow-up",
            "message": message,
            "device_type": state.last_device_type,
            "room": room,
            "display": display_payload(
                "context-room-inventory",
                f"{room} · {state.last_device_type}",
                subtitle="Follow-up to the previous device-type question",
                metrics=[{"label": "Devices", "value": str(len(devices)), "icon": "🚪"}],
                items=items,
                note="Room and device type were resolved from the previous conversation context.",
            ),
        }

    async def _scope_devices(self, state: ConversationState) -> list[ContextDevice]:
        current = await self._current_context_devices(state)
        if current:
            return current
        if not state.last_device_type:
            return []
        return [
            self._context_device(item)
            for item in await self._indexed_devices()
            if state.last_device_type in self.device_index._groups(item)
        ]

    async def _devices_from_answer(self, answer: dict[str, Any]) -> list[ContextDevice]:
        indexed = await self._indexed_devices()
        by_label = {_normalise(_label(item)): item for item in indexed if _label(item)}
        wanted: list[str] = []
        if answer.get("device_label"):
            wanted.append(str(answer["device_label"]))
        display = answer.get("display")
        if isinstance(display, dict):
            for item in display.get("items") or []:
                if isinstance(item, dict) and item.get("title"):
                    wanted.append(str(item["title"]))
        captured: list[ContextDevice] = []
        seen: set[str] = set()
        for label in wanted:
            item = by_label.get(_normalise(label))
            if not item:
                continue
            device = self._context_device(item)
            if device.device_id and device.device_id not in seen:
                seen.add(device.device_id)
                captured.append(device)
        return captured

    async def _indexed_devices(self) -> list[dict[str, Any]]:
        enriched = getattr(self.device_index, "enriched_devices", None)
        if callable(enriched):
            return list(await enriched())
        return list(await self.device_index.summary_devices())

    @staticmethod
    def _context_device(item: dict[str, Any]) -> ContextDevice:
        return ContextDevice(
            device_id=_device_id(item),
            label=_label(item),
            room=_room_name(item),
            attributes=_attributes(item),
        )

    @staticmethod
    def _device_type_from_answer(answer: dict[str, Any]) -> str | None:
        value = str(answer.get("device_type") or "").strip()
        if value:
            return value
        intent = str(answer.get("intent") or "")
        if intent.startswith("fallback-device-type-"):
            return intent.removeprefix("fallback-device-type-")
        return _TYPE_INTENTS.get(intent)

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, dict):
            value = value.get("value") or value.get("currentValue")
        try:
            match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
            return float(match.group(0)) if match else None
        except Exception:
            return None

    @staticmethod
    def _primary_attribute(device_type: str | None) -> str:
        return {
            "motion": "motion",
            "contact": "contact",
            "temperature": "temperature",
            "humidity": "humidity",
            "presence": "presence",
            "battery": "battery",
            "power": "power",
            "energy": "energy",
            "light": "switch",
            "switch": "switch",
            "outlet": "switch",
            "thermostat": "thermostatOperatingState",
        }.get(str(device_type or ""), "status")

    @staticmethod
    def _format_value(attribute: str, value: Any) -> str:
        if value in (None, ""):
            return "Available"
        suffix = {
            "temperature": "°C",
            "humidity": "%",
            "battery": "%",
            "power": " W",
            "energy": " kWh",
        }.get(attribute, "")
        text = str(value)
        return text if not suffix or suffix.strip().lower() in text.lower() else f"{text}{suffix}"


def install_conversation_context(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    max_group_control: int = 8,
) -> ConversationContextStore:
    """Wrap the active ask handler with deterministic, per-session follow-up resolution."""
    original_ask: AskHandler = application.ask
    store = ConversationContextStore(
        device_index,
        application.fallback,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        max_group_control=max_group_control,
    )

    async def context_ask(request: Any) -> dict[str, Any]:
        started = time.perf_counter()
        original_query = str(request.query or "").strip()
        resolution = await store.resolve(request)
        request.query = resolution.query
        if resolution.answer is not None:
            answer = resolution.answer
            answer.setdefault("elapsed_ms", round((time.perf_counter() - started) * 1000))
        else:
            answer = await original_ask(request)
        state = await store.capture(
            request,
            answer,
            original_query=original_query,
            resolved_query=resolution.query,
        )
        if resolution.reason:
            answer["context_resolved"] = True
            answer["context_reason"] = resolution.reason
            answer["original_query"] = original_query
            answer["resolved_query"] = resolution.query
        answer["context_session"] = state.session_id
        return answer

    application.ask = context_ask

    @application.app.get("/api/conversation-context", response_model=None)
    async def conversation_context(session_id: str = "default"):
        return await store.diagnostics(session_id)

    @application.app.post("/api/conversation-context/clear", response_model=None)
    async def clear_conversation_context(payload: dict[str, Any] | None = None):
        session_id = str((payload or {}).get("session_id") or "default")
        removed = await store.clear(session_id)
        return {"success": True, "cleared": removed, "session_id": session_id[:160]}

    return store


__all__ = [
    "ContextDevice",
    "ConversationContextStore",
    "ConversationState",
    "install_conversation_context",
]

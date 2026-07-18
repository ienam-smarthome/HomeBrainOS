from __future__ import annotations

import re
import time
from typing import Any

from conversation_context import (
    AskHandler,
    ContextResolution,
    ConversationContextStore,
)


_DEVICE_INTENTS = {
    "fallback-lights-on",
    "fallback-switches-on",
    "fallback-motion-active",
    "fallback-low-batteries",
}


class SafeConversationContextStore(ConversationContextStore):
    """Context store that never carries device pronouns across unrelated answers."""

    @staticmethod
    def _device_context_active(state: Any) -> bool:
        # capture() clears these fields after every unrelated answer, so their
        # presence is the authoritative signal that a follow-up may reference
        # devices. This also permits room inventories and other device displays.
        return bool(
            getattr(state, "devices", None)
            or getattr(state, "last_device_type", None)
        )

    async def resolve(self, request: Any) -> ContextResolution:
        query = str(getattr(request, "query", "") or "").strip()
        state = await self.get(self.session_id(request))
        if not state or not self._device_context_active(state):
            return ContextResolution(query=query)
        return await super().resolve(request)

    async def capture(
        self,
        request: Any,
        answer: dict[str, Any],
        *,
        original_query: str,
        resolved_query: str,
    ):
        captured_now = await self._devices_from_answer(answer)
        answer_type = self._device_type_from_answer(answer)
        intent = str(answer.get("intent") or "")
        explicit_device_result = bool(
            answer_type
            or answer.get("device_label")
            or captured_now
            or intent in _DEVICE_INTENTS
            or intent.startswith("fallback-device-type-")
        )
        context_continuation = intent.startswith("context-")

        state = await super().capture(
            request,
            answer,
            original_query=original_query,
            resolved_query=resolved_query,
        )

        async with self._lock:
            if explicit_device_result:
                # An empty device inventory is meaningful. Do not retain devices
                # from the previous result and accidentally resolve "them" to it.
                state.devices = captured_now[:60]
            elif not context_continuation:
                state.devices = []
                state.last_device_type = None
                state.last_room = None
            self._items[state.session_id] = state
        return state

    @staticmethod
    def _room_follow_up(query: str) -> str | None:
        text = str(query or "").strip()
        for pattern in (
            r"^(?:and\s+)?(?:what|how)\s+about\s+(?:the\s+)?(.+?)[?.!]*$",
            r"^(?:and\s+)?(?:in|for)\s+(?:the\s+)?(.+?)[?.!]*$",
        ):
            match = re.match(pattern, text, flags=re.I)
            if match:
                return match.group(1).strip()
        return None

    async def _room_answer(self, state: Any, requested_room: str):
        answer = await super()._room_answer(state, requested_room)
        if answer is not None:
            return answer
        stripped = re.sub(r"\s+room$", "", requested_room.strip(), flags=re.I).strip()
        if stripped and stripped.lower() != requested_room.strip().lower():
            return await super()._room_answer(state, stripped)
        return None

    async def _devices_from_answer(self, answer: dict[str, Any]):
        wanted = []
        if answer.get("device_label"):
            wanted.append(str(answer["device_label"]))
        display = answer.get("display")
        if isinstance(display, dict):
            for item in display.get("items") or []:
                if isinstance(item, dict) and item.get("title"):
                    wanted.append(str(item["title"]))
        if not wanted:
            return []
        return await super()._devices_from_answer(answer)


def install_safe_conversation_context(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    max_group_control: int = 8,
) -> SafeConversationContextStore:
    """Install conservative per-browser follow-up resolution around the ask API."""
    original_ask: AskHandler = application.ask
    store = SafeConversationContextStore(
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


__all__ = ["SafeConversationContextStore", "install_safe_conversation_context"]

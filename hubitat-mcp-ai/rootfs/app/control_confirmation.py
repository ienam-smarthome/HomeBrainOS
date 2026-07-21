from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from control_language import canonicalise_basic_control
from device_intelligence_index import _normalise
from presenter import display_payload, safe_debug
from spoken_device_name import unique_spoken_match


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_YES = {"yes", "yeah", "yep", "correct", "confirm", "confirmed", "do it", "please do", "go ahead"}
_NO = {"no", "nope", "cancel", "stop", "do not", "don't", "never mind", "nevermind"}
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


@dataclass(slots=True)
class PendingControlConfirmation:
    session_id: str
    action: str
    requested_name: str
    candidates: list[str]
    created_at: float
    expires_at: float


class ControlConfirmationStore:
    """Short-lived per-browser confirmation for ambiguous device controls."""

    def __init__(self, *, ttl_seconds: float = 120.0, max_sessions: int = 128) -> None:
        self.ttl_seconds = max(30.0, min(600.0, float(ttl_seconds)))
        self.max_sessions = max(8, min(1000, int(max_sessions)))
        self._items: dict[str, PendingControlConfirmation] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def session_id(request: Any) -> str:
        value = str(getattr(request, "session_id", "") or "default").strip()
        return value[:160] or "default"

    async def get(self, session_id: str) -> PendingControlConfirmation | None:
        key = str(session_id or "default")[:160]
        async with self._lock:
            self._purge_locked()
            return self._items.get(key)

    async def put(
        self,
        session_id: str,
        *,
        action: str,
        requested_name: str,
        candidates: list[str],
    ) -> PendingControlConfirmation:
        key = str(session_id or "default")[:160]
        now = time.time()
        unique = list(dict.fromkeys(str(item).strip() for item in candidates if str(item).strip()))[:8]
        pending = PendingControlConfirmation(
            session_id=key,
            action=action,
            requested_name=requested_name,
            candidates=unique,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        async with self._lock:
            self._purge_locked()
            if len(self._items) >= self.max_sessions and key not in self._items:
                oldest = min(self._items.values(), key=lambda item: item.created_at)
                self._items.pop(oldest.session_id, None)
            self._items[key] = pending
        return pending

    async def clear(self, session_id: str) -> bool:
        key = str(session_id or "default")[:160]
        async with self._lock:
            return self._items.pop(key, None) is not None

    def _purge_locked(self) -> None:
        now = time.time()
        for key in [key for key, value in self._items.items() if value.expires_at <= now]:
            self._items.pop(key, None)


def _reply_kind(query: str) -> str | None:
    value = _normalise(query)
    if value in _YES:
        return "yes"
    if value in _NO:
        return "no"
    return None


def _choice_index(query: str, candidates: list[str]) -> int | None:
    value = _normalise(query)
    if value.isdigit():
        index = int(value) - 1
        return index if 0 <= index < len(candidates) else None
    for word, index in _ORDINALS.items():
        if value in {word, f"the {word} one", f"number {index + 1}", f"option {index + 1}"}:
            return index if index < len(candidates) else None
    exact = [index for index, label in enumerate(candidates) if _normalise(label) == value]
    return exact[0] if len(exact) == 1 else None


def _confirmation_message(action: str, candidates: list[str]) -> str:
    if len(candidates) == 1:
        return f"Did you mean {candidates[0]}? Reply Yes to turn it {action}, or No to cancel."
    lines = ["Which device did you mean?"]
    lines.extend(f"{index}. {label}" for index, label in enumerate(candidates, start=1))
    lines.append("Reply with the number or exact device name. Reply No to cancel.")
    return "\n".join(lines)


def _confirmation_display(action: str, candidates: list[str]) -> dict[str, Any]:
    return display_payload(
        "control-confirmation",
        "Confirm device",
        subtitle=f"Requested action: {action.title()}",
        metrics=[
            {"label": "Action", "value": action.title(), "icon": "🎯"},
            {"label": "Matches", "value": str(len(candidates)), "icon": "🔎"},
        ],
        items=[
            {
                "icon": "📱",
                "title": label,
                "value": "Reply Yes" if len(candidates) == 1 else str(index),
                "query": "Yes" if len(candidates) == 1 else str(index),
                "subtitle": "Suggested device" if len(candidates) == 1 else "Reply with this number",
            }
            for index, label in enumerate(candidates, start=1)
        ],
        note=(
            "No command has been sent. The confirmation expires automatically."
        ),
    )


def _mark_spoken_resolution(
    answer: dict[str, Any],
    *,
    original_query: str,
    requested_name: str,
    resolved_name: str,
    action: str,
) -> dict[str, Any]:
    updated = dict(answer)
    updated["spoken_name_resolution"] = {
        "requested_name": requested_name,
        "resolved_name": resolved_name,
        "method": "unique-spoken-key",
        "automatic": True,
    }
    updated["original_query"] = original_query
    updated["resolved_query"] = f"turn {action} {resolved_name}"
    updated["resolved_device_name"] = resolved_name
    updated["auto_resolved_confirmation"] = True

    display = updated.get("display")
    if isinstance(display, dict):
        display = dict(display)
        existing = str(display.get("note") or "").strip()
        resolution_note = (
            f"Speech name resolved uniquely: {requested_name} → {resolved_name}. "
            "The final state was still verified from Hubitat."
        )
        display["note"] = f"{existing} {resolution_note}".strip()
        updated["display"] = display
    return updated


def install_control_confirmation(
    application: Any,
    *,
    ttl_seconds: float = 120.0,
    max_sessions: int = 128,
) -> ControlConfirmationStore:
    """Allow safe Yes/No and numbered follow-ups for pending controls.

    Before displaying an ambiguity menu, obvious speech variations are compared with
    the returned selected-device labels. Automatic execution is allowed only when one
    candidate has an identical conservative spoken-name key. General fuzzy scores are
    never used to choose a device.
    """
    original_ask: AskHandler = application.ask
    store = ControlConfirmationStore(
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
    )

    async def ask_with_confirmation(request: Any) -> dict[str, Any]:
        session_id = store.session_id(request)
        query = str(getattr(request, "query", "") or "").strip()
        pending = await store.get(session_id)

        if pending is not None:
            reply = _reply_kind(query)
            if reply == "no":
                await store.clear(session_id)
                return {
                    "success": True,
                    "route": "mcp-confirmation",
                    "intent": "control-confirmation-cancelled",
                    "message": "Cancelled. No device command was sent.",
                    "display": display_payload(
                        "control-confirmation-cancelled",
                        "Command cancelled",
                        subtitle="No device was changed",
                        metrics=[{"label": "Command", "value": "Cancelled", "icon": "🛑"}],
                    ),
                }

            selected: str | None = None
            if reply == "yes" and len(pending.candidates) == 1:
                selected = pending.candidates[0]
            elif reply == "yes":
                return {
                    "success": False,
                    "route": "mcp-confirmation",
                    "intent": "control-confirmation-choice-required",
                    "confirmation_required": True,
                    "message": _confirmation_message(pending.action, pending.candidates),
                    "display": _confirmation_display(pending.action, pending.candidates),
                }
            else:
                index = _choice_index(query, pending.candidates)
                if index is not None:
                    selected = pending.candidates[index]

            if selected:
                await store.clear(session_id)
                original_query = query
                request.query = f"turn {pending.action} {selected}"
                answer = await original_ask(request)
                answer["confirmation_follow_up"] = True
                answer["confirmation_reply"] = original_query
                answer["confirmed_candidate"] = selected
                return answer

            # Any unrelated new explicit command supersedes the pending question.
            if canonicalise_basic_control(query) is not None:
                await store.clear(session_id)
            elif _normalise(query) in {"help", "what", "why"}:
                await store.clear(session_id)

        answer = await original_ask(request)
        if not answer.get("confirmation_required"):
            return answer

        control = canonicalise_basic_control(query)
        confirmation = answer.get("confirmation") if isinstance(answer.get("confirmation"), dict) else {}
        action = str(confirmation.get("action") or (control.action if control else "")).lower()
        requested_name = str(confirmation.get("requested_name") or (control.target if control else "")).strip()
        candidates = confirmation.get("candidates") or answer.get("alternatives") or []
        candidates = [str(item).strip() for item in candidates if str(item).strip()]
        if action not in {"on", "off"} or not candidates:
            return answer

        spoken_candidate = unique_spoken_match(requested_name, candidates)
        if spoken_candidate:
            original_query = query
            request.query = f"turn {action} {spoken_candidate}"
            resolved = dict(await original_ask(request))
            if not resolved.get("confirmation_required"):
                await store.clear(session_id)
                return _mark_spoken_resolution(
                    resolved,
                    original_query=original_query,
                    requested_name=requested_name,
                    resolved_name=spoken_candidate,
                    action=action,
                )
            request.query = original_query

        pending = await store.put(
            session_id,
            action=action,
            requested_name=requested_name,
            candidates=candidates,
        )
        updated = dict(answer)
        updated.update(
            {
                "success": False,
                "route": "mcp-confirmation",
                "intent": "control-confirmation-required",
                "confirmation_required": True,
                "message": _confirmation_message(action, pending.candidates),
                "display": _confirmation_display(action, pending.candidates),
                "confirmation": {
                    "action": action,
                    "requested_name": requested_name,
                    "candidates": pending.candidates,
                    "expires_in_seconds": store.ttl_seconds,
                },
            }
        )
        updated["technical"] = safe_debug(
            {
                "pending_confirmation": updated["confirmation"],
                "original_intent": answer.get("intent"),
            }
        )
        return updated

    application.ask = ask_with_confirmation
    application.control_confirmation_store = store
    return store


__all__ = [
    "ControlConfirmationStore",
    "PendingControlConfirmation",
    "install_control_confirmation",
]

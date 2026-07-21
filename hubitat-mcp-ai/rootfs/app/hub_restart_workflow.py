from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_YES = {"yes", "confirm", "confirmed", "do it", "go ahead", "please do", "proceed"}
_NO = {"no", "cancel", "stop", "never mind", "nevermind"}
_RESTART = re.compile(
    r"^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?(?:restart|reboot)\s+"
    r"(?:(?:the|my)\s+)?(?:hub|hubitat(?:\s+hub)?)[?.!]*$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class PendingRestart:
    expires_at: float


class HubRestartWorkflow:
    """Two-turn, explicit-confirmation workflow for the destructive hub reboot tool."""

    def __init__(self, application: Any, *, ttl_seconds: float = 120.0) -> None:
        self.application = application
        self.ttl_seconds = max(30.0, min(300.0, float(ttl_seconds)))
        self._pending: dict[str, PendingRestart] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def session_id(request: Any) -> str:
        value = str(getattr(request, "session_id", "") or "default").strip()
        return value[:160] or "default"

    @staticmethod
    def matches(query: str) -> bool:
        return bool(_RESTART.match(str(query or "").strip()))

    async def answer(self, request: Any, fallback: AskHandler) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        session_id = self.session_id(request)
        pending = await self._get(session_id)
        normal = " ".join(query.lower().strip(" .!?").split())

        if pending is not None:
            if normal in _NO:
                await self._pop(session_id)
                return self._cancelled()
            if normal in _YES:
                # Consume before the write so a timeout or repeated browser submit
                # cannot accidentally issue the destructive operation twice.
                await self._pop(session_id)
                return await self._restart()

        if not self.matches(query):
            return await fallback(request)

        await self._put(session_id)
        return self._confirmation()

    async def _put(self, session_id: str) -> None:
        async with self._lock:
            self._purge_locked()
            self._pending[session_id] = PendingRestart(
                expires_at=time.monotonic() + self.ttl_seconds
            )

    async def _get(self, session_id: str) -> PendingRestart | None:
        async with self._lock:
            self._purge_locked()
            return self._pending.get(session_id)

    async def _pop(self, session_id: str) -> PendingRestart | None:
        async with self._lock:
            self._purge_locked()
            return self._pending.pop(session_id, None)

    def _purge_locked(self) -> None:
        now = time.monotonic()
        for key in [key for key, item in self._pending.items() if item.expires_at <= now]:
            self._pending.pop(key, None)

    def _confirmation(self) -> dict[str, Any]:
        display = display_payload(
            "hub-restart-confirmation",
            "Restart the Hubitat hub now?",
            subtitle="This will temporarily take the smart-home hub offline.",
            metrics=[
                {"label": "Downtime", "value": "1–3 min", "icon": "⏱️"},
                {"label": "Backup", "value": "Required", "icon": "💾"},
            ],
            note=(
                "Choose Yes — restart hub or No — cancel below. You can also reply Yes or No. "
                "The Hubitat MCP server enforces a backup from the last 24 hours."
            ),
        )
        display["actions"] = [
            {
                "label": "Yes — restart hub",
                "query": "Yes",
                "tone": "danger",
                "icon": "🔄",
            },
            {
                "label": "No — cancel",
                "query": "No",
                "tone": "secondary",
                "icon": "✖️",
            },
        ]
        return {
            "success": False,
            "route": "mcp-hub-restart-confirmation",
            "intent": "hub-restart-confirmation-required",
            "confirmation_required": True,
            "message": (
                "Do you want to restart the Hubitat hub now? It will be unavailable for about "
                "1–3 minutes. "
                "The MCP server also requires Hub Admin Write access and a backup from the last "
                "24 hours. Reply Yes to restart the hub, or No to cancel."
            ),
            "display": display,
        }

    @staticmethod
    def _cancelled() -> dict[str, Any]:
        return {
            "success": True,
            "route": "mcp-hub-restart-confirmation",
            "intent": "hub-restart-cancelled",
            "message": "Hub restart cancelled. No command was sent.",
        }

    async def _restart(self) -> dict[str, Any]:
        arguments = {"confirm": True}
        try:
            result = await self.application.mcp.call_tool("hub_reboot", arguments)
        except Exception as exc:
            return {
                "success": False,
                "route": "mcp-hub-restart",
                "intent": "hub-restart-unconfirmed",
                "message": (
                    "The restart request was sent, but HomeBrain could not confirm whether the hub "
                    "accepted it. Do not retry immediately; first check whether the hub goes offline."
                ),
                "tools_used": [
                    {"name": "hub_reboot", "success": False, "error": str(exc)}
                ],
                "technical": safe_debug({"error": str(exc) or type(exc).__name__}),
            }

        if result.is_error:
            error = str(result.text or result.data or "Hubitat rejected the restart request.")
            return {
                "success": False,
                "route": "mcp-hub-restart",
                "intent": "hub-restart-failed",
                "message": f"The hub was not restarted: {error}",
                "tools_used": [
                    {"name": "hub_reboot", "success": False, "error": error[:700]}
                ],
            }

        return {
            "success": True,
            "route": "mcp-hub-restart",
            "intent": "hub-restart-requested",
            "message": (
                "The Hubitat hub accepted the restart request. It should be unavailable for about "
                "1–3 minutes while it restarts."
            ),
            "tools_used": [{"name": "hub_reboot", "success": True}],
            "technical": safe_debug({"tool": "hub_reboot", "arguments": arguments}),
        }


def install_hub_restart_workflow(
    application: Any,
    *,
    ttl_seconds: float = 120.0,
) -> HubRestartWorkflow:
    original_ask: AskHandler = application.ask
    workflow = HubRestartWorkflow(application, ttl_seconds=ttl_seconds)

    async def restart_ask(request: Any) -> dict[str, Any]:
        return await workflow.answer(request, original_ask)

    application.ask = restart_ask
    return workflow


__all__ = ["HubRestartWorkflow", "install_hub_restart_workflow"]

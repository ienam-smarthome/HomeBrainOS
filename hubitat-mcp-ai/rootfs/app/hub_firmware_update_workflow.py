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
_UPDATE = re.compile(
    r"^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?"
    r"(?:(?:check\s+(?:for\s+)?)?(?:and\s+)?(?:install|apply|start|run|do)?\s*)?"
    r"(?:update|upgrade)\s+"
    r"(?:(?:the|my)\s+)?(?:(?:hub|hubitat)(?:\s+hub)?\s+)?"
    r"(?:software|firmware|platform)[?.!]*$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class PendingFirmwareUpdate:
    expires_at: float


class HubFirmwareUpdateWorkflow:
    """Explicit, session-scoped confirmation for Hubitat firmware updates."""

    def __init__(self, application: Any, *, ttl_seconds: float = 120.0) -> None:
        self.application = application
        self.ttl_seconds = max(30.0, min(300.0, float(ttl_seconds)))
        self._pending: dict[str, PendingFirmwareUpdate] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def session_id(request: Any) -> str:
        value = str(getattr(request, "session_id", "") or "default").strip()
        return value[:160] or "default"

    @staticmethod
    def matches(query: str) -> bool:
        return bool(_UPDATE.match(str(query or "").strip()))

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
                # Consume first: a timeout or duplicate browser submission must
                # never issue this destructive operation twice.
                await self._pop(session_id)
                return await self._update()

        if not self.matches(query):
            return await fallback(request)

        await self._put(session_id)
        return self._confirmation()

    async def _put(self, session_id: str) -> None:
        async with self._lock:
            self._purge_locked()
            self._pending[session_id] = PendingFirmwareUpdate(
                expires_at=time.monotonic() + self.ttl_seconds
            )

    async def _get(self, session_id: str) -> PendingFirmwareUpdate | None:
        async with self._lock:
            self._purge_locked()
            return self._pending.get(session_id)

    async def _pop(self, session_id: str) -> PendingFirmwareUpdate | None:
        async with self._lock:
            self._purge_locked()
            return self._pending.pop(session_id, None)

    def _purge_locked(self) -> None:
        now = time.monotonic()
        for key in [key for key, item in self._pending.items() if item.expires_at <= now]:
            self._pending.pop(key, None)

    def _confirmation(self) -> dict[str, Any]:
        display = display_payload(
            "hub-firmware-update-confirmation",
            "Update the Hubitat hub software now?",
            subtitle="The hub will restart and devices will be temporarily unavailable.",
            metrics=[
                {"label": "Operation", "value": "Firmware update", "icon": "⬆️"},
                {"label": "Restart", "value": "Required", "icon": "🔄"},
            ],
            note=(
                "Choose Yes - update hub or No - cancel below. You can also reply Yes or No. "
                "Confirmation expires after two minutes."
            ),
        )
        display["actions"] = [
            {
                "label": "Yes - update hub",
                "query": "Yes",
                "tone": "danger",
                "icon": "⬆️",
            },
            {
                "label": "No - cancel",
                "query": "No",
                "tone": "secondary",
                "icon": "✖️",
            },
        ]
        return {
            "success": False,
            "route": "mcp-hub-firmware-update-confirmation",
            "intent": "hub-firmware-update-confirmation-required",
            "confirmation_required": True,
            "message": (
                "Do you want to update the Hubitat hub software now? The hub will restart and "
                "devices may be temporarily unavailable. Select Yes to update, or No to cancel."
            ),
            "display": display,
        }

    @staticmethod
    def _cancelled() -> dict[str, Any]:
        return {
            "success": True,
            "route": "mcp-hub-firmware-update-confirmation",
            "intent": "hub-firmware-update-cancelled",
            "message": "Hub software update cancelled. No command was sent.",
        }

    async def _update(self) -> dict[str, Any]:
        arguments = {"confirm": True}
        try:
            result = await self.application.mcp.call_tool(
                "hub_update_firmware", arguments
            )
        except Exception as exc:
            return {
                "success": False,
                "route": "mcp-hub-firmware-update",
                "intent": "hub-firmware-update-unconfirmed",
                "message": (
                    "The update request was sent, but HomeBrain could not confirm whether the hub "
                    "accepted it. Do not retry immediately; first check the Hubitat admin page."
                ),
                "tools_used": [
                    {
                        "name": "hub_update_firmware",
                        "success": False,
                        "error": str(exc),
                    }
                ],
                "technical": safe_debug({"error": str(exc) or type(exc).__name__}),
            }

        if result.is_error:
            error = str(result.text or result.data or "Hubitat rejected the update request.")
            return {
                "success": False,
                "route": "mcp-hub-firmware-update",
                "intent": "hub-firmware-update-failed",
                "message": f"The hub software was not updated: {error}",
                "tools_used": [
                    {
                        "name": "hub_update_firmware",
                        "success": False,
                        "error": error[:700],
                    }
                ],
            }

        return {
            "success": True,
            "route": "mcp-hub-firmware-update",
            "intent": "hub-firmware-update-requested",
            "message": (
                "The Hubitat hub accepted the software update request. It may be unavailable "
                "while the update is installed and the hub restarts."
            ),
            "tools_used": [{"name": "hub_update_firmware", "success": True}],
            "technical": safe_debug(
                {"tool": "hub_update_firmware", "arguments": arguments}
            ),
        }


def install_hub_firmware_update_workflow(
    application: Any,
    *,
    ttl_seconds: float = 120.0,
) -> HubFirmwareUpdateWorkflow:
    original_ask: AskHandler = application.ask
    workflow = HubFirmwareUpdateWorkflow(application, ttl_seconds=ttl_seconds)

    async def firmware_update_ask(request: Any) -> dict[str, Any]:
        return await workflow.answer(request, original_ask)

    application.ask = firmware_update_ask
    return workflow


__all__ = ["HubFirmwareUpdateWorkflow", "install_hub_firmware_update_workflow"]

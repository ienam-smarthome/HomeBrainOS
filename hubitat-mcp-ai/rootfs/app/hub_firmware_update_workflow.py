from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from presenter import display_payload, first_mapping, first_value, safe_debug
from system_presenter_v2 import present_hub_info_v2


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
    current_version: str | None = None
    available_version: str | None = None


class HubFirmwareUpdateWorkflow:
    """Explicit, session-scoped confirmation for Hubitat firmware updates."""

    def __init__(
        self,
        application: Any,
        backup_service: Any,
        *,
        ttl_seconds: float = 120.0,
    ) -> None:
        self.application = application
        self.backup_service = backup_service
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

        status = await self._read_update_status()
        if status["available"] is not True:
            return self._status_without_confirmation(status)

        await self._put(session_id, status)
        return self._confirmation(status)

    async def _put(self, session_id: str, status: dict[str, Any]) -> None:
        async with self._lock:
            self._purge_locked()
            self._pending[session_id] = PendingFirmwareUpdate(
                expires_at=time.monotonic() + self.ttl_seconds,
                current_version=status.get("current_version"),
                available_version=status.get("available_version"),
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

    def _confirmation(self, status: dict[str, Any]) -> dict[str, Any]:
        current = str(status.get("current_version") or "Unknown")
        available = str(status.get("available_version") or "Available")
        channel = str(status.get("channel") or "").strip()
        available_label = f"{available} ({channel})" if channel else available
        display = display_payload(
            "hub-firmware-update-confirmation",
            "Update the Hubitat hub software now?",
            subtitle="HomeBrain will verify or create a backup first, then the hub will restart.",
            metrics=[
                {"label": "Installed", "value": current, "icon": "🧩"},
                {"label": "Available", "value": available_label, "icon": "⬆️"},
                {"label": "Restart", "value": "Required", "icon": "🔄"},
            ],
            note=(
                "Choose Yes - update hub or No - cancel below. You can also reply Yes or No. "
                "Yes authorizes the required backup and the firmware update. Confirmation "
                "expires after two minutes."
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
                "Do you want to update the Hubitat hub software now? HomeBrain will first verify "
                "or create the required recent backup, then start the update. The hub will restart "
                "and devices may be temporarily unavailable. Select Yes to continue, or No to "
                "cancel."
            ),
            "display": display,
            "tools_used": [{"name": "hub_get_info", "success": True}],
            "technical": safe_debug({"platform_update": status.get("raw")}),
        }

    @staticmethod
    def _status_without_confirmation(status: dict[str, Any]) -> dict[str, Any]:
        current = str(status.get("current_version") or "Unknown")
        available = status.get("available")
        error = str(status.get("error") or "").strip()
        if available is False:
            title = "Hub software is up to date"
            message = f"The Hubitat hub is already running the latest software ({current})."
            intent = "hub-firmware-up-to-date"
            success = True
        else:
            title = "Could not verify hub software"
            message = (
                "HomeBrain could not reliably read the installed and available Hubitat software "
                "versions, so no update confirmation was created."
            )
            if error:
                message += f" {error}"
            intent = "hub-firmware-status-unavailable"
            success = False
        return {
            "success": success,
            "route": "mcp-hub-firmware-status",
            "intent": intent,
            "message": message,
            "display": display_payload(
                "hub-firmware-status",
                title,
                metrics=[
                    {"label": "Installed", "value": current, "icon": "🧩"},
                    {
                        "label": "Update",
                        "value": "Up to date" if available is False else "Unknown",
                        "icon": "✅" if available is False else "❓",
                    },
                ],
                note="No firmware update command was sent.",
            ),
            "tools_used": [
                {
                    "name": "hub_get_info",
                    "success": not bool(error),
                    **({"error": error[:700]} if error else {}),
                }
            ],
            "technical": safe_debug({"platform_update": status.get("raw"), "error": error}),
        }

    async def _read_update_status(self) -> dict[str, Any]:
        arguments = {"includeAppUpdate": False, "includeHealthAlerts": True}
        try:
            result = await self.application.mcp.call_tool("hub_get_info", arguments)
        except Exception as exc:
            return {
                "available": None,
                "current_version": None,
                "available_version": None,
                "error": str(exc).strip() or type(exc).__name__,
                "raw": None,
            }
        if result.is_error:
            return {
                "available": None,
                "current_version": None,
                "available_version": None,
                "error": str(result.text or "hub_get_info failed"),
                "raw": result.data,
            }

        data = first_mapping(result.data)
        _message, hub_display = present_hub_info_v2(data)
        platform = hub_display.get("platform_update") or {}
        raw_platform = data.get("platformUpdate")
        raw_platform = raw_platform if isinstance(raw_platform, dict) else {}
        current = (
            platform.get("current")
            or first_value(data, "firmwareVersion", "currentVersion")
        )
        available_version = platform.get("available_version")
        channel = first_value(raw_platform, "channel", "releaseChannel", "track")
        note = str(first_value(raw_platform, "note", "message") or "")
        if not channel and "beta" in note.lower():
            channel = "beta"
        return {
            "available": platform.get("available"),
            "current_version": str(current) if current not in (None, "") else None,
            "available_version": (
                str(available_version)
                if available_version not in (None, "")
                else None
            ),
            "channel": str(channel) if channel not in (None, "") else None,
            "error": None,
            "raw": raw_platform,
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
        backup_ok, backup_details = await self._ensure_recent_backup()
        if not backup_ok:
            error = str(
                backup_details.get("error")
                or "A verified backup from the last 24 hours is required."
            ).strip()
            return {
                "success": False,
                "route": "mcp-hub-firmware-update",
                "intent": "hub-firmware-update-backup-failed",
                "message": (
                    "The hub software update was not started because HomeBrain could not "
                    f"complete and verify the required backup: {error}"
                ),
                "tools_used": [
                    {
                        "name": "hub_create_backup",
                        "success": False,
                        "error": error[:700],
                    }
                ],
                "technical": safe_debug({"backup": backup_details}),
            }

        arguments = {"confirm": True}
        try:
            result = await self.application.mcp.call_tool(
                "hub_update_firmware", arguments
            )
        except Exception as exc:
            error = str(exc).strip() or type(exc).__name__
            uncertain = isinstance(exc, (TimeoutError, asyncio.TimeoutError))
            return {
                "success": False,
                "route": "mcp-hub-firmware-update",
                "intent": (
                    "hub-firmware-update-unconfirmed"
                    if uncertain
                    else "hub-firmware-update-failed"
                ),
                "message": (
                    (
                        "The update request may have been sent, but HomeBrain could not confirm "
                        "whether the hub accepted it. Do not retry immediately; first check the "
                        "Hubitat admin page."
                    )
                    if uncertain
                    else f"The hub software update was not started: {error}"
                ),
                "tools_used": [
                    {
                        "name": "hub_update_firmware",
                        "success": False,
                        "error": error,
                    }
                ],
                "technical": safe_debug(
                    {
                        "error": error,
                        "exception_type": type(exc).__name__,
                        "backup": backup_details,
                    }
                ),
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
                {
                    "tool": "hub_update_firmware",
                    "arguments": arguments,
                    "backup": backup_details,
                }
            ),
        }

    async def _ensure_recent_backup(self) -> tuple[bool, dict[str, Any]]:
        try:
            key = await self.backup_service._read_best_practice_key()
            ok, details = await self.backup_service._ensure_backup(key)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return False, {
                "error": str(exc).strip() or "Unexpected MCP backup workflow error",
                "exception_type": type(exc).__name__,
            }
        normalized = details if isinstance(details, dict) else {"result": details}
        normalized["best_practice_key_found"] = bool(key)
        return bool(ok), normalized


def install_hub_firmware_update_workflow(
    application: Any,
    backup_service: Any,
    *,
    ttl_seconds: float = 120.0,
) -> HubFirmwareUpdateWorkflow:
    original_ask: AskHandler = application.ask
    workflow = HubFirmwareUpdateWorkflow(
        application,
        backup_service,
        ttl_seconds=ttl_seconds,
    )

    async def firmware_update_ask(request: Any) -> dict[str, Any]:
        return await workflow.answer(request, original_ask)

    application.ask = firmware_update_ask
    return workflow


__all__ = ["HubFirmwareUpdateWorkflow", "install_hub_firmware_update_workflow"]

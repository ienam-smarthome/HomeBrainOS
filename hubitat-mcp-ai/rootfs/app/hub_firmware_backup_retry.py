from __future__ import annotations

import asyncio
import json
from types import MethodType
from typing import Any

from presenter import safe_debug


_BACKUP_REQUIRED = "backup required"


def _technical_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _verified_recent_backup(answer: dict[str, Any]) -> bool:
    technical = _technical_mapping(answer.get("technical"))
    backup = technical.get("backup")
    if not isinstance(backup, dict):
        return False
    if backup.get("recent") is not True:
        return False
    return bool(backup.get("verified_by") or backup.get("post_create_checks"))


def _is_backup_guard_lag(answer: dict[str, Any]) -> bool:
    text = " ".join(
        str(answer.get(key) or "")
        for key in ("message", "technical")
    ).lower()
    return _BACKUP_REQUIRED in text and _verified_recent_backup(answer)


def install_firmware_backup_settle_retry(
    workflow: Any,
    *,
    settle_seconds: float = 4.0,
) -> Any:
    """Retry firmware once when MCP has not indexed a verified fresh backup yet."""

    original_update = workflow._update
    delay = max(1.0, min(15.0, float(settle_seconds)))

    async def update_with_backup_settle_retry(self: Any) -> dict[str, Any]:
        first = await original_update()
        if first.get("success") is True or not _is_backup_guard_lag(first):
            return first

        await asyncio.sleep(delay)
        arguments = {"confirm": True}
        try:
            retry_result = await self.application.mcp.call_tool(
                "hub_update_firmware",
                arguments,
            )
        except Exception as exc:
            error = str(exc).strip() or type(exc).__name__
            return {
                "success": False,
                "route": "mcp-hub-firmware-update",
                "intent": "hub-firmware-update-backup-index-lag",
                "message": (
                    "A fresh hub backup was created and verified, but the MCP firmware guard "
                    "still did not recognise it after one safe retry. The update was not started. "
                    "Wait about one minute, then request the software update again."
                ),
                "tools_used": [
                    {
                        "name": "hub_update_firmware",
                        "success": False,
                        "error": error[:700],
                    }
                ],
                "technical": safe_debug(
                    {
                        "retry_reason": "verified-backup-index-lag",
                        "settle_seconds": delay,
                        "retry_error": error,
                        "retry_exception_type": type(exc).__name__,
                        "first_attempt": first,
                    }
                ),
            }

        if getattr(retry_result, "is_error", False):
            error = str(
                getattr(retry_result, "text", "")
                or getattr(retry_result, "data", "")
                or "Hubitat rejected the update request."
            )
            return {
                "success": False,
                "route": "mcp-hub-firmware-update",
                "intent": "hub-firmware-update-backup-index-lag",
                "message": (
                    "A fresh hub backup was created and verified, but the MCP firmware guard "
                    "still did not recognise it after one safe retry. The update was not started. "
                    "Wait about one minute, then request the software update again."
                ),
                "tools_used": [
                    {
                        "name": "hub_update_firmware",
                        "success": False,
                        "error": error[:700],
                    }
                ],
                "technical": safe_debug(
                    {
                        "retry_reason": "verified-backup-index-lag",
                        "settle_seconds": delay,
                        "retry_error": error,
                        "first_attempt": first,
                    }
                ),
            }

        return {
            "success": True,
            "route": "mcp-hub-firmware-update",
            "intent": "hub-firmware-update-requested-after-backup-settle",
            "message": (
                "The fresh backup was verified and the Hubitat hub accepted the software update "
                "after its backup index refreshed. The hub may be unavailable while it installs "
                "the update and restarts."
            ),
            "tools_used": [
                {
                    "name": "hub_update_firmware",
                    "success": True,
                    "retry": True,
                }
            ],
            "technical": safe_debug(
                {
                    "tool": "hub_update_firmware",
                    "arguments": arguments,
                    "retry_reason": "verified-backup-index-lag",
                    "settle_seconds": delay,
                    "first_attempt": first,
                }
            ),
        }

    workflow._update = MethodType(update_with_backup_settle_retry, workflow)
    return workflow


__all__ = [
    "install_firmware_backup_settle_retry",
]

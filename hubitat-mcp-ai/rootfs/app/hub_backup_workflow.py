from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from automation_rule_workflow_native_rm import _nested_value
from backup_intent import is_explicit_backup_request
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def install_explicit_hub_backup_workflow(application: Any, backup_service: Any) -> None:
    """Keep explicit backup creation on one guarded, idempotent Python workflow."""

    original_ask: AskHandler = application.ask

    async def ask_with_explicit_backup(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if not is_explicit_backup_request(query):
            return await original_ask(request)

        key: str | None = None
        try:
            key = await backup_service._read_best_practice_key()
            ok, details = await backup_service._ensure_backup(key, force=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ok = False
            details = {
                "created": False,
                "pending": False,
                "exception_type": type(exc).__name__,
                "error": str(exc).strip() or "Unexpected MCP backup workflow error",
            }
        filename = str(_nested_value(details.get("result"), "fileName") or "").strip()
        pending = bool(details.get("pending") or details.get("started")) and not ok

        if ok:
            message = "Hub backup completed successfully."
            if filename:
                message = f"Hub backup completed successfully: {filename}."
            title = "Backup complete"
            intent = "hub-backup-complete"
        elif pending:
            message = (
                "The hub accepted the backup request, but it is still running or its response "
                "timed out. HomeBrain did not start a second backup. Wait about 30 seconds, "
                "then ask to perform a backup again; HomeBrain will verify the pending result first."
            )
            title = "Backup still running"
            intent = "hub-backup-pending"
        else:
            error = str(details.get("error") or "The MCP backup request failed.").strip()
            message = f"Hub backup was not completed: {error}"
            title = "Backup failed"
            intent = "hub-backup-failed"

        return {
            "success": ok,
            "route": "mcp-backup",
            "intent": intent,
            "message": message,
            "model": None,
            "display": display_payload(
                "hub-backup",
                title,
                subtitle=filename or ("No duplicate request was sent" if pending else "Hubitat MCP"),
                metrics=[
                    {
                        "label": "Status",
                        "value": "Complete" if ok else ("Pending" if pending else "Failed"),
                        "icon": "💾",
                    }
                ],
                note="Backup creation is handled deterministically with MCP acknowledgement and idempotency safeguards.",
            ),
            "technical": safe_debug(
                {
                    "backup": details,
                    "best_practice_key_found": bool(key),
                    "duplicate_write_prevented": pending,
                }
            ),
            "version": application.VERSION,
        }

    application.ask = ask_with_explicit_backup


__all__ = ["install_explicit_hub_backup_workflow"]

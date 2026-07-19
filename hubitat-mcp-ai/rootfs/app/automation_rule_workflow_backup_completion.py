from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from automation_rule_workflow import _session_id
from automation_rule_workflow_confirmed_backup import (
    ConfirmedBackupWashingRuleMachineWorkflow,
)


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


class BackupCompletionRuleMachineWorkflow(ConfirmedBackupWashingRuleMachineWorkflow):
    """Treat long-running backup creation as asynchronous and verify completion.

    Hubitat can take longer than the normal 25-second MCP request timeout to create
    a whole-hub backup. In that case the HTTP client raises a timeout with an empty
    message even though the hub may continue creating the backup. Never proceed on
    an unverified response, but poll the local backup list and avoid launching a
    duplicate backup while the first request may still be running.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._backup_pending_until = 0.0

    async def _poll_recent_backup(
        self,
        *,
        delays: tuple[float, ...],
    ) -> tuple[bool, list[dict[str, Any]]]:
        checks: list[dict[str, Any]] = []
        for delay in delays:
            if delay > 0:
                await asyncio.sleep(delay)
            ok, details = await self._recent_listed_backup()
            checks.append(details)
            if ok:
                return True, checks
        return False, checks

    async def _ensure_backup(self, key: str | None) -> tuple[bool, dict[str, Any]]:
        now = time.monotonic()

        # A previous create request may still be running on the hub. Recheck once
        # rather than launching another expensive backup immediately.
        if now < self._backup_pending_until:
            listed_ok, listed = await self._recent_listed_backup()
            if listed_ok:
                self._backup_pending_until = 0.0
                return True, {
                    "created": True,
                    "recent": True,
                    "verified_by": "hub_list_backups_after_pending_create",
                    "listed": listed,
                    "best_practice_key_found": bool(key),
                }
            return False, {
                "created": False,
                "recent": False,
                "started": True,
                "pending": True,
                "listed_backup_check": listed,
                "best_practice_key_found": bool(key),
                "error": (
                    "The confirmed backup request may still be running on Hubitat. "
                    "Wait about 30 seconds, then press Create this rule again. "
                    "HomeBrain will verify the completed backup before writing the rule."
                ),
            }

        ok, details = await super()._ensure_backup(key)
        if ok:
            self._backup_pending_until = 0.0
            return True, details

        attempted_create = bool(details.get("confirm_sent"))
        error = str(details.get("error") or "").strip()
        started = bool(details.get("started"))

        # Empty exception text is the common httpx timeout signature. Also poll
        # when the server explicitly reports an in-progress backup.
        ambiguous_or_running = attempted_create and (not error or started)
        if not ambiguous_or_running:
            return False, details

        self._backup_pending_until = time.monotonic() + 120.0
        verified, checks = await self._poll_recent_backup(delays=(2.0, 4.0, 6.0))
        details["post_create_checks"] = checks
        details["pending"] = not verified
        details["timeout_or_async_response"] = True

        if verified:
            self._backup_pending_until = 0.0
            details.update(
                {
                    "created": True,
                    "recent": True,
                    "verified_by": "hub_list_backups_after_create",
                    "error": None,
                }
            )
            return True, details

        details["created"] = False
        details["recent"] = False
        details["started"] = True
        details["error"] = (
            "The confirmed backup call did not return a completion result before the "
            "25-second MCP timeout. Hubitat may still be creating it. Wait about 30 "
            "seconds and press Create this rule again; HomeBrain will check for the "
            "new backup and will not write the rule until it is verified."
        )
        return False, details


def install_backup_completion_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> BackupCompletionRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = BackupCompletionRuleMachineWorkflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )

    async def ask_with_rule_workflow(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        command = service.command(query)
        if command:
            answer = await service.handle(request, command)
            answer.setdefault("version", application.VERSION)
            return answer
        answer = await original_ask(request)
        await service.remember_answer(_session_id(request), answer)
        return answer

    application.ask = ask_with_rule_workflow
    application.automation_rule_workflow = service
    return service


__all__ = [
    "BackupCompletionRuleMachineWorkflow",
    "install_backup_completion_rule_machine_workflow",
]

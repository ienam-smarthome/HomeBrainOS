from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _session_id
from automation_rule_workflow_native_rm import (
    _BACKUP_NAMES,
    _GUIDE_NAMES,
    _best_practice_key,
    _nested_value,
)
from automation_rule_workflow_washing_final import FinalWashingRuleMachineWorkflow


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def _acknowledgment_key(value: Any) -> str | None:
    """Read the MCP best-practice key from current and older guide wording."""

    key = _best_practice_key(value)
    if key:
        return key

    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value or "")

    patterns = (
        r"acknowledg(?:e)?ment\s+key\s*(?:is|=|:)\s*[\s`*\"']*([A-Za-z0-9._-]{4,128})",
        r"acknowledg(?:e)?ment\s+token\s*(?:is|=|:)\s*[\s`*\"']*([A-Za-z0-9._-]{4,128})",
        r"bestPracticeKey\s*[=:]\s*[\s`*\"']*([A-Za-z0-9._-]{4,128})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


class ConfirmedBackupWashingRuleMachineWorkflow(FinalWashingRuleMachineWorkflow):
    """Final workflow using the MCP backup tool's actual confirmation contract.

    Hubitat backup creation can exceed the normal 25-second MCP request timeout.
    A blank timeout exception does not prove the backup failed, so the workflow
    polls the local backup list and prevents duplicate backup creation attempts
    while the first confirmed request may still be running.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._backup_pending_until = 0.0

    async def _read_best_practice_key(self) -> str | None:
        now = time.monotonic()
        if self._best_practice_cache and now - self._best_practice_cache[0] < 600:
            return self._best_practice_cache[1]

        tool = await self._find_tool(_GUIDE_NAMES, refresh=True)
        if tool is None:
            self._best_practice_cache = (now, None)
            return None

        section_field = self._argument_name(tool, "section", "section")
        key: str | None = None
        # Current servers publish the mandatory key in best_practice_reference.
        # Some builds additionally expose it in the tool-specific backup guide.
        for section in ("best_practice_reference", "backup"):
            try:
                result = await self._call_rule_tool(tool, {section_field: section})
            except Exception:
                continue
            if result.is_error:
                continue
            key = _acknowledgment_key(result.data) or _acknowledgment_key(result.text)
            if key:
                break

        self._best_practice_cache = (now, key)
        return key

    async def _poll_recent_backup(
        self,
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
        # A previous confirmed request may still be running on the hub. Recheck
        # instead of starting another whole-hub backup immediately.
        if time.monotonic() < self._backup_pending_until:
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

        listed_ok, listed = await self._recent_listed_backup()
        if listed_ok:
            return True, {
                "created": False,
                "recent": True,
                "verified_by": "hub_list_backups",
                "listed": listed,
                "best_practice_key_found": bool(key),
            }

        details: dict[str, Any] = {
            "created": False,
            "recent": False,
            "listed_backup_check": listed,
            "best_practice_key_found": bool(key),
        }
        tool = await self._find_tool(_BACKUP_NAMES, refresh=True)
        if tool is None:
            details["error"] = (
                "hub_create_backup is not present in MCP tools/list. In Apps > MCP Rule Server > "
                "Settings > Advanced: Per-tool Overrides, remove hub_create_backup from Disabled "
                "tools or reset the overrides, save, then refresh MCP tools."
            )
            return False, details

        args: dict[str, Any] = {
            self._argument_name(tool, "confirm", "confirm"): True,
        }
        args = self._add_best_practice_key(tool, args, key)
        details.update(
            {
                "tool": tool.name,
                "gateway": tool.gateway,
                "confirm_sent": True,
                "arguments": {
                    name: ("<present>" if "key" in name.lower() else value)
                    for name, value in args.items()
                },
            }
        )

        result = None
        try:
            result = await self._call_rule_tool(tool, args)
        except Exception as exc:
            # httpx timeout exceptions frequently stringify to an empty string.
            details["exception_type"] = type(exc).__name__
            details["error"] = str(exc).strip()

        if result is not None:
            details["result"] = result.data
            details["result_is_error"] = bool(result.is_error)
            if result.is_error or _nested_value(result.data, "success") is False:
                details["error"] = result.text or str(
                    _nested_value(result.data, "error") or "Backup failed"
                )
            elif str(_nested_value(result.data, "status") or "").lower() == "in_progress":
                details["error"] = (
                    "The hub backup started successfully and is still in progress."
                )
                details["started"] = True
            else:
                details["created"] = True
                details["recent"] = True
                self._backup_pending_until = 0.0
                return True, details

        error = str(details.get("error") or "").strip()
        timeout_type = str(details.get("exception_type") or "").lower()
        ambiguous_or_running = bool(
            details.get("started")
            or not error
            or "timeout" in timeout_type
            or "timed out" in error.lower()
        )
        if not ambiguous_or_running:
            return False, details

        # The confirmed call reached the server but did not provide a final result.
        # Poll for the backup that may still be completing in the background.
        self._backup_pending_until = time.monotonic() + 120.0
        verified, checks = await self._poll_recent_backup((2.0, 4.0, 6.0))
        details["post_create_checks"] = checks
        details["timeout_or_async_response"] = True
        details["pending"] = not verified

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

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain checks for a recent local backup, sends a confirmed backup request "
                    "when needed, and polls for completion if Hubitat takes longer than the MCP timeout."
                )
        return answer


def install_confirmed_backup_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> ConfirmedBackupWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = ConfirmedBackupWashingRuleMachineWorkflow(
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
    "ConfirmedBackupWashingRuleMachineWorkflow",
    "install_confirmed_backup_rule_machine_workflow",
]

from __future__ import annotations

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
    """Final workflow using the MCP backup tool's actual confirmation contract."""

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

    async def _ensure_backup(self, key: str | None) -> tuple[bool, dict[str, Any]]:
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

        try:
            result = await self._call_rule_tool(tool, args)
        except Exception as exc:
            details["error"] = str(exc)
            return False, details

        details["result"] = result.data
        if result.is_error or _nested_value(result.data, "success") is False:
            details["error"] = result.text or str(
                _nested_value(result.data, "error") or "Backup failed"
            )
            return False, details
        if str(_nested_value(result.data, "status") or "").lower() == "in_progress":
            details["error"] = (
                "The hub backup started successfully and is still in progress. Wait for it to "
                "finish, then press Create this rule again."
            )
            details["started"] = True
            return False, details

        details["created"] = True
        details["recent"] = True
        return True, details

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain first checks for a recent local backup. When it must create one, it "
                    "reads the MCP acknowledgment key and sends hub_create_backup with confirm=true."
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

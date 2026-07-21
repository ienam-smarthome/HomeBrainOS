from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _session_id
from automation_rule_workflow_native_rm import (
    _BACKUP_NAMES,
    _GUIDE_NAMES,
    _best_practice_key,
    _nested_value,
)
from automation_rule_workflow_washing_final import (
    FinalWashingRuleMachineWorkflow,
    _BACKUP_MAX_AGE_MS,
    _backup_timestamp_ms,
    _looks_like_local_hub_backup,
    _mapping_rows,
)


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


def _plain_backup_rows(value: Any) -> list[dict[str, Any]]:
    """Recover backup filenames when a server returns strings instead of objects."""

    rows: list[dict[str, Any]] = []
    if isinstance(value, str):
        text = value.strip()
        if text.lower().endswith((".lzf", ".zip")):
            rows.append({"fileName": text, "location": "local"})
        return rows
    if isinstance(value, list):
        for item in value:
            rows.extend(_plain_backup_rows(item))
        return rows
    if isinstance(value, dict):
        for item in value.values():
            rows.extend(_plain_backup_rows(item))
    return rows


class ConfirmedBackupWashingRuleMachineWorkflow(FinalWashingRuleMachineWorkflow):
    """Backup-safe Rule Machine workflow with strict gateway verification.

    Hubitat backup creation can exceed the normal 25-second MCP request timeout.
    A blank timeout exception does not prove the backup failed, so the workflow
    polls the local backup list and prevents duplicate backup creation attempts
    while the first confirmed request may still be running.

    Backup listing deliberately bypasses generic catalogue probing. A source-code
    gateway can mention ``hub_list_backups`` in app text and must never be accepted
    as the owning gateway. Only the direct core tool or ``hub_manage_backup`` is
    permitted for backup verification.
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

    async def _recent_listed_backup(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {
            "checked": False,
            "recent": False,
            "source": "hub_list_backups",
            "strict_gateway": True,
        }
        try:
            tools = await self.client.list_tools(refresh=True)
        except Exception as exc:
            details["error"] = f"Could not refresh MCP tools: {type(exc).__name__}: {str(exc).strip()}"
            return False, details

        visible = {str(getattr(tool, "name", "") or ""): tool for tool in tools}
        list_args: dict[str, Any] = {"scope": "hub_local", "limit": 10}
        gateway: str | None = None
        request_name: str
        request_args: dict[str, Any]

        if "hub_list_backups" in visible:
            request_name = "hub_list_backups"
            schema = dict(getattr(visible[request_name], "input_schema", {}) or {})
            properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            if properties:
                list_args = {key: value for key, value in list_args.items() if key in properties}
            request_args = list_args
        elif "hub_manage_backup" in visible:
            request_name = "hub_manage_backup"
            gateway = request_name
            request_args = {"tool": "hub_list_backups", "args": list_args}
        else:
            details["error"] = (
                "Neither the direct hub_list_backups tool nor the hub_manage_backup gateway "
                "was advertised. HomeBrain will not use an unrelated gateway for backup verification."
            )
            details["visible_backup_tools"] = sorted(
                name for name in visible if "backup" in name.lower()
            )
            return False, details

        details.update(
            {
                "checked": True,
                "tool": "hub_list_backups",
                "gateway": gateway,
                "request_tool": request_name,
                "arguments": list_args,
            }
        )
        try:
            result = await self.client.call_tool(request_name, request_args)
        except Exception as exc:
            details["exception_type"] = type(exc).__name__
            details["error"] = str(exc).strip() or f"{type(exc).__name__} while listing backups"
            return False, details

        details["result_is_error"] = bool(result.is_error)
        details["response_type"] = type(result.data).__name__
        if result.is_error:
            details["error"] = result.text or "hub_list_backups failed"
            return False, details

        now_ms = int(time.time() * 1000)
        raw_rows = _mapping_rows(result.data) + _plain_backup_rows(result.data)
        unique_rows: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(raw_rows):
            if not isinstance(item, dict) or not _looks_like_local_hub_backup(item):
                continue
            key = str(
                item.get("id")
                or item.get("fileName")
                or item.get("filename")
                or item.get("name")
                or index
            )
            existing = unique_rows.get(key, {})
            unique_rows[key] = {**existing, **item}

        candidates: list[dict[str, Any]] = []
        unparseable_names: list[str] = []
        for item in unique_rows.values():
            timestamp_ms = _backup_timestamp_ms(item, now_ms)
            name = item.get("fileName") or item.get("filename") or item.get("name") or item.get("id")
            if timestamp_ms is None:
                if name:
                    unparseable_names.append(str(name))
                continue
            age_ms = now_ms - timestamp_ms
            if age_ms < 0 or age_ms > 365 * 24 * 60 * 60 * 1000:
                continue
            candidates.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "age_ms": age_ms,
                    "name": name,
                }
            )

        candidates.sort(key=lambda item: item["timestamp_ms"], reverse=True)
        details["row_count"] = len(unique_rows)
        details["candidate_count"] = len(candidates)
        if unparseable_names:
            details["unparseable_names"] = unparseable_names[:5]
        if candidates:
            details["newest"] = candidates[0]
            if candidates[0]["age_ms"] < _BACKUP_MAX_AGE_MS:
                details["recent"] = True
                return True, details

        details["error"] = "No verifiable local hub backup from the last 24 hours was listed"
        return False, details

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

    async def _ensure_backup(
        self,
        key: str | None,
        *,
        force: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
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

        listed: dict[str, Any] = {"checked": False, "skipped_for_explicit_create": force}
        if not force:
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
        properties = tool.schema.get("properties") if isinstance(tool.schema, dict) else None
        supports_op_token = not properties or any(
            re.sub(r"[^a-z0-9]", "", str(name).lower()) == "optoken"
            for name in properties
        )
        if supports_op_token:
            args[self._argument_name(tool, "optoken", "opToken")] = (
                "homebrain-backup-" + uuid.uuid4().hex[:20]
            )
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
                details["error"] = "The hub backup started successfully and is still in progress."
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
                    "HomeBrain verifies backups only through hub_list_backups or the "
                    "hub_manage_backup gateway, and polls after a long-running backup request."
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

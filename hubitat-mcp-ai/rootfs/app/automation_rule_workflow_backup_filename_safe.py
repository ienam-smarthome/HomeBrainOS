from __future__ import annotations

import re
import time
from datetime import date, datetime
from typing import Any, Awaitable, Callable

from automation_rule_workflow import _session_id
from automation_rule_workflow_backup_confirmed import (
    ConfirmedBackupWashingRuleMachineWorkflow,
    _plain_backup_rows,
)
from automation_rule_workflow_washing_final import (
    _BACKUP_MAX_AGE_MS,
    _backup_timestamp_ms,
    _looks_like_local_hub_backup,
    _mapping_rows,
)


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_HUBITAT_BACKUP_DATE = re.compile(
    r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)"
)


def _hubitat_backup_filename_date(value: Any) -> date | None:
    """Extract the calendar date from Hubitat whole-hub backup filenames.

    Current Hubitat local backups can be named either
    ``2026-07-19~2.5.1.131.lzf`` or
    ``Hub_C8_Pro_2026-07-19~2.5.1.131~manual.lzf``.
    """

    text = str(value or "").strip()
    if not text.lower().endswith((".lzf", ".zip")):
        return None
    match = _HUBITAT_BACKUP_DATE.search(text)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def _row_name(item: dict[str, Any]) -> str | None:
    value = (
        item.get("fileName")
        or item.get("filename")
        or item.get("file_name")
        or item.get("name")
        or item.get("id")
    )
    return str(value) if value not in (None, "") else None


class FilenameSafeBackupWashingRuleMachineWorkflow(
    ConfirmedBackupWashingRuleMachineWorkflow
):
    """Verify current Hubitat local backups without depending on list ordering.

    Some MCP releases return local backups oldest-first. A limit of ten can omit a
    manual backup created moments earlier. Request a larger local set and treat a
    whole-hub filename carrying today's date as verified recent evidence.
    """

    async def _recent_listed_backup(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {
            "checked": False,
            "recent": False,
            "source": "hub_list_backups",
            "strict_gateway": True,
            "requested_limit": 100,
        }
        try:
            tools = await self.client.list_tools(refresh=True)
        except Exception as exc:
            details["error"] = (
                f"Could not refresh MCP tools: {type(exc).__name__}: "
                f"{str(exc).strip()}"
            )
            return False, details

        visible = {str(getattr(tool, "name", "") or ""): tool for tool in tools}
        desired_args: dict[str, Any] = {"scope": "hub_local", "limit": 100}
        gateway: str | None = None
        request_name: str
        request_args: dict[str, Any]
        effective_args = dict(desired_args)

        if "hub_list_backups" in visible:
            request_name = "hub_list_backups"
            schema = dict(getattr(visible[request_name], "input_schema", {}) or {})
            properties = (
                schema.get("properties")
                if isinstance(schema.get("properties"), dict)
                else {}
            )
            if properties:
                effective_args = {
                    key: value for key, value in desired_args.items() if key in properties
                }
            request_args = effective_args
        elif "hub_manage_backup" in visible:
            request_name = "hub_manage_backup"
            gateway = request_name
            request_args = {"tool": "hub_list_backups", "args": effective_args}
        else:
            details["error"] = (
                "Neither the direct hub_list_backups tool nor the "
                "hub_manage_backup gateway was advertised. HomeBrain will not use "
                "an unrelated gateway for backup verification."
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
                "arguments": effective_args,
            }
        )
        try:
            result = await self.client.call_tool(request_name, request_args)
        except Exception as exc:
            details["exception_type"] = type(exc).__name__
            details["error"] = (
                str(exc).strip() or f"{type(exc).__name__} while listing backups"
            )
            return False, details

        details["result_is_error"] = bool(result.is_error)
        details["response_type"] = type(result.data).__name__
        if result.is_error:
            details["error"] = result.text or "hub_list_backups failed"
            return False, details

        now_ms = int(time.time() * 1000)
        today = datetime.now().astimezone().date()
        raw_rows = _mapping_rows(result.data) + _plain_backup_rows(result.data)
        unique_rows: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(raw_rows):
            if not isinstance(item, dict) or not _looks_like_local_hub_backup(item):
                continue
            key = str(
                item.get("id")
                or item.get("fileName")
                or item.get("filename")
                or item.get("file_name")
                or item.get("name")
                or index
            )
            existing = unique_rows.get(key, {})
            unique_rows[key] = {**existing, **item}

        candidates: list[dict[str, Any]] = []
        dated_but_not_recent: list[str] = []
        unparseable_names: list[str] = []
        filename_today_matches: list[str] = []

        for item in unique_rows.values():
            name = _row_name(item)
            timestamp_ms = _backup_timestamp_ms(item, now_ms)
            source = "metadata"

            filename_date = _hubitat_backup_filename_date(name)
            if filename_date == today:
                # A whole-hub local filename carrying today's date is enough to
                # establish that it is less than 24 hours old without guessing its
                # exact creation time.
                timestamp_ms = now_ms
                source = "filename_today"
                if name:
                    filename_today_matches.append(name)
            elif timestamp_ms is None and filename_date is not None:
                if name:
                    dated_but_not_recent.append(name)
                continue

            if timestamp_ms is None:
                if name:
                    unparseable_names.append(name)
                continue

            age_ms = now_ms - timestamp_ms
            if age_ms < 0 or age_ms > 365 * 24 * 60 * 60 * 1000:
                continue
            candidates.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "age_ms": age_ms,
                    "name": name,
                    "timestamp_source": source,
                }
            )

        candidates.sort(key=lambda item: item["timestamp_ms"], reverse=True)
        details["row_count"] = len(unique_rows)
        details["candidate_count"] = len(candidates)
        if filename_today_matches:
            details["filename_today_matches"] = filename_today_matches[:5]
        if dated_but_not_recent:
            details["dated_older_names"] = dated_but_not_recent[:5]
        if unparseable_names:
            details["unparseable_names"] = unparseable_names[:5]
        if candidates:
            details["newest"] = candidates[0]
            if candidates[0]["age_ms"] < _BACKUP_MAX_AGE_MS:
                details["recent"] = True
                return True, details

        details["error"] = (
            "No verifiable local hub backup from the last 24 hours was listed"
        )
        return False, details

    async def _create(self, pending: Any) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain checks up to 100 local backups through "
                    "hub_list_backups or hub_manage_backup and recognises current "
                    "Hubitat manual filenames such as "
                    "Hub_C8_Pro_YYYY-MM-DD~firmware~manual.lzf."
                )
        return answer


def install_filename_safe_backup_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> FilenameSafeBackupWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = FilenameSafeBackupWashingRuleMachineWorkflow(
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
    "FilenameSafeBackupWashingRuleMachineWorkflow",
    "_hubitat_backup_filename_date",
    "install_filename_safe_backup_rule_machine_workflow",
]

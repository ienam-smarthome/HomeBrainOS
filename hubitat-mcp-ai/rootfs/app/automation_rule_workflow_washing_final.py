from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _session_id, _tool_rows
from automation_rule_workflow_live import LiveRuleTool
from automation_rule_workflow_washing import WashingRuleMachineWorkflow


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_BACKUP_MAX_AGE_MS = 24 * 60 * 60 * 1000


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            rows.extend(_mapping_rows(item))
        return rows
    if not isinstance(value, dict):
        return rows

    keys = {str(key).lower() for key in value}
    identifying = {
        "filename",
        "file_name",
        "name",
        "location",
        "scope",
        "created",
        "createdat",
        "created_at",
        "createdepoch",
        "timestamp",
        "date",
        "backuptime",
        "agehours",
        "agems",
    }
    if keys.intersection(identifying):
        rows.append(value)
    for item in value.values():
        rows.extend(_mapping_rows(item))
    return rows


def _number(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _epoch_ms(value: Any) -> int | None:
    number = _number(value)
    if number is not None:
        if number > 10_000_000_000:
            return int(number)
        if number > 1_000_000_000:
            return int(number * 1000)

    text = str(value or "").strip()
    if not text:
        return None
    normalised = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)

    # Hubitat backup filenames commonly include at least YYYY-MM-DD. Accept a
    # date-only filename only when it is today's date; that proves age <24h
    # without guessing the backup time.
    match = re.search(r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        today = datetime.now().astimezone().date()
        try:
            backup_date = datetime(year, month, day).date()
        except ValueError:
            return None
        if backup_date == today:
            return int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    return None


def _backup_timestamp_ms(item: dict[str, Any], now_ms: int) -> int | None:
    lowered = {str(key).lower(): value for key, value in item.items()}

    for key in ("agems", "age_ms", "agemillis", "agemilliseconds"):
        age = _number(lowered.get(key))
        if age is not None and 0 <= age < 365 * 24 * 60 * 60 * 1000:
            return int(now_ms - age)
    for key in ("agehours", "age_hours"):
        age = _number(lowered.get(key))
        if age is not None and 0 <= age < 365 * 24:
            return int(now_ms - age * 60 * 60 * 1000)
    for key in ("ageseconds", "age_seconds"):
        age = _number(lowered.get(key))
        if age is not None and 0 <= age < 365 * 24 * 60 * 60:
            return int(now_ms - age * 1000)

    for key in (
        "createdepoch",
        "created_epoch",
        "timestamp",
        "epoch",
        "createdat",
        "created_at",
        "created",
        "backuptime",
        "backup_time",
        "date",
        "time",
        "modified",
        "lastmodified",
        "last_modified",
        "filename",
        "file_name",
        "name",
    ):
        if key in lowered:
            parsed = _epoch_ms(lowered[key])
            if parsed is not None:
                return parsed
    return None


def _looks_like_local_hub_backup(item: dict[str, Any]) -> bool:
    values = " ".join(
        str(item.get(key) or "")
        for key in ("location", "scope", "storage", "type", "source", "kind")
    ).lower()
    if "cloud" in values or "source" in values or "code" in values:
        return False
    if any(token in values for token in ("local", "hub_local", "hub", "database")):
        return True
    # The server was explicitly queried with scope=hub_local, so rows that omit
    # a location discriminator are still local whole-hub backups.
    return True


class FinalWashingRuleMachineWorkflow(WashingRuleMachineWorkflow):
    """Final washing workflow with verified backups and clear confirmations."""

    async def _find_tool(
        self,
        names: set[str],
        *,
        refresh: bool = False,
    ) -> LiveRuleTool | None:
        """Find direct, mapped or catalogue-only MCP tools.

        Some MCP gateway descriptions are deliberately compact and therefore do not
        enumerate every hidden child tool. Probe live gateway catalogues only after
        the normal direct/mapped lookup has failed.
        """

        found = await super()._find_tool(names, refresh=refresh)
        if found is not None:
            return found

        requested = {str(name).lower() for name in names}
        try:
            visible = await self.client.list_tools(refresh=refresh)
        except Exception:
            return None

        gateways: list[tuple[int, str]] = []
        for tool in visible:
            name = str(getattr(tool, "name", "") or "")
            schema = dict(getattr(tool, "input_schema", {}) or {})
            properties = (
                schema.get("properties")
                if isinstance(schema.get("properties"), dict)
                else {}
            )
            description = str(getattr(tool, "description", "") or "")
            text = f"{name} {description}".lower()
            is_gateway = bool(
                {"tool", "args"}.issubset(properties)
                or name.startswith(("hub_manage_", "manage_", "hub_read_"))
            )
            if not is_gateway:
                continue

            tokens = {
                token
                for requested_name in requested
                for token in requested_name.removeprefix("hub_").split("_")
                if len(token) >= 4
            }
            priority = 0 if any(token in text for token in tokens) else 1
            gateways.append((priority, name))

        for _, gateway in sorted(set(gateways)):
            try:
                catalogue = await self.client.call_tool(gateway, {})
            except Exception:
                continue
            if catalogue.is_error:
                continue
            for row in _tool_rows(catalogue.data):
                row_name = str(row.get("name") or "")
                if row_name.lower() not in requested:
                    continue
                return LiveRuleTool(
                    name=row_name,
                    description=str(row.get("description") or ""),
                    schema=dict(row.get("schema") or {}),
                    gateway=gateway,
                )
        return None

    async def _recent_listed_backup(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {
            "checked": False,
            "recent": False,
            "source": "hub_list_backups",
        }
        tool = await self._find_tool({"hub_list_backups", "list_backups"}, refresh=True)
        if tool is None:
            details["error"] = "hub_list_backups was not advertised"
            return False, details

        args = {self._argument_name(tool, "scope", "scope"): "hub_local"}
        schema = tool.schema if isinstance(tool.schema, dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        if "limit" in properties:
            args["limit"] = 10

        try:
            result = await self._call_rule_tool(tool, args)
        except Exception as exc:
            details["error"] = str(exc)
            return False, details

        details.update(
            {
                "checked": True,
                "tool": tool.name,
                "gateway": tool.gateway,
                "arguments": args,
            }
        )
        if result.is_error:
            details["error"] = result.text or "hub_list_backups failed"
            return False, details

        now_ms = int(time.time() * 1000)
        candidates: list[dict[str, Any]] = []
        for item in _mapping_rows(result.data):
            if not _looks_like_local_hub_backup(item):
                continue
            timestamp_ms = _backup_timestamp_ms(item, now_ms)
            if timestamp_ms is None:
                continue
            age_ms = now_ms - timestamp_ms
            if age_ms < 0 or age_ms > 365 * 24 * 60 * 60 * 1000:
                continue
            candidates.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "age_ms": age_ms,
                    "name": item.get("fileName")
                    or item.get("filename")
                    or item.get("name")
                    or item.get("id"),
                }
            )

        candidates.sort(key=lambda item: item["timestamp_ms"], reverse=True)
        details["candidate_count"] = len(candidates)
        if candidates:
            details["newest"] = candidates[0]
            if candidates[0]["age_ms"] < _BACKUP_MAX_AGE_MS:
                details["recent"] = True
                return True, details
        details["error"] = "No verifiable local hub backup from the last 24 hours was listed"
        return False, details

    async def _ensure_backup(self, key: str | None) -> tuple[bool, dict[str, Any]]:
        listed_ok, listed = await self._recent_listed_backup()
        if listed_ok:
            return True, {
                "created": False,
                "recent": True,
                "verified_by": "hub_list_backups",
                "listed": listed,
            }

        created_ok, created = await super()._ensure_backup(key)
        if created_ok:
            created["listed_before_create"] = listed
            return True, created

        error = str(created.get("error") or "")
        if "not advertised" in error.lower():
            created["error"] = (
                "hub_create_backup is not present in MCP tools/list. It is a separate core tool, "
                "not part of hub_manage_backup. In Apps > MCP Rule Server > Settings > Advanced: "
                "Per-tool Overrides, remove hub_create_backup from Disabled tools or use Reset all "
                "overrides, then save and refresh MCP tools."
            )
        created["listed_backup_check"] = listed
        return False, created

    async def _call_operation(
        self,
        pending: PendingRule,
        operation: str,
    ) -> dict[str, Any]:
        answer = await super()._call_operation(pending, operation)
        is_washing = str((pending.draft or {}).get("type") or "") == "washing-complete"
        if is_washing and operation == "enable" and answer.get("success") is True:
            title = str((pending.created_rule or {}).get("name") or "Washing machine rule")
            answer["message"] = (
                f"Enabled **{title}**. It can now monitor washing-machine power and notify "
                "the selected phone after a genuine cycle finishes."
            )
        return answer

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain checked for an existing local hub backup from the last 24 hours, "
                    "then tried the separate hub_create_backup core tool. If it is absent, open "
                    "MCP Rule Server > Settings > Advanced: Per-tool Overrides and reset or "
                    "re-enable hub_create_backup, refresh MCP tools, then press Create again."
                )
        return answer


def install_final_washing_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> FinalWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = FinalWashingRuleMachineWorkflow(
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
    "FinalWashingRuleMachineWorkflow",
    "install_final_washing_rule_machine_workflow",
]

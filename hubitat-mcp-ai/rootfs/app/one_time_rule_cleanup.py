from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from health_audit_scheduler import next_daily_run, parse_daily_time
from mcp_client import HubitatMCPClient, tool_succeeded


logger = logging.getLogger("HomeBrainOS.OneTimeRuleCleanup")

_ONE_TIME_NAME = re.compile(
    r"^.+ \(One-time (?P<scheduled>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\)$"
)


@dataclass(slots=True)
class OneTimeRuleCleanupResult:
    checked_at: str
    scanned: int = 0
    eligible: int = 0
    deleted: list[dict[str, str]] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)
    list_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked_at": self.checked_at,
            "scanned": self.scanned,
            "eligible": self.eligible,
            "deleted": list(self.deleted),
            "deleted_count": len(self.deleted),
            "failed": list(self.failed),
            "failed_count": len(self.failed),
            "list_error": self.list_error,
        }


class OneTimeRuleCleanupService:
    """Soft-delete expired HomeBrain one-time Rule Machine rules only.

    Ownership is deliberately narrow: a rule must have both a Rule Machine app id
    and the exact HomeBrain suffix ``(One-time YYYY-MM-DD HH:MM)``. The suffix is
    interpreted in the same Hubitat-local timezone supplied by ``local_now``.
    Ordinary/recurring rules, malformed names, and future one-time rules are never
    submitted to the delete gateway.
    """

    def __init__(
        self,
        mcp: HubitatMCPClient,
        *,
        local_now: Callable[[], Awaitable[datetime]],
        grace_minutes: int = 10,
    ) -> None:
        self.mcp = mcp
        self._local_now = local_now
        self.grace_minutes = max(0, int(grace_minutes))

    @staticmethod
    def _candidate(name: str, app_id: str | None, now: datetime, grace_minutes: int) -> bool:
        if not app_id:
            return False
        match = _ONE_TIME_NAME.fullmatch(str(name or "").strip())
        if match is None:
            return False
        try:
            scheduled = datetime.strptime(match.group("scheduled"), "%Y-%m-%d %H:%M")
        except ValueError:
            return False
        scheduled = scheduled.replace(tzinfo=now.tzinfo)
        return scheduled + timedelta(minutes=grace_minutes) <= now

    @staticmethod
    def _authoritative_rule_rows(data: Any) -> list[dict[str, Any]] | None:
        """Return only an explicit hub_list_rules ``rules`` collection.

        Destructive cleanup must distinguish a genuinely empty authoritative
        rule list from an unrelated/schemaless gateway response. Only the
        ``rules`` field is accepted; common MCP wrapper objects may contain it.
        """
        if not isinstance(data, dict):
            return None
        if "rules" in data:
            rows = data.get("rules")
            if not isinstance(rows, list):
                return None
            return [dict(row) for row in rows if isinstance(row, dict)]
        for key in ("result", "data", "output", "structuredContent"):
            child = data.get(key)
            rows = OneTimeRuleCleanupService._authoritative_rule_rows(child)
            if rows is not None:
                return rows
        return None

    async def run(self) -> OneTimeRuleCleanupResult:
        now = await self._local_now()
        if now.tzinfo is None:
            raise ValueError("One-time cleanup requires an aware Hubitat-local datetime")
        outcome = OneTimeRuleCleanupResult(checked_at=now.isoformat())

        try:
            listed = await self.mcp.call_tool(
                "hub_read_rules",
                {"tool": "hub_list_rules", "args": {}},
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            outcome.list_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            logger.warning("One-time cleanup could not list rules: %s", exc)
            return outcome

        if not tool_succeeded(listed):
            outcome.list_error = "hub_read_rules failed; no rules were deleted"
            logger.warning("One-time cleanup list read failed; refusing deletion")
            return outcome

        rows = self._authoritative_rule_rows(listed.data)
        if rows is None:
            outcome.list_error = (
                "hub_list_rules returned no authoritative rules list; "
                "no rules were deleted"
            )
            logger.warning(
                "One-time cleanup rule-list response was not authoritative; refusing deletion"
            )
            return outcome

        outcome.scanned = len(rows)
        candidates: list[dict[str, str]] = []
        for row in rows:
            identifier = row.get("appId") or row.get("id") or row.get("ruleId")
            name = str(
                row.get("label")
                or row.get("name")
                or row.get("displayName")
                or row.get("title")
                or ""
            ).strip()
            app_id = str(identifier) if identifier is not None else None
            if self._candidate(name, app_id, now, self.grace_minutes):
                candidates.append({"id": str(app_id), "name": name})
        outcome.eligible = len(candidates)

        for item in candidates:
            app_id = str(item["id"])
            name = str(item["name"])
            arguments = {
                "tool": "hub_delete_native_app",
                "args": {
                    "appId": app_id,
                    "force": False,
                    "confirm": True,
                },
            }
            try:
                deleted = await self.mcp.call_tool(
                    "hub_manage_native_rules_and_apps",
                    arguments,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:300]}"
                outcome.failed.append({"appId": app_id, "name": name, "error": error})
                logger.warning("One-time cleanup failed for appId %s (%s): %s", app_id, name, exc)
                continue

            if tool_succeeded(deleted):
                outcome.deleted.append({"appId": app_id, "name": name})
                logger.info("Deleted expired HomeBrain one-time rule appId %s: %s", app_id, name)
            else:
                outcome.failed.append(
                    {"appId": app_id, "name": name, "error": "soft delete failed"}
                )
                logger.warning("One-time cleanup soft delete failed for appId %s: %s", app_id, name)

        return outcome


class OneTimeRuleCleanupScheduler:
    """Run destructive one-time-rule cleanup once daily in Hubitat-local time."""

    def __init__(
        self,
        service: OneTimeRuleCleanupService,
        *,
        enabled: bool,
        daily_time: str,
        local_now: Callable[[], Awaitable[datetime]],
        state_path: Path | str | None = None,
    ) -> None:
        self.service = service
        self.enabled = bool(enabled)
        requested = str(daily_time or "01:00")
        try:
            parse_daily_time(requested)
            self.daily_time = requested
            self.last_error: str | None = None
        except (TypeError, ValueError):
            self.daily_time = "01:00"
            self.last_error = f"Invalid one_time_rule_cleanup_time {requested!r}; using 01:00"
        self._local_now = local_now
        self._task: asyncio.Task[Any] | None = None
        self._run_lock = asyncio.Lock()
        self.next_run: str | None = None
        self.last_run: str | None = None
        self.last_trigger: str | None = None
        self.last_result: OneTimeRuleCleanupResult | None = None
        self.state_path = Path(state_path) if state_path else None
        self.persistence_error: str | None = None
        self._configuration_error = self.last_error
        self._restore_state()

    @staticmethod
    def _result_from_payload(value: Any) -> OneTimeRuleCleanupResult | None:
        if not isinstance(value, dict):
            return None
        checked_at = str(value.get("checked_at") or "").strip()
        if not checked_at:
            return None
        deleted = [dict(item) for item in value.get("deleted", []) if isinstance(item, dict)]
        failed = [dict(item) for item in value.get("failed", []) if isinstance(item, dict)]
        try:
            scanned = max(0, int(value.get("scanned") or 0))
            eligible = max(0, int(value.get("eligible") or 0))
        except (TypeError, ValueError):
            return None
        list_error = str(value.get("list_error") or "").strip() or None
        return OneTimeRuleCleanupResult(
            checked_at=checked_at,
            scanned=scanned,
            eligible=eligible,
            deleted=deleted,
            failed=failed,
            list_error=list_error,
        )

    def _restore_state(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                raise ValueError("unsupported cleanup state schema")
            restored = self._result_from_payload(payload.get("last_result"))
            self.last_result = restored
            self.last_run = str(payload.get("last_run") or "").strip() or (restored.checked_at if restored else None)
            self.last_trigger = str(payload.get("last_trigger") or "").strip() or None
            if self._configuration_error is None:
                self.last_error = str(payload.get("last_error") or "").strip() or None
            self.persistence_error = None
            logger.info(
                "One-time cleanup history restored: last_run=%s trigger=%s deleted=%s failed=%s",
                self.last_run or "none",
                self.last_trigger or "none",
                len(restored.deleted) if restored else 0,
                len(restored.failed) if restored else 0,
            )
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            logger.warning("Could not restore one-time cleanup history: %s", exc)

    def _persist_state(self) -> None:
        if self.state_path is None:
            return
        payload = {
            "schema_version": 1,
            "last_run": self.last_run,
            "last_trigger": self.last_trigger,
            "last_error": self.last_error,
            "last_result": self.last_result.as_dict() if self.last_result else None,
        }
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            temp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp.replace(self.state_path)
            self.persistence_error = None
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            logger.warning("Could not persist one-time cleanup history: %s", exc)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "time": self.daily_time,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "last_trigger": self.last_trigger,
            "last_error": self.last_error,
            "persistence_error": self.persistence_error,
            "history_persisted": bool(self.state_path),
            "running": self._run_lock.locked(),
            "task_active": bool(self._task is not None and not self._task.done()),
            "last_result": self.last_result.as_dict() if self.last_result else None,
        }

    async def run_now(self) -> OneTimeRuleCleanupResult:
        """Run the same guarded cleanup path immediately on explicit request."""
        return await self._run_once(trigger="manual")

    def start(self) -> None:
        if not self.enabled:
            logger.info("One-time cleanup scheduler disabled")
            return
        if self._task is not None:
            return
        logger.info(
            "One-time cleanup scheduler started: daily_time=%s grace_minutes=%s",
            self.daily_time,
            self.service.grace_minutes,
        )
        self._task = asyncio.create_task(self._run(), name="homebrain-one-time-rule-cleanup")

    async def close(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel("application shutdown")
        with suppress(asyncio.CancelledError):
            await task

    async def _run_once(self, *, trigger: str) -> OneTimeRuleCleanupResult:
        async with self._run_lock:
            logger.info("One-time cleanup starting: trigger=%s", trigger)
            try:
                result = await self.service.run()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                self.last_trigger = trigger
                self._persist_state()
                logger.exception("One-time rule cleanup failed: trigger=%s", trigger)
                raise

            self.last_result = result
            self.last_run = result.checked_at
            self.last_trigger = trigger
            self.last_error = result.list_error
            self._persist_state()
            logger.info(
                "One-time cleanup completed: trigger=%s scanned=%s eligible=%s deleted=%s failed=%s list_error=%s",
                trigger,
                result.scanned,
                result.eligible,
                len(result.deleted),
                len(result.failed),
                result.list_error or "none",
            )
            return result

    async def _run(self) -> None:
        while True:
            try:
                now = await self._local_now()
                if now.tzinfo is None:
                    raise ValueError("One-time cleanup scheduler requires an aware datetime")
                target = next_daily_run(now, self.daily_time)
                self.next_run = target.isoformat()
                logger.info(
                    "One-time cleanup next run: configured_time=%s next_run=%s",
                    self.daily_time,
                    self.next_run,
                )
                delay = max(1.0, (target - now).total_seconds())
                await asyncio.sleep(delay)
                await self._run_once(trigger="scheduled")
                self.next_run = None
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                logger.warning("One-time cleanup scheduler clock failed: %s", exc)
                self.next_run = None
                await asyncio.sleep(60)


__all__ = [
    "OneTimeRuleCleanupResult",
    "OneTimeRuleCleanupScheduler",
    "OneTimeRuleCleanupService",
]

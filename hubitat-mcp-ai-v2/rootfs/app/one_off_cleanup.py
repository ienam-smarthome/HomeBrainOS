"""Opt-in, conservative native Rule Machine one-off expiry maintenance.

No model tool routes, no UI writes, no automatic migration of older names.
Every possible destructive action is re-attested against installed hub state.
Default config is DISABLED and DRY RUN; never delete on add-on upgrade.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from one_off_rule_policy import OWNED, decode_mcp_payload

log = logging.getLogger("HomeBrainV2.OneOffCleanup")


def _successful(value: Any) -> dict | None:
    if not isinstance(value, dict) or value.get("isError") is True:
        return None
    content = decode_mcp_payload(value)
    return content if isinstance(content, dict) and content.get("success") is not False else None


def _rule_rows(payload: dict) -> list[dict] | None:
    rows = payload.get("rules")
    if isinstance(rows, list) and all(isinstance(x, dict) for x in rows):
        return rows
    for key in ("result", "data", "structuredContent"):
        sub = payload.get(key)
        if isinstance(sub, dict):
            found = _rule_rows(sub)
            if found is not None:
                return found
    return None


def _named_candidate(row: dict, now: datetime, grace: int) -> tuple[str, str, str] | None:
    name = row.get("name") or row.get("label")
    app_id = row.get("appId", row.get("id"))
    if not isinstance(name, str) or not str(app_id).isdigit():
        return None
    match = OWNED.fullmatch(name)
    if match is None or int(app_id) <= 0:
        return None
    declared = row.get("appType") or row.get("type")
    if declared:
        typed = declared.get("name") if isinstance(declared, dict) else str(declared)
        if typed != "Rule Machine":
            return None
    try:
        local = datetime.strptime(
            match.group("date") + " " + match.group("hour"), "%Y-%m-%d %H:%M"
        ).replace(tzinfo=now.tzinfo)
    except ValueError:
        return None
    # Protect future schedules and any rule still in its post-run grace period.
    if local.astimezone(timezone.utc) + timedelta(minutes=grace) > now.astimezone(timezone.utc):
        return None
    return str(app_id), name, match.group("date")


def _setting_values(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return {
            str(name): row.get("value") if isinstance(row, dict) else row
            for name, row in value.items()
        }
    if isinstance(value, list):
        if not all(isinstance(x, dict) and isinstance(x.get("name"), str)
                   and "value" in x for x in value):
            return None
        return {x["name"]: x["value"] for x in value}
    return None


def _attested_read(read: dict, app_id: str, label: str, scheduled_day: str) -> bool:
    """Require exact native read identity AND persisted dated trigger semantics."""
    doc = read.get("rule", read.get("app", read.get("document", read)))
    if not isinstance(doc, dict):
        return False
    if str(doc.get("id", doc.get("appId", doc.get("rule_id")))) != app_id:
        return False
    if (doc.get("label") or doc.get("name") or doc.get("origLabel")) != label:
        return False
    typed = doc.get("appType") or doc.get("type")
    typed_name = typed.get("name") if isinstance(typed, dict) else typed
    if typed_name != "Rule Machine":
        return False
    if isinstance(typed, dict) and typed.get("namespace") not in ("hubitat", None):
        return False
    settings = _setting_values(doc.get("settings", read.get("settings")))
    if not settings:
        return False
    if (settings.get("tCapab1") != "Certain Time (and optional date)"
            or settings.get("date1") not in (True, "true")
            or str(settings.get("atDate1")) != scheduled_day):
        return False
    # An undated daily rule or an unrelated rule with an ownership-like
    # name MUST NOT be removed. Require exactly one native date trigger.
    if any(k.startswith("tCapab") and k != "tCapab1" for k in settings):
        return False
    return True


class OneOffCleanup:
    def __init__(
        self, mcp: Any, *, enabled: bool = False, dry_run: bool = True,
        daily_time: str = "07:00", timezone_name: str = "Europe/London",
        grace_minutes: int = 15, state_file: Path | None = None,
    ):
        self.mcp = mcp
        self.enabled = bool(enabled)
        self.dry_run = bool(dry_run)
        self.zone = ZoneInfo(timezone_name)
        try:
            self.clock = time.fromisoformat(daily_time)
        except ValueError:
            raise ValueError("one-off cleanup time must be HH:MM") from None
        if self.clock.second or self.clock.microsecond:
            raise ValueError("one-off cleanup time must be HH:MM")
        self.grace = max(10, int(grace_minutes))
        self.state_file = state_file
        self.last_day: str | None = None
        self.last_result: dict | None = None
        self.uncertain_ids: set[str] = set()
        self.task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._load()

    def _load(self):
        if not self.state_file or not self.state_file.exists():
            return
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            if payload.get("version") != 1:
                return
            self.last_day = payload.get("last_day")
            self.last_result = payload.get("last_result")
            self.uncertain_ids = {
                x for x in payload.get("uncertain_ids", [])
                if isinstance(x, str) and x.isdigit()
            }
        except (ValueError, OSError, AttributeError):
            log.warning("Cannot read saved one-off cleanup status; refusing unsafe recovery")
            # Disabling writes on corrupt history avoids retrying an unknown
            # previously submitted deletion after a restart.
            self.dry_run = True

    def _persist(self):
        if self.state_file is None:
            return
        payload = {
            "version": 1, "last_day": self.last_day,
            "last_result": self.last_result,
            "uncertain_ids": sorted(self.uncertain_ids),
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self.state_file)

    def status(self):
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "daily_time": self.clock.strftime("%H:%M"),
            "timezone": str(self.zone),
            "grace_minutes": self.grace,
            "last_day": self.last_day,
            "last_result": self.last_result,
            "task_active": bool(self.task and not self.task.done()),
            "uncertain_deletions_held": len(self.uncertain_ids),
        }

    async def run_once(self, *, now: datetime | None = None) -> dict:
        """Run only after scheduled opt-in; no unauthorised public API."""
        async with self._lock:
            local = (now or datetime.now(self.zone)).astimezone(self.zone)
            result: dict[str, Any] = {
                "checked_at": local.isoformat(), "scanned": 0,
                "eligible": 0, "confirmed": 0,
                "would_delete": [], "deleted": [], "skipped": [],
                "errors": [], "dry_run": self.dry_run,
            }
            try:
                raw = await self.mcp.call(
                    "hub_read_rules", {"tool": "hub_list_rules", "args": {}}
                )
                data = _successful(raw)
                rows = _rule_rows(data) if data is not None else None
                if rows is None:
                    raise ValueError("No authoritative native rule list")
            except asyncio.CancelledError:
                raise
            except Exception:
                result["errors"].append("Native rule list unavailable; no deletes")
                return result

            result["scanned"] = len(rows)
            for row in rows:
                item = _named_candidate(row, local, self.grace)
                if not item:
                    continue
                app_id, label, day = item
                result["eligible"] += 1
                if app_id in self.uncertain_ids:
                    result["skipped"].append({"appId": app_id, "why": "uncertain previous delete"})
                    continue
                try:
                    native = await self.mcp.call(
                        "hub_manage_native_rules_and_apps",
                        {"tool": "hub_set_rule", "args": {
                            "operation": "read", "rule_id": int(app_id),
                        }},
                    )
                    source = _successful(native)
                    if source is None or not _attested_read(source, app_id, label, day):
                        result["skipped"].append({
                            "appId": app_id, "why": "native dated-rule identity not attested"
                        })
                        continue
                    result["confirmed"] += 1
                    if self.dry_run:
                        result["would_delete"].append({"appId": app_id, "name": label})
                        continue
                    # No retries after transport ambiguity. Persist the in-flight
                    # identifier BEFORE making an irreversible native request.
                    self.uncertain_ids.add(app_id)
                    self._persist()
                    deleted = await self.mcp.call(
                        "hub_manage_native_rules_and_apps",
                        {"tool": "hub_delete_native_app", "args": {
                            "appId": app_id, "force": False, "confirm": True,
                        }},
                    )
                    outcome = _successful(deleted)
                    if outcome is None or outcome.get("success") is not True:
                        result["errors"].append({
                            "appId": app_id, "why": "delete unverified; manual check required"
                        })
                        continue
                    self.uncertain_ids.discard(app_id)
                    result["deleted"].append({"appId": app_id, "name": label})
                    self._persist()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    result["errors"].append({
                        "appId": app_id, "why": "native read/delete unavailable; manual check"
                    })
                    # If an attempted delete timed out, the ID remains held
                    # for manual reconciliation. Reads never enter this set.
            return result

    async def _run(self):
        while True:
            local = datetime.now(self.zone)
            when = datetime.combine(local.date(), self.clock, tzinfo=self.zone)
            if when <= local:
                when = datetime.combine(
                    local.date() + timedelta(days=1), self.clock, tzinfo=self.zone
                )
            await asyncio.sleep(max(1, (when.astimezone(timezone.utc)
                                        - local.astimezone(timezone.utc)).total_seconds()))
            today = datetime.now(self.zone).date().isoformat()
            if today == self.last_day:
                continue
            try:
                self.last_day = today
                self._persist()
                self.last_result = await self.run_once()
                self._persist()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("One-off maintenance failed; no automatic retry")

    def start(self):
        if self.enabled and self.mcp is not None and self.task is None:
            self.task = asyncio.create_task(self._run(), name="v2-owned-oneoff-cleanup")

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        self.task = None

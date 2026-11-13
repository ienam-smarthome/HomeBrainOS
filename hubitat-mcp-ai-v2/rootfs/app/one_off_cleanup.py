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
        if typed not in ("Rule Machine", "Rule-5.1"):
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


def _attested_read(
    document: dict, app_config: dict, app_id: str,
    label: str, scheduled_day: str, scheduled_clock: str,
) -> bool:
    """Require native rule settings AND independently typed installed-child app.

    The native hub_set_rule read returns rule_id/settings but does not
    necessarily contain an installed app label/type. An app page alone does
    not establish that the persisted trigger is dated. Both are required.
    """
    if str(document.get("rule_id")) != app_id:
        return False
    app = app_config.get("app")
    if not isinstance(app, dict) or str(app.get("id", app.get("appId"))) != app_id:
        return False
    if (app.get("label") or app.get("name")) != label:
        return False
    typed = app.get("appType")
    if (not isinstance(typed, dict)
            or typed.get("namespace") != "hubitat"
            or typed.get("name") != "Rule-5.1"):
        return False
    settings = _setting_values(document.get("settings"))
    if not settings:
        return False
    if (settings.get("tCapab1") != "Certain Time (and optional date)"
            or settings.get("date1") not in (True, "true")
            or str(settings.get("atDate1")) != scheduled_day
            or settings.get("time1") != "A specific time"):
        return False
    if any(k.startswith("tCapab") and k != "tCapab1" for k in settings):
        return False
    if (settings.get("actType.1") != "switchActs"
            or settings.get("actSubType.1") != "getOnOffSwitch"
            or "onOffSwitch.1" not in settings or "onOff.1" not in settings):
        return False
    if any(k.startswith("actType.") and k != "actType.1" for k in settings):
        return False
    original_time = settings.get("atTime1")
    if not isinstance(original_time, str):
        return False
    try:
        when = datetime.fromisoformat(original_time)
    except ValueError:
        return False
    if (when.tzinfo is None or when.utcoffset() is None
            or when.strftime("%Y-%m-%d") != scheduled_day
            or when.strftime("%H:%M") != scheduled_clock):
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
        # /api/status is not an authenticated rule inventory endpoint.
        # Expose counts, never household rule names or native app IDs.
        last = self.last_result
        summary = None
        if isinstance(last, dict):
            summary = {
                "checked_at": last.get("checked_at"),
                "scanned": last.get("scanned", 0),
                "eligible": last.get("eligible", 0),
                "confirmed": last.get("confirmed", 0),
                "would_delete_count": len(last.get("would_delete", [])),
                "deleted_count": len(last.get("deleted", [])),
                "skipped_count": len(last.get("skipped", [])),
                "error_count": len(last.get("errors", [])),
                "dry_run": last.get("dry_run", True),
            }
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "daily_time": self.clock.strftime("%H:%M"),
            "timezone": str(self.zone),
            "grace_minutes": self.grace,
            "last_day": self.last_day,
            "last_result": summary,
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
            if not self.enabled:
                result["errors"].append("Cleanup is disabled; no MCP calls")
                return result
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
                scheduled_clock = OWNED.fullmatch(label).group("hour")
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
                    # The actual native document contains persisted settings,
                    # but not a reliable app class/label. Read the installed
                    # app identity independently and require a Rule-5.1 child.
                    config_raw = await self.mcp.call(
                        "hub_get_app_config", {"appId": int(app_id)}
                    )
                    app_identity = _successful(config_raw)
                    if (source is None or app_identity is None
                            or not _attested_read(source, app_identity,
                                                  app_id, label, day,
                                                  scheduled_clock)):
                        result["skipped"].append({
                            "appId": app_id, "why": "native date or installed-child identity unverified"
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

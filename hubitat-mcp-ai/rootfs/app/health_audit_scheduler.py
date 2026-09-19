from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from health_audit_service import HealthAuditService
from pushover_notifier import PushoverNotifier


logger = logging.getLogger("HomeBrainOS.HealthScheduler")


def parse_daily_time(value: str) -> tuple[int, int]:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError("Daily health-check time must use HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("Daily health-check time must use HH:MM")
    return hour, minute


def next_daily_run(now: datetime, daily_time: str) -> datetime:
    if now.tzinfo is None:
        raise ValueError("Scheduler requires an aware datetime")
    hour, minute = parse_daily_time(daily_time)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def catchup_due(
    now: datetime,
    daily_time: str,
    latest: dict[str, Any] | None,
    *,
    grace_minutes: int = 60,
) -> bool:
    if now.tzinfo is None:
        return False
    hour, minute = parse_daily_time(daily_time)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < target or now > target + timedelta(minutes=max(0, grace_minutes)):
        return False
    if not isinstance(latest, dict) or latest.get("reason") != "scheduled":
        return True
    raw = str(latest.get("checked_at") or "").strip()
    if not raw:
        return True
    try:
        checked = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if checked.tzinfo is None:
        return True
    return checked.astimezone(now.tzinfo).date() != now.date()


class MorningHealthScheduler:
    """Run one stored read-only system audit each morning in hub-local time."""

    def __init__(
        self,
        service: HealthAuditService,
        *,
        enabled: bool,
        daily_time: str,
        local_now: Callable[[], Awaitable[datetime]],
        notifier: PushoverNotifier | None = None,
        startup_delay_seconds: float = 30.0,
        catchup_minutes: int = 60,
    ) -> None:
        self.service = service
        self.enabled = bool(enabled)
        requested_time = str(daily_time or "07:00")
        invalid_time_error: str | None = None
        try:
            parse_daily_time(requested_time)
            self.daily_time = requested_time
        except (TypeError, ValueError):
            self.daily_time = "07:00"
            invalid_time_error = (
                f"Invalid morning_health_check_time {requested_time!r}; using 07:00"
            )
        self._local_now = local_now
        self.notifier = notifier
        self.startup_delay_seconds = max(0.0, float(startup_delay_seconds))
        self.catchup_minutes = max(0, int(catchup_minutes))
        self._task: asyncio.Task[Any] | None = None
        self.next_run: str | None = None
        self.last_error: str | None = invalid_time_error
        self.last_notification_at: str | None = None
        self.last_notification_error: str | None = None

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "time": self.daily_time,
            "next_run": self.next_run,
            "last_error": self.last_error,
            "pushover_enabled": bool(self.notifier and self.notifier.enabled),
            "last_notification_at": self.last_notification_at,
            "last_notification_error": self.last_notification_error,
        }

    def start(self) -> None:
        if not self.enabled or self._task is not None:
            return
        self._task = asyncio.create_task(
            self._run(),
            name="homebrain-morning-health-check",
        )

    async def close(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel("application shutdown")
        with suppress(asyncio.CancelledError):
            await task

    async def _run_once(self) -> None:
        try:
            result = await self.service.run(reason="scheduled")
            self.last_error = None
            if self.notifier and self.notifier.enabled:
                try:
                    await self.notifier.send(result)
                    self.last_notification_at = str(
                        result.get("checked_at")
                        or datetime.now().astimezone().isoformat()
                    )
                    self.last_notification_error = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_notification_error = (
                        f"{type(exc).__name__}: {str(exc)[:300]}"
                    )
                    logger.warning(
                        "Scheduled System Check completed but Pushover delivery failed: %s",
                        exc,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            logger.exception("Scheduled system health audit failed")

    async def _run(self) -> None:
        if self.startup_delay_seconds:
            await asyncio.sleep(self.startup_delay_seconds)

        while True:
            try:
                now = await self._local_now()
                if now.tzinfo is None:
                    now = now.astimezone()

                if catchup_due(
                    now,
                    self.daily_time,
                    self.service.latest(),
                    grace_minutes=self.catchup_minutes,
                ):
                    self.next_run = now.isoformat()
                    await self._run_once()
                    await asyncio.sleep(1)
                    now = await self._local_now()
                    if now.tzinfo is None:
                        now = now.astimezone()

                target = next_daily_run(now, self.daily_time)
                self.next_run = target.isoformat()
                delay = max(1.0, (target - now).total_seconds())
                await asyncio.sleep(delay)
                await self._run_once()
                self.next_run = None
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                logger.warning("Health scheduler clock failed: %s", exc)
                self.next_run = None
                await asyncio.sleep(60)


__all__ = [
    "MorningHealthScheduler",
    "catchup_due",
    "next_daily_run",
    "parse_daily_time",
]

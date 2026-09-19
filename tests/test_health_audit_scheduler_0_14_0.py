from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from health_audit_scheduler import (  # noqa: E402
    MorningHealthScheduler,
    catchup_due,
    next_daily_run,
    parse_daily_time,
)


def test_parse_daily_time_and_next_run() -> None:
    assert parse_daily_time("07:30") == (7, 30)

    now = datetime(2026, 9, 19, 6, 15, tzinfo=ZoneInfo("Europe/London"))
    assert next_daily_run(now, "07:00").isoformat() == "2026-09-19T07:00:00+01:00"

    later = datetime(2026, 9, 19, 8, 15, tzinfo=ZoneInfo("Europe/London"))
    assert next_daily_run(later, "07:00").isoformat() == "2026-09-20T07:00:00+01:00"


def test_catchup_only_once_for_same_local_day() -> None:
    zone = ZoneInfo("Europe/London")
    now = datetime(2026, 9, 19, 7, 20, tzinfo=zone)

    assert catchup_due(now, "07:00", None) is True
    assert catchup_due(
        now,
        "07:00",
        {
            "reason": "scheduled",
            "checked_at": "2026-09-19T06:05:00+00:00",
        },
    ) is False
    assert catchup_due(
        now,
        "07:00",
        {
            "reason": "manual",
            "checked_at": "2026-09-19T06:05:00+00:00",
        },
    ) is True


def test_invalid_configured_time_falls_back_without_crashing() -> None:
    class Service:
        def latest(self):
            return None

    async def now():
        return datetime(2026, 9, 19, 6, 0, tzinfo=ZoneInfo("Europe/London"))

    scheduler = MorningHealthScheduler(
        Service(),  # type: ignore[arg-type]
        enabled=True,
        daily_time="99:99",
        local_now=now,
    )

    assert scheduler.daily_time == "07:00"
    assert "Invalid morning_health_check_time" in str(scheduler.last_error)


@pytest.mark.asyncio
async def test_scheduled_check_sends_pushover_but_preserves_audit_on_delivery_failure() -> None:
    class Service:
        async def run(self, *, reason):
            assert reason == "scheduled"
            return {"status": "healthy", "attention_count": 0}

    class Notifier:
        enabled = True

        def __init__(self):
            self.results = []

        async def send(self, result):
            self.results.append(result)
            raise RuntimeError("network unavailable")

    async def now():
        return datetime(2026, 9, 19, 6, 0, tzinfo=ZoneInfo("Europe/London"))

    notifier = Notifier()
    scheduler = MorningHealthScheduler(
        Service(),  # type: ignore[arg-type]
        enabled=True,
        daily_time="07:00",
        local_now=now,
        notifier=notifier,  # type: ignore[arg-type]
    )

    await scheduler._run_once()

    assert notifier.results == [{"status": "healthy", "attention_count": 0}]
    assert scheduler.last_error is None
    assert "network unavailable" in str(scheduler.last_notification_error)

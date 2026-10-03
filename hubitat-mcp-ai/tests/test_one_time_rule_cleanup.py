from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult
from one_time_rule_cleanup import OneTimeRuleCleanupService


def result(name: str, arguments: dict[str, Any], data: Any, *, error: bool = False) -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments=arguments,
        raw={},
        text="",
        data=data,
        is_error=error,
    )


class FakeMCP:
    def __init__(self, *, fail_app: str | None = None, list_failure: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_app = fail_app
        self.list_failure = list_failure

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_read_rules":
            if self.list_failure:
                return result(name, arguments, {"success": False, "error": "unavailable"}, error=True)
            return result(
                name,
                arguments,
                {
                    "success": True,
                    "rules": [
                        {
                            "appId": "4210",
                            "name": "Block Media Google TV Streamer (One-time 2026-10-03 08:42)",
                            "status": "active",
                        },
                        {
                            "appId": "4211",
                            "name": "Block Media Google TV Streamer (One-time 2026-10-03 11:46)",
                            "status": "active",
                        },
                        {
                            "appId": "5000",
                            "name": "Future Light (One-time 2026-10-04 08:00)",
                            "status": "active",
                        },
                        {
                            "appId": "6000",
                            "name": "01. Humidity Controller",
                            "status": "active",
                        },
                        {
                            "appId": "7000",
                            "name": "Not HomeBrain (One-time tomorrow)",
                            "status": "active",
                        },
                    ],
                },
            )
        if name == "hub_manage_native_rules_and_apps":
            app_id = str((arguments.get("args") or {}).get("appId"))
            failed = app_id == self.fail_app
            return result(
                name,
                arguments,
                {"success": not failed, "error": "delete failed" if failed else None},
                error=failed,
            )
        raise AssertionError(f"Unexpected tool call: {name} {arguments}")


async def local_now() -> datetime:
    return datetime(2026, 10, 4, 1, 0, tzinfo=ZoneInfo("Europe/London"))


@pytest.mark.asyncio
async def test_cleanup_deletes_only_expired_exact_homebrain_one_time_names() -> None:
    mcp = FakeMCP()
    service = OneTimeRuleCleanupService(mcp, local_now=local_now, grace_minutes=10)

    outcome = await service.run()

    assert outcome.scanned == 5
    assert outcome.eligible == 2
    assert [item["appId"] for item in outcome.deleted] == ["4210", "4211"]
    delete_calls = [call for call in mcp.calls if call[0] == "hub_manage_native_rules_and_apps"]
    assert len(delete_calls) == 2
    for _, arguments in delete_calls:
        assert arguments["tool"] == "hub_delete_native_app"
        assert arguments["args"]["force"] is False
        assert arguments["args"]["confirm"] is True
    assert {call[1]["args"]["appId"] for call in delete_calls} == {"4210", "4211"}


@pytest.mark.asyncio
async def test_cleanup_grace_period_prevents_early_delete() -> None:
    async def now_before_grace() -> datetime:
        return datetime(2026, 10, 3, 11, 55, tzinfo=ZoneInfo("Europe/London"))

    mcp = FakeMCP()
    service = OneTimeRuleCleanupService(mcp, local_now=now_before_grace, grace_minutes=10)
    outcome = await service.run()

    assert [item["appId"] for item in outcome.deleted] == ["4210"]
    assert all(item["appId"] != "4211" for item in outcome.deleted)


@pytest.mark.asyncio
async def test_cleanup_continues_after_one_soft_delete_failure() -> None:
    mcp = FakeMCP(fail_app="4210")
    service = OneTimeRuleCleanupService(mcp, local_now=local_now, grace_minutes=10)

    outcome = await service.run()

    assert [item["appId"] for item in outcome.failed] == ["4210"]
    assert [item["appId"] for item in outcome.deleted] == ["4211"]


@pytest.mark.asyncio
async def test_cleanup_refuses_all_deletes_when_rule_list_fails() -> None:
    mcp = FakeMCP(list_failure=True)
    service = OneTimeRuleCleanupService(mcp, local_now=local_now, grace_minutes=10)

    outcome = await service.run()

    assert outcome.list_error
    assert not outcome.deleted
    assert [name for name, _args in mcp.calls] == ["hub_read_rules"]

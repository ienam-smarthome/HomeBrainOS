from datetime import datetime, timezone

import pytest

from mcp_client import MCPToolResult
from rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService


class FakeMCP:
    async def call_tool(self, name, arguments):
        if name == "hub_get_info":
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={"success": True, "timeZone": "Europe/London"},
            )
        raise RuntimeError(name)


@pytest.mark.asyncio
async def test_relative_schedule_uses_hub_timezone_not_utc_container_clock():
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *_args, **_kwargs: None,
        now=lambda: datetime(2026, 10, 3, 8, 42, 0, tzinfo=timezone.utc),
    )

    # Avoid exercising device/rule I/O: intercept the second, authoritative
    # intent pass by replacing the resolver-facing portion after timezone work.
    hub_now, name, source = await service._hub_timezone.now_in_hub_timezone(service._now)
    intent = service._intent("block Google TV after 1 min", now=hub_now)

    assert name == "Europe/London"
    assert source == "hub_get_info"
    assert hub_now.isoformat().startswith("2026-10-03T09:42:00+01:00")
    assert intent is not None
    assert intent.start_time == "2026-10-03T09:43:00"


def test_one_time_clock_uses_supplied_hub_local_now_for_next_occurrence():
    service = RuleAuthoringService(
        object(),
        lambda *_args, **_kwargs: None,
        now=lambda: datetime(2026, 10, 3, 8, 42, 0, tzinfo=timezone.utc),
    )
    local_now = datetime.fromisoformat("2026-10-03T09:42:00+01:00")
    intent = service._intent("turn on Hallway Light 1 at 10am", now=local_now)
    assert intent is not None
    assert intent.start_time == "2026-10-03T10:00:00"

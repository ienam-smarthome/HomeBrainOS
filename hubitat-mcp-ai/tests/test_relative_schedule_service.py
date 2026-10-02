from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult
from rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService


TARGET = "Block Media-Google-TV-Streamer"


class FakeMCP:
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if name == "hub_read_devices":
            return MCPToolResult(
                data={
                    "success": True,
                    "devices": [
                        {
                            "id": "6923",
                            "label": TARGET,
                            "name": TARGET,
                            "capabilities": ["Switch"],
                            "commands": ["on", "off", "blockInternet", "allowInternet"],
                        }
                    ],
                },
                is_error=False,
            )
        if name == "hub_read_rules":
            return MCPToolResult(data={"success": True, "rules": []}, is_error=False)
        raise AssertionError(f"Unexpected tool: {name} {arguments}")


@pytest.mark.asyncio
async def test_relative_block_schedule_builds_one_time_rule_without_delay_action() -> None:
    evidence: list[tuple[Any, ...]] = []
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *args, **kwargs: evidence.append((args, kwargs)),
        now=lambda: datetime(2026, 10, 2, 22, 25, 12),
    )

    decision = await service.propose(
        f"block {TARGET} after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.message is None
    assert decision.rule_names == ("Block Media Google TV Streamer (One-time 2026-10-02 22:26)",)
    assert len(decision.actions) == 2

    create = decision.actions[0]
    payload = create["args"]
    assert payload["addTrigger"] == {
        "capability": "Certain Time (and optional date)",
        "time": "A specific time",
        "atTime": "2026-10-02T22:26:12",
    }
    assert payload["addAction"] == {
        "capability": "runCommand",
        "deviceIds": ["6923"],
        "capabilityFilter": "Switch",
        "command": "blockInternet",
    }
    assert payload["addAction"].get("minutes") is None

    pause = decision.actions[1]["args"]["addAction"]
    assert pause["capability"] == "pauseRule"

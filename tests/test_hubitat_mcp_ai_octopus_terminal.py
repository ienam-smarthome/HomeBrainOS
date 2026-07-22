from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_focus_octopus_energy import (  # noqa: E402
    install_control_focus_octopus_energy,
)
from mcp_client import MCPToolResult  # noqa: E402


class FakeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def invalidate(self, _category: str) -> None:
        return None

    async def supported_arguments(self, _name: str, desired: dict) -> dict:
        return dict(desired)

    async def get_tool(self, _name: str):
        return None

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, dict(arguments)))
        devices = [
            {
                "id": "7433",
                "label": "Octopus Meter Today",
                "room": "Octopus Energy",
                "currentStates": {
                    "Health Status": "online",
                    "Value": "4.8 kWh",
                    "Value Str": "4.8 kWh",
                },
                "attributes": {
                    "friendly_name": "Octopus Live Meter Display Today"
                },
            },
            {
                "id": "7434",
                "label": "Octopus Meter Power",
                "room": "Octopus Energy",
                "currentStates": {"Value": "173 W", "Value Str": "173 W"},
                "attributes": {
                    "friendly_name": "Octopus Live Meter Display Power"
                },
            },
        ]
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={"devices": devices},
            is_error=False,
        )


def test_octopus_meter_today_is_terminal_and_reads_real_hubitat_label():
    planner_calls: list[str] = []

    async def unified_planner(request):
        planner_calls.append(request.query)
        return {"route": "ollama+mcp", "message": "Incorrect AI answer"}

    application = SimpleNamespace(
        ask=unified_planner,
        mcp=FakeMCP(),
        VERSION="test-version",
    )
    install_control_focus_octopus_energy(application)

    answer = asyncio.run(
        application.ask(SimpleNamespace(query="octopus meter today"))
    )

    assert planner_calls == []
    assert answer["route"] == "mcp-octopus-summary"
    assert answer["model"] is None
    assert answer["success"] is True
    assert {
        "id": "7433",
        "label": "Octopus Meter Today",
        "period": "today",
        "value": "4.8 kWh",
        "room": "Octopus Energy",
    } in answer["octopus_displays"]
    assert "4.8 kWh" in answer["message"]

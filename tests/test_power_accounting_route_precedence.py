from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import _answer_terminal_entity_read
from mcp_client import MCPToolResult


ROWS = [
    {
        "id": "whole",
        "label": "Octopus Meter Current Power",
        "attributes": {
            "value": {
                "currentValue": "315 W",
            }
        },
    },
    {
        "id": "fridge",
        "label": "Fridge",
        "attributes": {
            "power": {
                "currentValue": 79,
                "unit": "W",
            }
        },
    },
    {
        "id": "freezer",
        "label": "Freezer",
        "attributes": {
            "power": {
                "currentValue": 81,
                "unit": "W",
            }
        },
    },
]


class MCP:
    def __init__(self):
        self.calls = []

    async def supported_arguments(self, _name, desired):
        return dict(desired)

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={"devices": ROWS},
            is_error=False,
        )


def test_power_accounting_precedes_generic_entity_resolution():
    mcp = MCP()
    application = SimpleNamespace(mcp=mcp)

    answer = asyncio.run(
        _answer_terminal_entity_read(
            application,
            "How much power is unaccounted for?",
        )
    )

    assert answer is not None
    assert answer["route"] == "mcp-power-accounting"
    assert answer["intent"] == "verified-power-accounting"
    assert answer["whole_house_power_w"] == 315
    assert answer["monitored_device_power_w"] == 160
    assert answer["unaccounted_power_w"] == 155

    assert "could not find a device" not in answer["message"].lower()
    assert "unaccounted for" not in answer.get(
        "device_label",
        "",
    ).lower()

    assert len(mcp.calls) == 1
    assert mcp.calls[0][0] == "hub_list_devices"


def test_normal_named_power_device_read_is_not_power_accounting():
    application = SimpleNamespace()

    # This assertion protects the routing predicate without requiring a full
    # device inventory fixture.
    from power_accounting import is_power_accounting_query

    assert not is_power_accounting_query(
        "How much power is Fridge using?"
    )

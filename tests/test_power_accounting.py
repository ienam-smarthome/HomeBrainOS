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

from mcp_client import MCPToolResult
from power_accounting import (
    PowerAccountingService,
    is_power_accounting_query,
)


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
        "room": "Appliances",
        "attributes": {
            "power": {
                "currentValue": 79,
                "unit": "W",
            }
        },
    },
    {
        "id": "freezer",
        "label": "Freezer (MQTT)",
        "room": "Appliances",
        "attributes": {
            "power": {
                "currentValue": 81,
                "unit": "W",
            }
        },
    },
    {
        "id": "computer",
        "label": "Computer",
        "room": "Multimedia",
        "attributes": {
            "power": {
                "currentValue": 37,
                "unit": "W",
            }
        },
    },
    {
        "id": "idle",
        "label": "TV",
        "attributes": {
            "power": {
                "currentValue": 0,
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


def service():
    mcp = MCP()
    application = SimpleNamespace(mcp=mcp)
    return PowerAccountingService(application), mcp


def test_power_accounting_query_matching():
    assert is_power_accounting_query(
        "How much power is unaccounted for?"
    )
    assert is_power_accounting_query(
        "Compare whole house power with monitored devices"
    )
    assert is_power_accounting_query(
        "Why is my electricity usage high?"
    )
    assert not is_power_accounting_query(
        "show power devices"
    )
    assert not is_power_accounting_query(
        "show Octopus meter"
    )


def test_power_accounting_uses_one_shared_detailed_read():
    reader, mcp = service()

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    assert len(mcp.calls) == 1
    assert mcp.calls[0][0] == "hub_list_devices"
    assert mcp.calls[0][1]["detailed"] is True
    assert mcp.calls[0][1]["format"] == "detailed"

    assert result["whole_house_power_w"] == 315
    assert result["monitored_device_power_w"] == 197
    assert result["unaccounted_power_w"] == 118
    assert round(result["coverage_percent"], 1) == 62.5
    assert result["active_reading_count"] == 3
    assert result["idle_reading_count"] == 1


def test_whole_house_meter_is_not_added_to_device_total():
    reader, _mcp = service()

    result = asyncio.run(
        reader.answer(
            "Compare Octopus with monitored devices"
        )
    )

    assert result["monitored_device_power_w"] == 197
    assert result["whole_house_meter"]["label"] == (
        "Octopus Meter Current Power"
    )
    assert "315 W" in result["message"]
    assert "197 W" in result["message"]
    assert "118 W" in result["message"]


def test_accounting_lists_largest_individual_loads():
    reader, _mcp = service()

    result = asyncio.run(
        reader.answer(
            "Why is my electricity usage high?"
        )
    )

    assert [
        item["label"]
        for item in result["active_power_readings"]
    ] == [
        "Freezer (MQTT)",
        "Fridge",
        "Computer",
    ]

def test_power_accounting_questions_bypass_general_ai():
    from hybrid_assistant_mode import is_hybrid_ai_query

    assert not is_hybrid_ai_query(
        "Why is electricity usage high right now?"
    )
    assert not is_hybrid_ai_query(
        "How much power is unaccounted for?"
    )
    assert not is_hybrid_ai_query(
        "Compare whole house power with monitored devices"
    )


def test_unrelated_energy_advice_remains_an_ai_question():
    from hybrid_assistant_mode import is_hybrid_ai_query

    assert is_hybrid_ai_query(
        "How can I reduce my electricity bill?"
    )
    assert is_hybrid_ai_query(
        "Suggest ways to improve energy efficiency"
    )

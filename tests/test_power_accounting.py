from __future__ import annotations
import json

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

def test_accounting_preserves_fractional_total_precision():
    rows = [
        {
            "id": "whole",
            "label": "Octopus Meter Current Power",
            "attributes": {
                "value": {"currentValue": "229 W"},
            },
        },
        {
            "id": "one",
            "label": "Fridge",
            "attributes": {
                "power": {
                    "currentValue": 86,
                    "unit": "W",
                }
            },
        },
        {
            "id": "two",
            "label": "Fan",
            "attributes": {
                "power": {
                    "currentValue": 14.6,
                    "unit": "W",
                }
            },
        },
        {
            "id": "three",
            "label": "Socket",
            "attributes": {
                "power": {
                    "currentValue": 60.8,
                    "unit": "W",
                }
            },
        },
    ]

    class FractionMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={"devices": rows},
                is_error=False,
            )

    reader = PowerAccountingService(
        SimpleNamespace(mcp=FractionMCP())
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    assert result["monitored_device_power_w"] == 161.4
    assert result["unaccounted_power_w"] == 67.6
    assert "161.4 W" in result["message"]
    assert "67.6 W" in result["message"]


def test_structured_octopus_power_precedes_display_text():
    rows = [
        {
            "id": "whole",
            "label": "Octopus Meter Current Power",
            "attributes": {
                "power": {
                    "currentValue": 229,
                    "unit": "W",
                },
                "display": {
                    "currentValue": (
                        "Power 999 W, cost 12.34, rate 22.5"
                    ),
                },
            },
        },
        {
            "id": "load",
            "label": "Fridge",
            "attributes": {
                "power": {
                    "currentValue": 100,
                    "unit": "W",
                }
            },
        },
    ]

    class StructuredMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={"devices": rows},
                is_error=False,
            )

    reader = PowerAccountingService(
        SimpleNamespace(mcp=StructuredMCP())
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    assert result["whole_house_power_w"] == 229
    assert result["whole_house_value_source"] == (
        "structured-power-attribute"
    )


def test_duplicate_octopus_meter_prefers_newest_exact_label():
    rows = [
        {
            "id": "old",
            "label": "Octopus Meter Current Power",
            "lastActivity": "2026-07-25T20:00:00Z",
            "attributes": {
                "power": {
                    "currentValue": 800,
                    "unit": "W",
                }
            },
        },
        {
            "id": "new",
            "label": "Octopus Meter Current Power",
            "lastActivity": "2026-07-25T20:01:00Z",
            "attributes": {
                "power": {
                    "currentValue": 229,
                    "unit": "W",
                }
            },
        },
        {
            "id": "load",
            "label": "Fridge",
            "lastActivity": "2026-07-25T20:00:50Z",
            "attributes": {
                "power": {
                    "currentValue": 100,
                    "unit": "W",
                }
            },
        },
    ]

    class DuplicateMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={"devices": rows},
                is_error=False,
            )

    reader = PowerAccountingService(
        SimpleNamespace(mcp=DuplicateMCP())
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    assert result["whole_house_power_w"] == 229
    assert result["whole_house_meter"]["id"] == "new"
    assert result["reading_quality"]["quality"] == "good"
    assert (
        result["reading_quality"]["comparison_skew_seconds"]
        == 10
    )
    assert (
        result["reading_quality"]["active_reading_skew_seconds"]
        == 0
    )


def test_historical_energy_questions_are_not_live_accounting():
    assert not is_power_accounting_query(
        "Why was electricity usage high today?"
    )
    assert not is_power_accounting_query(
        "Why was my bill high this month?"
    )
    assert not is_power_accounting_query(
        "Compare energy usage in kWh"
    )
    assert is_power_accounting_query(
        "Why is electricity usage high right now?"
    )

def test_nested_sparse_duplicate_does_not_replace_complete_device():
    rows = {
        "devices": [
            {
                "id": "whole",
                "label": "Octopus Meter Current Power",
                "lastActivity": "2026-07-25T21:00:00Z",
                "attributes": {
                    "value": {
                        "currentValue": "229 W",
                    }
                },
                "nested": {
                    "id": "whole",
                    "label": "Octopus Meter Current Power",
                },
            },
            {
                "id": "fridge",
                "label": "Fridge",
                "lastActivity": "2026-07-25T20:59:55Z",
                "attributes": {
                    "power": {
                        "currentValue": 86.4,
                        "unit": "W",
                    }
                },
                "nested": {
                    "id": "fridge",
                    "label": "Fridge",
                },
            },
        ]
    }

    class NestedMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data=rows,
                is_error=False,
            )

    reader = PowerAccountingService(
        SimpleNamespace(mcp=NestedMCP())
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    assert result["whole_house_power_w"] == 229
    assert result["monitored_device_power_w"] == 86.4
    assert result["unaccounted_power_w"] == 142.6
    assert result["active_power_readings"][0]["id"] == "fridge"

    import json

    technical = json.loads(result["technical"])
    assert technical["extracted_device_row_count"] == 2

def test_idle_stale_reading_does_not_define_comparison_quality():
    rows = {
        "devices": [
            {
                "id": "whole",
                "label": "Octopus Meter Current Power",
                "attributes": {
                    "value": {
                        "currentValue": "367 W",
                    }
                },
            },
            {
                "id": "tv",
                "label": "TV",
                "lastActivity": "2026-07-25T23:00:30+01:00",
                "attributes": {
                    "power": {
                        "currentValue": 87,
                        "unit": "W",
                    }
                },
            },
            {
                "id": "fridge",
                "label": "Fridge",
                "lastActivity": "2026-07-25T22:59:01+01:00",
                "attributes": {
                    "power": {
                        "currentValue": 79,
                        "unit": "W",
                    }
                },
            },
            {
                "id": "idle",
                "label": "Fan Switch",
                "lastActivity": "2026-07-25T22:29:59+01:00",
                "attributes": {
                    "power": {
                        "currentValue": 0,
                        "unit": "W",
                    }
                },
            },
        ]
    }

    class TimestampMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data=rows,
                is_error=False,
            )

    reader = PowerAccountingService(
        SimpleNamespace(mcp=TimestampMCP())
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    quality = result["reading_quality"]

    assert quality["quality"] == "unknown"
    assert quality["reason"] == (
        "whole-house meter timestamp unavailable"
    )
    assert quality["comparison_skew_seconds"] is None

    assert quality["active_reading_timestamp_count"] == 2
    assert quality["active_reading_skew_seconds"] == 89

    assert quality["all_reading_timestamp_count"] == 3
    assert quality["all_reading_skew_seconds"] == 1831

    assert (
        "Comparison timestamp quality is unknown: "
        "whole-house meter timestamp unavailable."
        in result["message"]
    )
    assert "Active monitored readings span 89 seconds." in result["message"]


def test_meter_timestamp_controls_comparison_quality():
    rows = {
        "devices": [
            {
                "id": "whole",
                "label": "Octopus Meter Current Power",
                "lastActivity": "2026-07-25T23:01:00+01:00",
                "attributes": {
                    "value": {
                        "currentValue": "229 W",
                    }
                },
            },
            {
                "id": "load-one",
                "label": "Fridge",
                "lastActivity": "2026-07-25T23:00:50+01:00",
                "attributes": {
                    "power": {
                        "currentValue": 86,
                        "unit": "W",
                    }
                },
            },
            {
                "id": "load-two",
                "label": "Computer",
                "lastActivity": "2026-07-25T23:00:40+01:00",
                "attributes": {
                    "power": {
                        "currentValue": 40,
                        "unit": "W",
                    }
                },
            },
        ]
    }

    class TimestampMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data=rows,
                is_error=False,
            )

    reader = PowerAccountingService(
        SimpleNamespace(mcp=TimestampMCP())
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    quality = result["reading_quality"]

    assert quality["quality"] == "good"
    assert quality["reason"] is None
    assert quality["comparison_skew_seconds"] == 20
    assert quality["active_reading_skew_seconds"] == 10
    assert (
        "Comparison timestamp quality is Good "
        "with a maximum meter-to-device skew of 20 seconds."
        in result["message"]
    )

def test_power_accounting_display_has_breakdown_tile():
    rows = {
        "devices": [
            {
                "id": "whole",
                "label": "Octopus Meter Current Power",
                "attributes": {
                    "value": {
                        "currentValue": "362 W",
                    }
                },
            },
            {
                "id": "tv",
                "label": "TV",
                "attributes": {
                    "power": {
                        "currentValue": 89,
                        "unit": "W",
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
                        "currentValue": 74,
                        "unit": "W",
                    }
                },
            },
        ]
    }

    class BreakdownMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data=rows,
                is_error=False,
            )

    reader = PowerAccountingService(
        SimpleNamespace(mcp=BreakdownMCP())
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    items = result["display"]["items"]
    breakdown = items[0]

    assert breakdown["title"] == "Power breakdown"
    assert breakdown["value"] == "242 W"
    assert "3 active monitored devices" in breakdown["subtitle"]
    assert "TV 89 W" in breakdown["subtitle"]
    assert "Fridge 79 W" in breakdown["subtitle"]
    assert "Freezer 74 W" in breakdown["subtitle"]

    assert items[1]["title"] == "TV"
    assert items[2]["title"] == "Fridge"
    assert items[3]["title"] == "Freezer"

def test_empty_projected_snapshot_retries_plain_inventory():
    projected = {"devices": []}
    fallback = {
        "devices": [
            {
                "id": "whole",
                "label": "Octopus Meter Current Power",
                "attributes": {
                    "value": {
                        "currentValue": "200 W",
                    }
                },
            },
            {
                "id": "load",
                "label": "Fridge",
                "attributes": {
                    "power": {
                        "currentValue": 80,
                        "unit": "W",
                    }
                },
            },
        ]
    }

    class RetryMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            data = (
                fallback
                if arguments == {
                    "detailed": True,
                    "format": "detailed",
                }
                else projected
            )
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data=data,
                is_error=False,
            )

    mcp = RetryMCP()
    reader = PowerAccountingService(
        SimpleNamespace(mcp=mcp)
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    assert len(mcp.calls) == 2
    assert mcp.calls[1] == (
        "hub_list_devices",
        {
            "detailed": True,
            "format": "detailed",
        },
    )
    assert result["success"] is True
    assert result["whole_house_power_w"] == 200
    assert result["monitored_device_power_w"] == 80
    assert result["unaccounted_power_w"] == 120

    technical = json.loads(result["technical"])
    assert technical["projected_device_row_count"] == 0
    assert technical["snapshot_retry_used"] is True
    assert technical["retry_device_row_count"] == 2
    assert technical["extracted_device_row_count"] == 2


def test_double_empty_snapshot_returns_unavailable_not_zero():
    class EmptyMCP(MCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={"devices": []},
                is_error=False,
            )

    mcp = EmptyMCP()
    reader = PowerAccountingService(
        SimpleNamespace(mcp=mcp)
    )

    result = asyncio.run(
        reader.answer(
            "How much power is unaccounted for?"
        )
    )

    assert len(mcp.calls) == 2
    assert result["success"] is False
    assert result["whole_house_power_w"] is None
    assert result["monitored_device_power_w"] is None
    assert result["unaccounted_power_w"] is None
    assert result["coverage_percent"] is None
    assert "No 0 W total has been assumed" in result["message"]

    display = result["display"]
    assert display["metrics"][0]["value"] == "Unavailable"
    assert (
        display["items"][0]["title"]
        == "Device snapshot unavailable"
    )

    technical = json.loads(result["technical"])
    assert technical["snapshot_retry_used"] is True
    assert technical["extracted_device_row_count"] == 0
    assert technical["snapshot_status"] == "unavailable"

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

from control_focus_octopus_energy import OctopusLiveMeterSummary
from mcp_client import MCPToolResult


OCTOPUS_ROWS = [
    {
        "id": "7430",
        "label": "Octopus Meter Energy Today",
        "attributes": {},
    },
    {
        "id": "7434",
        "label": "Octopus Meter Current Power",
        "attributes": {},
    },
]


class RecordingClient:
    def __init__(self):
        self.calls = []

    async def supported_arguments(self, name, arguments):
        return dict(arguments)

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))

        if name == "hub_list_devices":
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={"devices": OCTOPUS_ROWS},
                is_error=False,
            )

        device_id = str(arguments["deviceId"])
        value = (
            "9.18 kWh (£2.97)"
            if device_id == "7430"
            else "214 W"
        )
        label = next(
            row["label"]
            for row in OCTOPUS_ROWS
            if row["id"] == device_id
        )
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "device": {
                    "id": device_id,
                    "label": label,
                    "attributes": {
                        "display": {"value": value}
                    },
                }
            },
            is_error=False,
        )


def service():
    client = RecordingClient()
    application = SimpleNamespace(
        mcp=client,
        device_index=None,
    )
    return OctopusLiveMeterSummary(application), client


def test_octopus_family_uses_one_inventory_read():
    reader, client = service()

    result = asyncio.run(
        reader.answer("show Octopus meter")
    )

    inventory = [
        call
        for call in client.calls
        if call[0] == "hub_list_devices"
    ]
    details = [
        call
        for call in client.calls
        if call[0] == "hub_get_device"
    ]

    assert len(inventory) == 1
    assert len(details) == 2
    assert result["success"] is True


def test_octopus_today_uses_same_grouped_reader():
    reader, client = service()

    result = asyncio.run(
        reader.answer("show Octopus energy today")
    )

    assert result["success"] is True
    assert result["route"] == "mcp-octopus-summary"
    assert "9.18 kWh" in result["message"]
    assert len(
        [
            call
            for call in client.calls
            if call[0] == "hub_list_devices"
        ]
    ) == 1


def test_octopus_reader_does_not_invalidate_device_cache():
    source = (
        APP_DIR / "control_focus_octopus_energy.py"
    ).read_text(encoding="utf-8")

    method = source.split(
        "async def _read_family",
        1,
    )[1].split(
        "async def _read_by_ids",
        1,
    )[0]

    assert 'invalidate("devices")' not in method

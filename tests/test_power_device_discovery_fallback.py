from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import power_accounting
from mcp_client import MCPToolResult
from power_device_discovery_fallback import (
    install_power_device_discovery_fallback,
    power_candidate_score,
    targeted_power_detail_rows,
)


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_candidate_scoring_prioritises_real_metering_devices():
    assert power_candidate_score(
        {
            "id": "1",
            "label": "Fridge",
            "deviceType": "Tasmota MQTT Power Meter",
        }
    ) >= 800
    assert power_candidate_score(
        {
            "id": "2",
            "label": "Washing Machine",
            "deviceType": "Generic MQTT Device",
        }
    ) >= 500
    assert power_candidate_score(
        {
            "id": "3",
            "label": "Dehumidifier 2",
            "deviceType": "Generic Switch",
        }
    ) >= 250
    assert power_candidate_score(
        {
            "id": "4",
            "label": "Block Google-TV-Streamer",
            "deviceType": "Virtual Switch",
        }
    ) == 0


class Client:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        device_id = str(arguments["deviceId"])
        values = {
            "fridge": ("Fridge", 72),
            "freezer": ("Freezer", 81),
            "washer": ("Washing Machine", 4.2),
            "block": ("Block Tablet", None),
        }
        label, value = values[device_id]
        attributes = {} if value is None else {"power": value}
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "device": {
                    "id": device_id,
                    "label": label,
                    "attributes": attributes,
                }
            },
            is_error=False,
        )


def test_targeted_fallback_discovers_appliance_power_readings():
    client = Client()
    inventory = [
        {"id": "block", "label": "Block Tablet", "deviceType": "Virtual Switch"},
        {"id": "washer", "label": "Washing Machine", "deviceType": "MQTT Device"},
        {"id": "fridge", "label": "Fridge", "deviceType": "Tasmota Power Meter"},
        {"id": "freezer", "label": "Freezer", "deviceType": "MQTT Device"},
    ]

    rows, diagnostic = asyncio.run(targeted_power_detail_rows(client, inventory))

    assert diagnostic["candidate_count"] == 3
    assert diagnostic["candidate_labels"] == ["Fridge", "Freezer", "Washing Machine"]
    assert diagnostic["numeric_power_reading_count"] == 3
    assert [call[1]["deviceId"] for call in client.calls] == [
        "fridge",
        "freezer",
        "washer",
    ]
    assert {row["label"] for row in rows} == {
        "Fridge",
        "Freezer",
        "Washing Machine",
    }


def test_installer_replaces_only_power_detail_fallback():
    original = power_accounting._targeted_power_detail_rows
    try:
        result = install_power_device_discovery_fallback()
        assert result is None
        assert power_accounting._targeted_power_detail_rows is targeted_power_detail_rows
    finally:
        power_accounting._targeted_power_detail_rows = original


def test_public_entrypoint_installs_fallback_without_ask_wrapper():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "install_power_device_discovery_fallback" in source
    assert "power_device_discovery_fallback = install_power_device_discovery_fallback()" in source
    assert 'capture(\n    "power-device-discovery"' not in source

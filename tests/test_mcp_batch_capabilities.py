from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import HubitatMCPClient, MCPTool  # noqa: E402


def gateway_tool(name: str, description: str) -> MCPTool:
    return MCPTool(
        name,
        description,
        {
            "type": "object",
            "properties": {
                "tool": {"type": "string"},
                "args": {"type": "object"},
            },
        },
    )


@pytest.mark.asyncio
async def test_detects_batch_command_and_multi_device_poll_from_gateway_catalog() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    client._tools = {
        "hub_manage_devices": gateway_tool(
            "hub_manage_devices",
            (
                "hub_call_device_command: Send one command, or batch up to 20 "
                "with commands: [{deviceId, command, parameters?}]"
            ),
        ),
        "hub_read_devices": gateway_tool(
            "hub_read_devices",
            (
                "hub_get_device_attribute: Read one attribute, or block-poll "
                "deviceIds + mode any/all."
            ),
        ),
    }

    try:
        assert await client.supports_device_command_batch() is True
        assert await client.supports_multi_device_attribute_poll() is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_batch_feature_detection_fails_closed_on_older_catalog() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    client._tools = {
        "hub_manage_devices": gateway_tool(
            "hub_manage_devices",
            "hub_call_device_command: Send one command to one device.",
        ),
        "hub_read_devices": gateway_tool(
            "hub_read_devices",
            "hub_get_device_attribute: Read one device attribute.",
        ),
    }

    try:
        assert await client.supports_device_command_batch() is False
        assert await client.supports_multi_device_attribute_poll() is False
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_batch_command_rollback_setting_disables_feature() -> None:
    client = HubitatMCPClient(
        "http://hubitat.test/mcp",
        batch_device_commands_enabled=False,
    )
    client._initialized = True
    client._tools = {
        "hub_manage_devices": gateway_tool(
            "hub_manage_devices",
            (
                "hub_call_device_command supports commands array for "
                "multiple devices."
            ),
        ),
    }

    try:
        assert await client.supports_device_command_batch() is False
    finally:
        await client.close()

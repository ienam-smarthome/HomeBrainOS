"""Numeric Hubitat references must use ID reads, never labelFilter lookups."""
from pathlib import Path
import sys

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService
from mcp_client import MCPToolResult
from agent_prompt_policy import build_system_prompt


class IDClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name == "hub_read_devices"
        assert arguments == {
            "tool": "hub_get_device", "args": {"deviceId": "7334"}
        }
        if isinstance(self.result, Exception):
            raise self.result
        return MCPToolResult(
            name, arguments, {}, "ok", self.result,
            is_error=bool(self.result.get("isError")),
        )


@pytest.mark.asyncio
async def test_fp2_parent_id_fetched_directly_instead_of_label():
    client = IDClient({
        "id": "7334", "label": "FP2 Livingroom",
        "room": "Living Room",
        "attributes": {"healthStatus": "offline", "hapStatus": "connecting (live)"},
    })
    receipts = []
    service = DeviceQueryService(client, lambda *a, **kw: receipts.append((a, kw)))
    response = await service.resolve_device({"name": "7334"})
    assert response.data["matched"] is True
    assert response.data["deviceId"] == "7334"
    assert response.data["target"]["attributes"]["healthStatus"] == "offline"
    assert response.data["label"] == "FP2 Livingroom"
    assert response.data["reason"] == "Authoritative Hubitat numeric device ID read."
    assert response.data["attempts"] == [{"source": "device_id_direct", "count": 1}]
    assert len(client.calls) == 1
    assert receipts[0][1]["supports_live_claim"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [
    {"success": False, "isError": True, "error": "Device not selected"},
    {"id": "9999", "label": "Different device"},
    {},
])
async def test_unverified_numeric_parent_is_not_declared_missing(result):
    client = IDClient(result)
    service = DeviceQueryService(client, lambda *a, **kw: None)
    response = await service.resolve_device({"name": "7334"})
    assert response.data["matched"] is False
    assert response.data["complete"] is False
    assert response.data["deviceId"] == "7334"
    assert "unverified" in response.data["reason"]
    assert "missing" not in response.data["reason"].lower()
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_numeric_id_transport_error_fails_closed():
    client = IDClient(TimeoutError("Hubitat MCP unavailable"))
    service = DeviceQueryService(client, lambda *a, **kw: None)
    response = await service.resolve_device({"name": "7334"})
    assert response.data["matched"] is False
    assert response.data["complete"] is False
    assert response.data["attempts"] == [{"source": "device_id_direct", "count": 0}]
    assert "unverified" in response.data["reason"]


def test_agent_prompt_keeps_rule_config_separate_from_historical_proof():
    policy = build_system_prompt("", "")
    assert 'hub_get_device(deviceId=' in policy
    assert 'labelFilter="7334"' in policy
    assert "potential" in policy.lower()
    assert "historical" in policy.lower()
    assert "required expression" in policy.lower()
    assert "retained" in policy.lower()

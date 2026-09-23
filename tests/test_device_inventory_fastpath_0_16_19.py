from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from deterministic_tool_presenter import present_tool_result  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402


DEVICES = [
    {
        "id": "1",
        "label": "Bathroom Light",
        "room": "Bathroom",
        "capabilities": ["Switch", "Light"],
    },
    {
        "id": "2",
        "label": "Bathroom Motion",
        "room": "Bathroom",
        "capabilities": ["MotionSensor"],
    },
    {
        "id": "3",
        "label": "Bedroom Meter",
        "roomName": "Bedroom 1",
        "capabilities": ["TemperatureMeasurement"],
    },
    {
        "id": "4",
        "label": "Hub Info (C8 Pro)",
        "capabilities": ["TemperatureMeasurement"],
    },
]


class _InventoryMCP:
    def __init__(self) -> None:
        self.identity_reads = 0
        self.tool_calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return []

    async def get_device_identities(self):
        self.identity_reads += 1
        return [dict(item) for item in DEVICES]

    async def call_tool(self, name: str, arguments: dict):
        self.tool_calls.append((name, arguments))
        raise AssertionError("inventory fast path must not page remote hub_list_devices")


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("provider must not be called for deterministic inventory")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_device_inventory_groups_complete_identity_by_room() -> None:
    mcp = _InventoryMCP()
    service = DeviceQueryService(mcp, lambda *_a, **_k: None)

    result = await service.device_inventory({})

    assert result.is_error is False
    assert result.data["count"] == 4
    assert result.data["complete"] is True
    assert result.data["read_scope"] == "authoritative device identity"
    assert [room["room"] for room in result.data["rooms"]] == [
        "Bathroom",
        "Bedroom 1",
        "Unassigned",
    ]
    bathroom = result.data["rooms"][0]
    assert bathroom["count"] == 2
    assert [item["label"] for item in bathroom["devices"]] == [
        "Bathroom Light",
        "Bathroom Motion",
    ]
    assert mcp.identity_reads == 1
    assert mcp.tool_calls == []


def test_device_inventory_presenter_renders_every_room_without_truncation() -> None:
    data = {
        "count": 4,
        "rooms": [
            {
                "room": "Bathroom",
                "count": 2,
                "devices": [
                    {"id": "1", "label": "Bathroom Light"},
                    {"id": "2", "label": "Bathroom Motion"},
                ],
            },
            {
                "room": "Bedroom 1",
                "count": 1,
                "devices": [{"id": "3", "label": "Bedroom Meter"}],
            },
            {
                "room": "Unassigned",
                "count": 1,
                "devices": [{"id": "4", "label": "Hub Info (C8 Pro)"}],
            },
        ],
    }

    message = present_tool_result("homebrain_device_inventory", data)

    assert message is not None
    assert message.startswith("4 Hubitat devices across 3 room groups.")
    assert "**Bathroom (2):** Bathroom Light, Bathroom Motion" in message
    assert "**Bedroom 1 (1):** Bedroom Meter" in message
    assert "**Unassigned (1):** Hub Info (C8 Pro)" in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "list devices",
        "show all devices",
        "device inventory",
        "what devices do I have?",
    ],
)
async def test_inventory_requests_skip_model_and_remote_device_pagination(prompt: str) -> None:
    mcp = _InventoryMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(prompt)

    assert ai.requests == []
    assert mcp.tool_calls == []
    assert mcp.identity_reads == 1
    assert outcome.metrics["counters"].get("model_rounds", 0) == 0
    assert outcome.message.startswith("4 Hubitat devices across 3 room groups.")
    assert "Bathroom Light" in outcome.message
    assert "Bedroom Meter" in outcome.message
    assert "Hub Info (C8 Pro)" in outcome.message

    inventory_receipts = [
        receipt
        for receipt in outcome.evidence
        if receipt.get("tool") == "homebrain_device_inventory"
    ]
    assert len(inventory_receipts) == 1
    assert inventory_receipts[0]["supports_live_claim"] is False

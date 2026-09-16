from __future__ import annotations

from typing import Any

import pytest

from device_query_service import DeviceQueryService
from mcp_client import HubitatMCPClient


@pytest.mark.asyncio
async def test_active_rooms_falls_back_when_projected_records_omit_live_state() -> None:
    """Reproduce the live 0.10.433 failure at the real MCP-client boundary.

    The filtered request returns a non-empty device set but omits the detailed
    ``attributes`` state container. That must be treated as a projection-contract
    failure and fall back to the complete authoritative snapshot, never rendered
    as a confident "no rooms are active" result.
    """

    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        arguments = payload["params"]["arguments"]
        args = arguments.get("args") or {}
        if args.get("capabilityFilter"):
            return {
                "result": {
                    "structuredContent": {
                        "devices": [
                            {
                                "id": "1",
                                "label": "Projected Motion",
                                "room": "Living Room",
                                "capabilities": ["MotionSensor"],
                                # Deliberately no attributes/currentStates: this is
                                # the bad non-empty shape observed in 0.10.433.
                            }
                        ],
                        "count": 1,
                        "total": 1,
                    }
                }
            }
        return {
            "result": {
                "structuredContent": {
                    "devices": [
                        {
                            "id": "7",
                            "label": "Fallback Motion",
                            "room": "Office",
                            "capabilities": ["MotionSensor"],
                            "currentStates": {"motion": "active"},
                        }
                    ]
                }
            }
        }

    client._post = fake_post  # type: ignore[method-assign]
    receipts = []
    service = DeviceQueryService(
        client, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.active_rooms({})

    assert result.data["active_rooms"] == [
        {"name": "Office", "reasons": ["motion"]}
    ]
    assert result.data["count"] == 1
    assert len(posts) == 2
    projected_args = posts[0]["params"]["arguments"]["args"]
    assert "attributes" in projected_args["fields"]
    assert "currentStates" not in projected_args["fields"]
    assert posts[1]["params"]["arguments"] == {
        "tool": "hub_list_devices",
        "args": {},
    }
    # Only the complete fallback snapshot is recorded as authoritative evidence.
    assert len(receipts) == 1
    assert receipts[0][1]["summary"] == "1 source device records"

    await client.close()

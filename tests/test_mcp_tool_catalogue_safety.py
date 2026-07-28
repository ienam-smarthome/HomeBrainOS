from __future__ import annotations

import asyncio

from mcp_client import MCPTool
from mcp_tool_catalogue import build_mcp_tool_catalogue


class FakeCatalogueClient:
    server_info = {"name": "test"}

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                "hub_get_info",
                "Read hub information",
                {},
                annotations={"readOnlyHint": True, "destructiveHint": False},
            ),
            MCPTool(
                "hub_update_firmware",
                "Install firmware",
                {},
                annotations={"readOnlyHint": False, "destructiveHint": True},
            ),
            MCPTool(
                "hub_manage_rooms",
                "Includes hub_list_rooms, hub_create_room and hub_delete_room",
                {},
                annotations={"readOnlyHint": False, "destructiveHint": False},
            ),
        ]

    async def gateway_map(self, refresh: bool = False):
        return {
            "hub_list_rooms": "hub_manage_rooms",
            "hub_create_room": "hub_manage_rooms",
            "hub_delete_room": "hub_manage_rooms",
        }


def test_catalogue_reports_safety_for_visible_and_hidden_tools():
    data = asyncio.run(build_mcp_tool_catalogue(FakeCatalogueClient()))

    assert data["tool_safety"]["hub_get_info"] == "read"
    assert data["tool_safety"]["hub_update_firmware"] == "destructive"
    assert data["tool_safety"]["hub_list_rooms"] == "read"
    assert data["tool_safety"]["hub_create_room"] == "mutate"
    assert data["safety_counts"] == {
        "read": 2,
        "mutate": 1,
        "destructive": 2,
    }

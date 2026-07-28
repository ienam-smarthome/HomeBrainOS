from __future__ import annotations

import asyncio

from mcp_client import HubitatMCPClient
from mcp_tool_safety import (
    classify_tool_safety,
    effective_tool_name,
    requires_explicit_confirmation,
)


def test_server_annotations_are_authoritative():
    assert (
        classify_tool_safety(
            "custom_probe",
            annotations={"readOnlyHint": True, "destructiveHint": False},
        )
        == "read"
    )
    assert (
        classify_tool_safety(
            "custom_operation",
            annotations={"readOnlyHint": False, "destructiveHint": False},
        )
        == "mutate"
    )
    assert (
        classify_tool_safety(
            "custom_operation",
            annotations={"readOnlyHint": False, "destructiveHint": True},
        )
        == "destructive"
    )


def test_gateway_calls_are_classified_by_the_selected_leaf():
    arguments = {
        "tool": "hub_delete_device",
        "args": {"deviceId": "42", "confirm": True},
    }
    assert effective_tool_name("hub_manage_destructive_ops", arguments) == "hub_delete_device"
    assert classify_tool_safety("hub_manage_destructive_ops", arguments) == "destructive"
    assert classify_tool_safety("hub_manage_devices", {}) == "read"


def test_conditional_metric_snapshot_is_not_misclassified_as_a_read():
    assert classify_tool_safety("hub_get_metrics", {}) == "read"
    assert (
        classify_tool_safety("hub_get_metrics", {"recordSnapshot": True})
        == "mutate"
    )


def test_known_write_and_destructive_fallbacks_are_conservative():
    assert classify_tool_safety("hub_update_device") == "mutate"
    assert classify_tool_safety("hub_create_room") == "mutate"
    assert classify_tool_safety("hub_manage_mode", {"action": "activate"}) == "mutate"
    assert (
        classify_tool_safety("hub_manage_virtual_device", {"action": "create"})
        == "mutate"
    )
    assert classify_tool_safety("hub_update_package") == "destructive"


def test_destructive_calls_need_verbal_and_schema_confirmation():
    args = {"deviceId": "42", "confirm": True}
    assert requires_explicit_confirmation(
        "hub_delete_device", args, "Delete device 42"
    )
    assert requires_explicit_confirmation(
        "hub_delete_device",
        {"deviceId": "42"},
        "I confirm, proceed with deleting device 42",
    )
    assert not requires_explicit_confirmation(
        "hub_delete_device",
        args,
        "I confirm, proceed with deleting device 42",
    )


def test_normal_mutations_do_not_gain_destructive_confirmation_requirements():
    assert not requires_explicit_confirmation(
        "hub_call_device_command",
        {"deviceId": "5", "command": "on"},
        "Turn on Kitchen Light",
    )
    assert requires_explicit_confirmation(
        "hub_call_device_command",
        {"deviceId": "5", "command": "unlock"},
        "Unlock the front door",
    )


def test_mcp_client_preserves_server_safety_and_output_metadata():
    async def scenario():
        client = HubitatMCPClient("http://example.test/mcp")
        client._initialized = True

        async def fake_post(_payload, allow_empty=False):
            return {
                "result": {
                    "tools": [
                        {
                            "name": "hub_get_info",
                            "description": "Hub information",
                            "inputSchema": {"type": "object", "properties": {}},
                            "outputSchema": {
                                "type": "object",
                                "properties": {"success": {"type": "boolean"}},
                            },
                            "annotations": {
                                "readOnlyHint": True,
                                "destructiveHint": False,
                            },
                        }
                    ]
                }
            }

        client._post = fake_post
        try:
            tools = await client.list_tools(refresh=True)
        finally:
            await client.close()

        assert tools[0].annotations["readOnlyHint"] is True
        assert tools[0].output_schema["properties"]["success"]["type"] == "boolean"

    asyncio.run(scenario())

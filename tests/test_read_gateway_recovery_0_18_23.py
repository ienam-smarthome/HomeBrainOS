"""Regression: source+runtime reads must survive model gateway mismatch."""
from __future__ import annotations

from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_discovery_catalog import ToolDiscoveryCatalog


def read_gateway(name, *operations, description=""):
    return MCPTool(
        name,
        description or name,
        {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": list(operations)},
                "args": {"type": "object"},
            },
        },
    )


def plain_tool(name, description=""):
    return MCPTool(name, description or name, {"type":"object"})


def discovery(operation, gateway):
    return MCPToolResult(
        "hub_search_tools", {}, {}, "",
        {"results":[{"tool":operation,"gateway":gateway}]}, is_error=False,
    )


def test_wrong_history_gateway_rerouted_only_through_known_read_enum():
    catalog = ToolDiscoveryCatalog([
        plain_tool("hub_search_tools"),
        read_gateway("hub_read_diagnostics", "hub_get_logs"),
        read_gateway("hub_read_devices", "hub_get_device", "hub_list_device_events"),
    ])
    wrong = {"tool":"hub_list_device_events",
             "args":{"deviceId":7103,"hoursBack":24,"limit":100}}
    assert catalog.gateway_operation_error("hub_read_diagnostics", wrong)
    corrected = catalog.compatible_read_gateway("hub_read_diagnostics", wrong)
    assert corrected is not None
    assert corrected[0] == "hub_read_devices"
    assert corrected[1].name == "hub_read_devices"
    assert catalog.gateway_operation_error(corrected[0], wrong) is None


def test_wrong_logs_gateway_rerouted_from_live_discovery_not_guess():
    catalog = ToolDiscoveryCatalog([
        plain_tool("hub_search_tools"),
        plain_tool("hub_read_diagnostics", "Tools hub_get_logs and hub_get_stats"),
        read_gateway("hub_read_devices", "hub_get_device"),
    ])
    args = {"tool":"hub_get_logs",
            "args":{"deviceId":7103,"since":"24h","limit":100}}
    assert catalog.compatible_read_gateway("hub_read_devices", args) is None
    catalog.expand(discovery("hub_get_logs", "hub_read_diagnostics"),
                   query="hub_get_logs")
    resolved = catalog.compatible_read_gateway("hub_read_devices", args)
    assert resolved is not None
    assert resolved[0] == "hub_read_diagnostics"
    assert catalog.gateway_operation_error(resolved[0], args) is None


def test_authoritative_schema_enum_beats_outdated_prose_description():
    catalog = ToolDiscoveryCatalog([
        read_gateway(
            "hub_read_devices", "hub_get_device", "hub_list_device_events",
            description=(
                "Old guide lists hub_get_device and hub_get_device_attribute "
                "but omits the new history operation."
            ),
        ),
    ])
    args = {"tool":"hub_list_device_events", "args":{"deviceId":7103}}
    assert catalog.gateway_operation_error("hub_read_devices", args) is None


def test_ambiguous_mapping_does_not_automatically_choose():
    catalog = ToolDiscoveryCatalog([
        read_gateway("hub_read_devices", "hub_list_device_events"),
        read_gateway("hub_read_diagnostics", "hub_list_device_events"),
        read_gateway("hub_read_rules", "hub_get_rules"),
    ])
    wrong = {"tool":"hub_list_device_events","args":{"deviceId":7103}}
    assert catalog.compatible_read_gateway("hub_read_rules", wrong) is None


def test_no_write_gateway_or_unknown_mapping_can_be_selected():
    catalog = ToolDiscoveryCatalog([
        plain_tool("hub_search_tools"),
        read_gateway("hub_read_diagnostics", "hub_get_logs"),
        read_gateway("hub_manage_devices", "hub_list_device_events"),
    ])
    args = {"tool":"hub_list_device_events","args":{"deviceId":7103}}
    catalog.expand(discovery("hub_list_device_events", "hub_manage_devices"),
                   query="hub_list_device_events")
    assert catalog.compatible_read_gateway("hub_read_diagnostics", args) is None
    assert catalog.compatible_read_gateway("hub_manage_devices", args) is None


def test_matching_gateway_and_non_gateway_operation_stay_unchanged():
    catalog = ToolDiscoveryCatalog([
        read_gateway("hub_read_diagnostics", "hub_get_logs"),
    ])
    args = {"tool":"hub_get_logs","args":{"deviceId":7103}}
    assert catalog.compatible_read_gateway("hub_read_diagnostics", args) is None
    assert catalog.compatible_read_gateway("hub_read_diagnostics", {}) is None


def test_nested_wire_envelope_supported_without_rewriting_payload():
    catalog = ToolDiscoveryCatalog([
        read_gateway("hub_read_devices", "hub_get_device"),
        read_gateway("hub_read_diagnostics", "hub_get_logs"),
    ])
    nested = {"args":{"tool":"hub_get_logs",
                       "args":{"deviceId":7103,"since":"24h"}}}
    match = catalog.compatible_read_gateway("hub_read_devices", nested)
    assert match is not None and match[0] == "hub_read_diagnostics"
    assert nested["args"]["args"]["deviceId"] == 7103


def test_discovery_only_does_not_authorize_undeclared_write():
    catalog = ToolDiscoveryCatalog([
        plain_tool("hub_search_tools"),
        plain_tool("hub_manage_devices"),
        read_gateway("hub_read_devices","hub_get_device"),
    ])
    catalog.expand(discovery("hub_delete_device", "hub_manage_devices"),
                   query="hub_delete_device")
    assert catalog.compatible_read_gateway(
        "hub_read_devices",
        {"tool":"hub_delete_device","args":{"deviceId":7103}},
    ) is None

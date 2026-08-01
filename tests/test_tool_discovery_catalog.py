from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from tool_discovery_catalog import ToolDiscoveryCatalog  # noqa: E402


def tool(name: str, description: str = "") -> MCPTool:
    return MCPTool(name, description or name, {"type": "object"})


def search_result(data, *, is_error=False):
    return MCPToolResult("hub_search_tools", {}, {}, "", data, is_error=is_error)


def test_initial_registry_is_fixed_order_and_excludes_remote_gateways():
    catalog = ToolDiscoveryCatalog([
        tool("hub_manage_devices"),
        tool("homebrain_control_devices"),
        tool("hub_read_diagnostics"),
        tool("hub_search_tools"),
        tool("homebrain_home_snapshot"),
    ])

    assert catalog.declared_names == (
        "hub_search_tools",
        "hub_read_diagnostics",
        "homebrain_home_snapshot",
        "homebrain_control_devices",
    )
    assert catalog.declared_tool("hub_manage_devices") is None


def test_expansion_accepts_only_explicit_match_gateway_fields():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("hub_read_devices"),
        tool("hub_manage_devices"),
    ])
    result = search_result({
        "matches": [
            {
                "gateway": "hub_read_devices",
                "description": "hub_manage_devices",
            }
        ],
        "unrelated": {"gateway": "hub_manage_devices"},
    })

    additions = catalog.expand(result)

    assert [item.name for item in additions] == ["hub_read_devices"]
    assert catalog.declared_tool("hub_manage_devices") is None


def test_expansion_accepts_upstream_search_results_wire_contract():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("hub_manage_rule_machine"),
        tool("hub_read_rules"),
    ])
    result = search_result({
        "query": "create Rule Machine rule",
        "resultsCount": 2,
        "totalToolsSearched": 142,
        "results": [
            {
                "tool": "hub_set_rule",
                "gateway": "hub_manage_rule_machine",
                "callAs": (
                    "Call via hub_manage_rule_machine(tool=\"hub_set_rule\", "
                    "args={...})"
                ),
            },
            {
                "tool": "hub_list_rules",
                "gateway": "hub_read_rules",
            },
        ],
    })

    additions = catalog.expand(result)

    assert [item.name for item in additions] == [
        "hub_manage_rule_machine",
        "hub_read_rules",
    ]


def test_upstream_results_do_not_expand_from_tool_or_description_text():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("hub_manage_rule_machine"),
    ])
    result = search_result({
        "results": [
            {
                "tool": "hub_manage_rule_machine",
                "description": "Use hub_manage_rule_machine to author rules",
            }
        ]
    })

    assert catalog.expand(result) == []
    assert catalog.declared_names == ("hub_search_tools",)


def test_expansion_supports_recognised_result_envelope_and_preserves_order():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("second"),
        tool("first"),
    ])
    result = search_result({
        "result": {
            "matches": [
                {"gateway": "first"},
                {"gateway": "second"},
                {"gateway": "first"},
            ]
        }
    })

    additions = catalog.expand(result)

    assert [item.name for item in additions] == ["first", "second"]
    assert catalog.declared_names == ("hub_search_tools", "first", "second")
    assert catalog.expand(result) == []


def test_failed_unknown_and_self_discovery_results_do_not_expand():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("known"),
    ])

    assert catalog.expand(search_result(
        {"matches": [{"gateway": "known"}]}, is_error=True
    )) == []
    assert catalog.expand(search_result({
        "matches": [
            {"gateway": "hub_search_tools"},
            {"gateway": "unknown"},
            {"gateway": 42},
        ]
    })) == []
    assert catalog.declared_names == ("hub_search_tools",)


def test_replace_declared_reports_missing_names_and_hides_other_tools():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("hub_restart"),
        tool("hub_update_firmware"),
    ])

    missing = catalog.replace_declared([
        "hub_restart", "missing_tool", "hub_restart"
    ])

    assert missing == ["missing_tool"]
    assert catalog.declared_names == ("hub_restart",)
    assert catalog.declared_tool("hub_update_firmware") is None


def test_duplicate_available_name_uses_last_definition_without_duplicate_schema():
    remote = tool("homebrain_home_snapshot", "remote collision")
    local = tool("homebrain_home_snapshot", "local authoritative schema")
    catalog = ToolDiscoveryCatalog([remote, local])

    schemas = catalog.schemas()

    assert len(schemas) == 1
    assert schemas[0]["function"]["description"] == "local authoritative schema"


def test_tool_schema_supplies_default_object_parameters():
    schema = ToolDiscoveryCatalog.tool_schema(
        MCPTool("tool", "", {})
    )

    assert schema == {
        "type": "function",
        "function": {
            "name": "tool",
            "description": "tool",
            "parameters": {"type": "object", "properties": {}},
        },
    }

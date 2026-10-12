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
        tool("hub_get_tool_guide"),
        tool("hub_read_diagnostics"),
        tool("hub_search_tools"),
        tool("homebrain_home_snapshot"),
        tool("homebrain_resolve_device"),
        tool("homebrain_device_history"),
    ])

    assert catalog.declared_names == (
        "hub_search_tools",
        "hub_get_tool_guide",
        "hub_read_diagnostics",
        "homebrain_resolve_device",
        "homebrain_device_history",
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


def test_discovery_does_not_expose_gateway_for_locally_wrapped_history():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("hub_read_devices"),
        tool("homebrain_device_history"),
    ])
    result = search_result({
        "results": [{
            "tool": "hub_list_device_events",
            "gateway": "hub_read_devices",
        }]
    })

    assert catalog.expand(result) == []
    assert "homebrain_device_history" in catalog.declared_names
    assert catalog.declared_tool("hub_read_devices") is None


def test_discovery_keeps_gateway_when_local_wrapper_is_unavailable():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("hub_read_devices"),
    ])
    result = search_result({
        "results": [{
            "tool": "hub_list_device_events",
            "gateway": "hub_read_devices",
        }]
    })

    assert [item.name for item in catalog.expand(result)] == [
        "hub_read_devices"
    ]


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


def test_expansion_caps_gateway_hits_to_the_top_ranked_matches():
    """Regression test for a real live failure: the orchestrator seeds
    discovery with the raw original-request text ("living room light"), and
    the upstream hub_search_tools fuzzy match on "room" ranked two unrelated
    room-admin gateways (hub_read_rooms, hub_manage_rooms) behind its usual
    top hit. Declaring all of them ballooned a routine 15-tool request to 17
    declared tools, which correlated with the model answering across two
    rounds without calling any tool at all (a live "Refused" outcome). Only
    upstream's top two ranked hits should expand the registry; the long tail
    beyond that should be dropped.
    """

    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"),
        tool("hub_manage_rule_machine"),
        tool("hub_read_rooms"),
        tool("hub_manage_rooms"),
    ])
    result = search_result({
        "results": [
            {"tool": "hub_set_rule", "gateway": "hub_manage_rule_machine"},
            {"tool": "hub_list_rooms", "gateway": "hub_read_rooms"},
            {"tool": "hub_edit_room", "gateway": "hub_manage_rooms"},
        ]
    })

    additions = catalog.expand(result)

    assert [item.name for item in additions] == [
        "hub_manage_rule_machine",
        "hub_read_rooms",
    ]
    assert catalog.declared_tool("hub_manage_rooms") is None


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


def test_explicit_operation_search_chooses_correct_gateway_even_below_fuzzy_top_two():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"), tool("hub_manage_rooms"),
        tool("hub_read_rooms"), tool("hub_read_apps_code"),
    ])
    result = search_result({"results": [
        {"tool": "hub_set_room", "gateway": "hub_manage_rooms"},
        {"tool": "hub_list_rooms", "gateway": "hub_read_rooms"},
        {"tool": "hub_get_app_config", "gateway": "hub_read_apps_code"},
    ]})
    added = catalog.expand(result, query="hub_get_app_config")
    assert [item.name for item in added] == ["hub_read_apps_code"]
    assert catalog.declared_tool("hub_read_rooms") is None
    assert catalog.declared_tool("hub_manage_rooms") is None


def test_explicit_tool_discovery_can_follow_multiple_stages_without_expanding_everything():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"), tool("hub_read_apps_code"),
        tool("hub_read_rules"), tool("hub_read_devices"),
        tool("hub_manage_code"),
    ])
    first = search_result({"results": [
        {"tool": "hub_get_app_config", "gateway": "hub_read_apps_code"},
        {"tool": "hub_update_app", "gateway": "hub_manage_code"},
    ]})
    second = search_result({"results": [
        {"tool": "hub_list_rules", "gateway": "hub_read_rules"},
        {"tool": "hub_list_devices", "gateway": "hub_read_devices"},
    ]})
    assert [x.name for x in catalog.expand(first, query="hub_get_app_config")] == ["hub_read_apps_code"]
    assert [x.name for x in catalog.expand(second, query="hub_list_rules")] == ["hub_read_rules"]
    assert "hub_manage_code" not in catalog.declared_names
    assert "hub_read_devices" not in catalog.declared_names


def test_complete_registry_keeps_gateway_beyond_old_forty_eight_tool_limit():
    from tool_catalog_assembly import build_request_tool_catalog

    remote = [tool(f"remote_irrelevant_{i}") for i in range(55)]
    remote += [tool("hub_search_tools"), tool("hub_read_rare_domain")]
    catalog = build_request_tool_catalog(remote)
    assert catalog.declared_tool("hub_read_rare_domain") is None
    assert "hub_read_rare_domain" in catalog.available_names
    match = search_result({"results": [
        {"tool": "hub_get_rare_domain", "gateway": "hub_read_rare_domain"}
    ]})
    assert [t.name for t in catalog.expand(match, query="hub_get_rare_domain")] == [
        "hub_read_rare_domain"
    ]


def test_read_gateway_exposure_respects_registry_and_never_exposes_manage_tools():
    catalog = ToolDiscoveryCatalog([
        tool("hub_search_tools"), tool("hub_read_apps_code"),
        tool("hub_read_rules"), tool("hub_manage_rule_machine"),
    ])
    additions = catalog.expose_read_gateways([
        "hub_manage_rule_machine", "hub_read_apps_code",
        "hub_read_disabled_gateway", "hub_read_rules",
    ])
    assert [tool.name for tool in additions] == [
        "hub_read_apps_code", "hub_read_rules"
    ]
    assert "hub_manage_rule_machine" not in catalog.declared_names
    assert "hub_read_disabled_gateway" not in catalog.declared_names

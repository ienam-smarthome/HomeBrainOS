from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from gateway_argument_view import gateway_operation, gateway_operation_args  # noqa: E402
from grounding_policy import GroundingPolicy  # noqa: E402
from history_result_enrichment import enrich_history_result  # noqa: E402
from history_temporal_analysis import history_temporal_evidence_details  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from tool_discovery_catalog import SEARCH_TOOL, ToolDiscoveryCatalog  # noqa: E402


def _later_rows() -> list[dict]:
    return [
        {
            "name": "level",
            "value": str(index),
            "description": "later daytime activity",
            "date": f"2026-09-18T19:{index:02d}:00+01:00",
            "isStateChange": True,
        }
        for index in range(18)
    ]


def _semantic_history_result() -> MCPToolResult:
    events = [
        *_later_rows(),
        {
            "name": "command-off",
            "value": None,
            "description": "Command called: off()",
            "date": "2026-09-18T01:45:01.779+01:00",
            "isStateChange": False,
        },
        {
            "name": "switch",
            "value": "off",
            "description": "Bedroom 3 Light switch is off",
            "date": "2026-09-18T01:45:02.397+01:00",
            "isStateChange": True,
        },
        {
            "name": "command-setLevel",
            "value": None,
            "description": "Command called: setLevel(15)",
            "date": "2026-09-18T01:32:51.812+01:00",
            "isStateChange": False,
        },
        {
            "name": "switch",
            "value": "on",
            "description": "Bedroom 3 Light switch is on",
            "date": "2026-09-18T01:32:51.716+01:00",
            "isStateChange": True,
        },
        {
            "name": "command-off",
            "value": None,
            "description": "Command called: off()",
            "date": "2026-09-18T01:30:07.775+01:00",
            "isStateChange": False,
        },
        {
            "name": "switch",
            "value": "off",
            "description": "Bedroom 3 Light switch is off",
            "date": "2026-09-18T01:30:07.971+01:00",
            "isStateChange": True,
        },
        {
            "name": "switch",
            "value": "on",
            "description": "Bedroom 3 Light switch is on",
            "date": "2026-09-18T00:02:53.713+01:00",
            "isStateChange": True,
        },
    ]
    data = {
        "success": True,
        "requested": "Bedroom 3 Light",
        "deviceId": "7841",
        "label": "Bedroom 3 Light",
        "room": "Bedroom 3",
        "attribute": None,
        "events": events,
        "count": len(events),
        "sourceEventCount": len(events),
        "analysisEventCount": len(events),
        "historySourceIntegrity": "unverified",
        "historySourceIntegrityVerified": False,
        "timeWindow": {
            "kind": "last_night",
            "label": "last night",
            "start": "2026-09-17T18:00:00+01:00",
            "end": "2026-09-18T08:00:00+01:00",
            "ongoing": False,
            "sourceCompleteToStart": True,
        },
    }
    return MCPToolResult(
        "homebrain_device_history",
        {"name": "Bedroom 3 Light", "limit": 50},
        {},
        "",
        data,
    )


def test_boundary_evidence_is_derived_after_attribute_inference() -> None:
    result = enrich_history_result(
        "homebrain_device_history",
        _semantic_history_result(),
    )
    data = result.data

    assert data["attribute"] == "switch"
    assert data["attributeInferred"] is True
    assert data["temporalAnalysis"]["intervalCount"] == 2
    assert "boundaryEvents" in data
    names = [row.get("name") for row in data["boundaryEvents"]]
    assert "command-off" in names
    assert "command-setLevel" in names
    assert any(
        row.get("date") == "2026-09-18T01:30:07.775+01:00"
        for row in data["boundaryEvents"]
    )


def test_post_enrichment_boundary_rows_survive_receipt_latest_event_cap() -> None:
    result = enrich_history_result(
        "homebrain_device_history",
        _semantic_history_result(),
    )
    details = history_temporal_evidence_details(result.data)

    assert details is not None
    assert details["observedEventsTruncated"] is True
    # The ordinary latest rows are all later daytime activity.
    assert not any(
        row.get("date") == "2026-09-18T01:30:07.775+01:00"
        for row in details["observedEvents"]
    )
    # Boundary evidence is independent of that newest-first cap.
    assert any(
        row.get("date") == "2026-09-18T01:30:07.775+01:00"
        for row in details["boundaryEvents"]
    )


def test_nested_gateway_envelope_has_one_canonical_operation_view() -> None:
    arguments = {
        "args": {
            "tool": "hub_get_logs",
            "args": {
                "since": "20h",
                "limit": 100,
                "pattern": "Bedroom 3 Light",
            },
        }
    }

    assert gateway_operation(arguments) == "hub_get_logs"
    assert gateway_operation_args(arguments) == {
        "since": "20h",
        "limit": 100,
        "pattern": "Bedroom 3 Light",
    }
    assert GroundingPolicy.is_live_log_call(
        "hub_read_diagnostics",
        arguments,
    )


def test_evidence_receipt_records_nested_gateway_subtool() -> None:
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        recorder.record(
            "hub_read_diagnostics",
            {
                "args": {
                    "tool": "hub_get_logs",
                    "args": {"since": "20h", "limit": 100},
                }
            },
            success=True,
            elapsed_ms=12,
            summary="logs checked",
        )
        receipts = recorder.receipts()
    finally:
        recorder.reset(token)

    assert receipts[0]["sub_tool"] == "hub_get_logs"


def _tool(name: str, description: str) -> MCPTool:
    return MCPTool(
        name,
        description,
        {"type": "object", "properties": {}},
    )


def test_causal_completion_activates_known_provenance_gateways_without_search() -> None:
    catalog = ToolDiscoveryCatalog([
        _tool(SEARCH_TOOL, "Search MCP operations"),
        _tool(
            "hub_read_diagnostics",
            "Read diagnostics including hub_get_logs and hub_get_errors",
        ),
        _tool(
            "hub_read_apps_code",
            "Read installed app configuration and source",
        ),
        _tool(
            "hub_read_rules",
            "Read Rule Machine rule configuration and execution details",
        ),
        _tool(
            "hub_read_devices",
            "Read devices and device events",
        ),
        _tool(
            "homebrain_device_history",
            "Read local device history",
        ),
        _tool(
            "hub_manage_rule_machine",
            "Create and edit Rule Machine rules",
        ),
    ])

    # Apps/rules are intentionally not part of the normal initial registry.
    assert "hub_read_apps_code" not in catalog.declared_names
    assert "hub_read_rules" not in catalog.declared_names

    names = catalog.activate_causal_provenance_view()

    assert SEARCH_TOOL in names
    assert "hub_read_diagnostics" in names
    assert "hub_read_apps_code" in names
    assert "hub_read_rules" in names
    assert "hub_read_devices" not in names
    assert "homebrain_device_history" not in names
    assert "hub_manage_rule_machine" not in names
    assert set(catalog.declared_names) == set(names)

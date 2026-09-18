from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_timeline import build_causal_timeline_rows  # noqa: E402
from history_temporal_analysis import (  # noqa: E402
    boundary_event_evidence,
    history_temporal_evidence_details,
)
from mcp_client import MCPTool  # noqa: E402
from tool_discovery_catalog import SEARCH_TOOL, ToolDiscoveryCatalog  # noqa: E402


def _intervals() -> list[dict[str, Any]]:
    return [
        {
            "start": "2026-09-18T00:02:53.713+01:00",
            "end": "2026-09-18T01:30:07.971+01:00",
            "durationSeconds": 5234,
            "duration": "1h 27m",
        },
        {
            "start": "2026-09-18T01:32:51.716+01:00",
            "end": "2026-09-18T01:45:02.397+01:00",
            "durationSeconds": 731,
            "duration": "12m",
        },
    ]


def _newer_rows(count: int = 18) -> list[dict[str, Any]]:
    return [
        {
            "name": "level",
            "value": str(index),
            "description": "later daytime activity",
            "date": f"2026-09-18T19:{index:02d}:00+01:00",
            "isStateChange": True,
        }
        for index in range(count)
    ]


def test_boundary_evidence_survives_newest_event_truncation() -> None:
    command = {
        "name": "command-off",
        "value": None,
        "description": "Command called: off()",
        "date": "2026-09-18T01:30:07.775+01:00",
        "isStateChange": False,
    }
    rows = [*_newer_rows(), command]

    selected = boundary_event_evidence(
        rows,
        {"intervals": _intervals()},
    )

    assert any(row["name"] == "command-off" for row in selected)
    kept = next(row for row in selected if row["name"] == "command-off")
    assert kept["boundaryDeltaSeconds"] < 0.2


def test_history_evidence_keeps_boundary_rows_beyond_latest_sixteen() -> None:
    command = {
        "name": "command-off",
        "value": None,
        "description": "Command called: off()",
        "date": "2026-09-18T01:30:07.775+01:00",
        "isStateChange": False,
    }
    all_rows = [*_newer_rows(), command]
    temporal = {
        "activeState": "on",
        "inactiveState": "off",
        "intervalCount": 2,
        "intervals": _intervals(),
        "totalActiveDuration": "1h 39m",
        "totalActiveSeconds": 5965,
        "durationReliability": "unverified-event-stream",
    }
    result = {
        "label": "Bedroom 3 Light",
        "attribute": "switch",
        "temporalAnalysis": temporal,
        "events": all_rows,
        "boundaryEvents": boundary_event_evidence(all_rows, temporal),
    }

    details = history_temporal_evidence_details(result)

    assert details is not None
    assert details["observedEventsTruncated"] is True
    assert not any(
        row.get("name") == "command-off"
        for row in details["observedEvents"]
    )
    assert any(
        row.get("name") == "command-off"
        for row in details["boundaryEvents"]
    )


def test_causal_timeline_prefers_preserved_boundary_commands() -> None:
    evidence = [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "details": {
                "label": "Bedroom 3 Light",
                "attribute": "switch",
                "temporalAnalysis": {
                    "activeState": "on",
                    "observedIntervals": _intervals(),
                },
                "observedEvents": _newer_rows(16),
                "boundaryEvents": [
                    {
                        "name": "command-off",
                        "description": "Command called: off()",
                        "date": "2026-09-18T01:30:07.775+01:00",
                        "boundaryDeltaSeconds": 0.196,
                    },
                    {
                        "name": "command-setLevel",
                        "description": "Command called: setLevel(15)",
                        "date": "2026-09-18T01:32:51.812+01:00",
                        "boundaryDeltaSeconds": 0.096,
                    },
                ],
            },
        }
    ]

    rows = build_causal_timeline_rows(evidence)

    assert any(
        event["name"] == "command-off"
        for event in rows[0]["endCommands"]
    )
    assert any(
        event["name"] == "command-setLevel"
        for event in rows[1]["startCommands"]
    )


def _tool(name: str, description: str) -> MCPTool:
    return MCPTool(
        name,
        description,
        {"type": "object", "properties": {}},
    )


def test_causal_completion_tool_view_excludes_device_and_mutation_tools() -> None:
    catalog = ToolDiscoveryCatalog([
        _tool(SEARCH_TOOL, "Search Hubitat MCP tools"),
        _tool(
            "hub_read_diagnostics",
            "Read diagnostics and native hub_get_logs operations",
        ),
        _tool(
            "hub_read_apps_code",
            "Read installed apps and hub_get_app_config",
        ),
        _tool(
            "hub_read_rules",
            "Read Rule Machine rules and execution details",
        ),
        _tool(
            "hub_read_devices",
            "Read devices and device event history",
        ),
        _tool(
            "hub_manage_rule_machine",
            "Create and edit Rule Machine rules",
        ),
        _tool(
            "homebrain_device_history",
            "Read one device history",
        ),
        _tool(
            "homebrain_location_events",
            "Read location mode events",
        ),
    ])
    catalog.replace_declared([
        SEARCH_TOOL,
        "hub_read_diagnostics",
        "hub_read_apps_code",
        "hub_read_rules",
        "hub_read_devices",
        "hub_manage_rule_machine",
        "homebrain_device_history",
        "homebrain_location_events",
    ])

    names = set(catalog.causal_provenance_names())

    assert SEARCH_TOOL not in names
    assert "hub_read_diagnostics" in names
    assert "hub_read_apps_code" in names
    assert "hub_read_rules" in names
    assert "hub_read_devices" not in names
    assert "hub_manage_rule_machine" not in names
    assert "homebrain_device_history" not in names
    assert "homebrain_location_events" not in names

    schema_names = {
        item["function"]["name"]
        for item in catalog.causal_provenance_schemas()
    }
    assert schema_names == names


def test_causal_completion_uses_search_only_when_no_provenance_reader_exists() -> None:
    catalog = ToolDiscoveryCatalog([
        _tool(SEARCH_TOOL, "Search Hubitat MCP tools"),
        _tool("hub_read_devices", "Read devices and event history"),
        _tool("hub_manage_rule_machine", "Create and edit rules"),
    ])

    assert catalog.causal_provenance_names() == (SEARCH_TOOL,)

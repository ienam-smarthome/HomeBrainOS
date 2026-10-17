"""General-purpose investigation checkpoint and read-only tool view (0.17.85)."""
from __future__ import annotations

from pathlib import Path
import json
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] /
           "hubitat-mcp-ai" / "rootfs" / "app")
)

import pytest

from investigation_checkpoint import (
    is_investigative_question, build_evidence_checkpoint,
    render_investigation_checkpoint,
)
from tool_discovery_catalog import ToolDiscoveryCatalog
from mcp_client import MCPTool


@pytest.mark.parametrize("query", [
    "Why did the hallway light turn on yesterday? Read-only.",
    "Investigate why Bedroom 3 Mesh is offline using MQTT evidence.",
    "Diagnose the motion lockout failure, read-only.",
    "Analyse scheduled jobs and identify their owners.",
    "Troubleshoot failed Rule Machine automations.",
    "Investigate unexpected energy readings on the freezer socket.",
])
def test_investigation_intent_across_domains(query):
    assert is_investigative_question(query)


@pytest.mark.parametrize("query", [
    "Turn on the hallway light",
    "What is the kitchen temperature?",
    "Create a rule to turn on a switch",
    "Switch off the dehumidifier",
])
def test_simple_control_or_state_lookup_not_reflection(query):
    assert not is_investigative_question(query)


def test_checkpoint_uses_source_receipts_not_raw_log_messages_or_secrets():
    data = [
        {
            "tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events",
            "success": True,
            "evidence_kind": "authoritative_device_event_history",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": "7805",
                                   "since":"2026-10-14T18:54:00Z",
                                   "until":"2026-10-14T18:56:00Z"}},
            "details": {
                "sourceVerifiedOn": False,
                "sourceHistoryComplete": False,
                "returnedRowsInWindow": 0,
                "events": [{
                    "message": "password=should-never-be-rendered",
                }],
            },
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "focal_producer_execution_logs",
            "arguments": {"tool": "hub_get_logs",
                          "args":{"appId": "4129", "limit": 50}},
            "details": {"logCount": 0, "logs": [
                {"message":"MQTT password: leak-me"}
            ]},
        },
    ]
    packet = build_evidence_checkpoint(
        "Investigate why the light turned on",
        data, available_read_tools=("hub_read_apps_code",),
    )
    assert packet["schema"] == "homebrain-evidence-checkpoint/v1"
    assert packet["sources"][0]["scope"]["deviceId"] == "7805"
    assert packet["sources"][0]["recorded_count"]["returnedRowsInWindow"] == 0
    assert "Exact historical state transition not verified" in packet["open_questions"]
    assert packet["declared_read_tools"] == ["hub_read_apps_code"]
    exposed = render_investigation_checkpoint(
        "Investigate why the light turned on", data,
    )
    assert "should-never-be-rendered" not in exposed
    assert "leak-me" not in exposed
    assert "source-event timestamps" in exposed


def _tool(name: str, **annotations):
    return MCPTool(
        name=name,
        description=name,
        input_schema={"type": "object", "properties": {}},
        annotations=annotations,
    )


def test_investigator_tool_view_excludes_known_write_gateways():
    catalog = ToolDiscoveryCatalog([
        _tool("hub_search_tools", readOnlyHint=True),
        _tool("hub_get_tool_guide", readOnlyHint=True),
        _tool("hub_read_devices", readOnlyHint=True),
        _tool("hub_read_apps_code", readOnlyHint=True),
        _tool("hub_read_rules", readOnlyHint=True),
        _tool("hub_read_diagnostics", readOnlyHint=True),
        _tool("homebrain_device_history", readOnlyHint=True),
        _tool("hub_manage_rule_machine", mutates=True),
        _tool("hub_manage_devices", mutates=True),
        _tool("homebrain_control_devices", effect="routine_write"),
    ])
    tools = catalog.activate_investigation_read_view(max_declared=15)
    assert "hub_read_apps_code" in tools
    assert "hub_read_rules" in tools
    assert "hub_read_diagnostics" in tools
    assert "hub_search_tools" in tools
    assert "hub_manage_rule_machine" not in tools
    assert "hub_manage_devices" not in tools
    assert "homebrain_control_devices" not in tools
    assert all(tool in catalog.available_names for tool in tools)


def test_investigator_tool_view_bounded_no_guessed_name():
    installed = [_tool("hub_search_tools", readOnlyHint=True)]
    installed.extend(_tool(f"hub_read_{n}", readOnlyHint=True) for n in range(45))
    catalog = ToolDiscoveryCatalog(installed)
    names = catalog.activate_investigation_read_view(max_declared=12)
    assert len(names) == 12
    assert names[0] == "hub_search_tools"
    assert "hub_read_not_installed" not in names


def test_duplicate_tool_sources_are_not_independent_corroboration():
    data = [
        {
            "tool": "hub_read_devices", "success": True,
            "evidence_kind":"authoritative_command_event_history",
            "arguments": {"tool":"hub_list_device_events",
                          "args":{"deviceId": "88", "attribute": "command-on"}},
            "details":{"eventCount": 1},
        },
        {
            "tool": "hub_read_devices", "success": True,
            "evidence_kind":"authoritative_command_event_history",
            "arguments": {"tool":"hub_list_device_events",
                          "args":{"deviceId": "88", "attribute": "command-on"}},
            "details":{"eventCount": 1},
        },
    ]
    packet = build_evidence_checkpoint("Investigate device 88", data)
    assert len(packet["sources"]) == 1


def test_failed_read_not_silently_treated_as_checked_success():
    packet = build_evidence_checkpoint("Diagnose the device", [
        {"tool": "hub_read_devices", "success": False,
         "evidence_kind": "read_error",
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": "5"}}}
    ])
    assert packet["sources"][0]["checked"] is False
    assert any("unavailable" in item for item in packet["open_questions"])


def test_hypothesis_comparison_distinguishes_read_coverage_from_proof():
    from general_task_engine import InvestigativeHypothesis

    candidates = (
        InvestigativeHypothesis("A local automation commanded ON",
                               "Was a relevant app command recorded?", "app_logs"),
        InvestigativeHypothesis("A sensor report was stale",
                               "Was fresh telemetry recorded?", "device_history"),
    )
    evidence = [
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "effect": "read", "mutates": False,
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": "51", "attribute": "switch"}},
         "details": {"eventCount": 0}},
    ]
    packet = build_evidence_checkpoint(
        "Investigate unexpected light events", evidence,
        candidate_hypotheses=candidates,
    )
    checks = packet["competing_hypothesis_checks"]
    assert len(checks) == 2
    assert checks[0]["source_state"] == "source-class-not-checked"
    assert checks[1]["source_state"] == "source-class-checked-verdict-unverified"
    assert all(item["hypothesis_verdict"] == "unverified" for item in checks)
    assert packet["next_unchecked_discriminators"] == [
        "Was a relevant app command recorded?"
    ]
    rendered = render_investigation_checkpoint(
        "Investigate unexpected light events", evidence,
        candidate_hypotheses=candidates,
    )
    assert "unverified" in rendered
    assert "successful" not in rendered.casefold() or "proof" in rendered.casefold()


def test_failed_read_never_marks_competing_explanation_checked():
    from general_task_engine import InvestigativeHypothesis

    candidates = (
        InvestigativeHypothesis("Scheduler overload", "Who owns the jobs?",
                               "scheduled_jobs"),
        InvestigativeHypothesis("CPU contention", "What is measured busy time?",
                               "performance_stats"),
    )
    packet = build_evidence_checkpoint("Diagnose scheduler workload", [
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_jobs",
         "success": False, "effect": "read", "mutates": False,
         "arguments": {"tool": "hub_get_jobs", "args": {}}},
    ], candidate_hypotheses=candidates)
    assert all(row["source_state"] == "source-class-not-checked"
               for row in packet["competing_hypothesis_checks"])
    assert len(packet["next_unchecked_discriminators"]) == 2


@pytest.mark.parametrize("question,expected", [
    ("Independently investigate why Bedroom 3 Mesh is offline and compare three competing explanations. Read-only.", True),
    ("Diagnose MQTT issues and test alternative hypotheses. Read-only.", True),
    ("Compare possible causes for repeated scheduled jobs. Read-only.", True),
    ("Use paid model. Investigate why Bedroom 3 Mesh is offline despite MQTT "
     "reporting connected. Compare the most plausible causes using available "
     "MCP evidence. Read-only.", True),
    ("Diagnose this MQTT outage and compare the likely explanations.", True),
    ("Investigate this device outage and compare the root causes.", True),
    ("Investigate the light; check possible alternative causes.", False),
    ("Investigate thoroughly why Livingroom Light 1 turned on at 12:00:03; "
     "check app logs and possible alternative causes. Read-only.", False),
    ("Why did the hallway light turn on?", False),
    ("Investigate the current status of Bedroom 3 Mesh.", False),
    ("Turn on Hallway Light", False),
])
def test_explicit_hypothesis_comparison_does_not_affect_plain_causal_paths(question, expected):
    from investigation_checkpoint import requests_explicit_hypothesis_comparison
    assert requests_explicit_hypothesis_comparison(question) is expected


def test_hubitat_device_log_does_not_verify_upstream_mqtt_packet_discriminator():
    from general_task_engine import InvestigativeHypothesis

    candidates = (
        InvestigativeHypothesis(
            "Endpoint is silent on MQTT", "Did an actual upstream MQTT packet arrive?",
            "device_logs", "upstream",
        ),
        InvestigativeHypothesis(
            "Hubitat driver state is cached", "Does the stored Hubitat value differ?",
            "device_state", "hubitat",
        ),
    )
    receipts = [
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "mutates": False, "effect": "read",
         "arguments": {"tool": "hub_get_logs", "args": {
             "deviceId": "7103", "since": "24h", "limit": 100,
         }}, "details": {"logCount": 38}},
        {"tool": "hub_read_devices", "sub_tool": "hub_get_device",
         "success": True, "mutates": False, "effect": "read",
         "arguments": {"tool": "hub_get_device", "args": {
             "deviceId": "7103",
         }}},
    ]
    packet = build_evidence_checkpoint(
        "Investigate offline MQTT device", receipts,
        candidate_hypotheses=candidates,
    )
    upstream, hubitat = packet["competing_hypothesis_checks"]
    assert upstream["source_state"] == "source-class-checked-verdict-unverified"
    assert upstream["origin_state"] == "upstream-origin-not-independently-verified"
    assert upstream["discriminator_verified"] is False
    assert upstream["hypothesis_verdict"] == "unverified"
    assert "Did an actual upstream MQTT packet arrive?" in packet[
        "next_unchecked_discriminators"
    ]
    assert hubitat["origin_state"] == "hubitat-source-class-observed"
    assert hubitat["discriminator_verified"] is False
    assert all(c["hypothesis_verdict"] == "unverified"
               for c in packet["competing_hypothesis_checks"])


def test_physical_delivery_cannot_be_established_from_successful_device_history():
    from general_task_engine import InvestigativeHypothesis

    candidates = (
        InvestigativeHypothesis("Socket is unpowered",
                                "Did the physical socket respond?",
                                "device_history", "physical"),
        InvestigativeHypothesis("A switch command was dispatched",
                                "Was on() recorded by Hubitat?",
                                "device_history", "hubitat"),
    )
    packet = build_evidence_checkpoint("Investigate an offline socket", [
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "effect": "read", "mutates": False,
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": "7103", "limit": 20}}}
    ], candidate_hypotheses=candidates)
    physical, recorded = packet["competing_hypothesis_checks"]
    assert physical["origin_state"] == "physical-origin-not-independently-verified"
    assert recorded["origin_state"] == "hubitat-source-class-observed"

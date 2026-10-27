"""v0.18.161: dated investigation must acquire evidence before model planning.

Synthetic 12 Oct → 27 Oct replay: operation shape, read/write authority, issuer
attestation and typed app configuration are checked through real V2 host code.
No Hubitat device, model provider or other network system is contacted.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.evidence import build_case_file
from investigation_v2.incident_retrieval import incident_first_proposals
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.model_adapter import V2ModelProposer
from investigation_v2.planning import review_model_read_proposals
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.temporal_scope import explicit_incident_window
from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect


QUESTION = "Investigate why Bedroom 3 Mesh went offline on 12 October 2026"
WINDOW = explicit_incident_window(QUESTION, zone_name="Europe/London")
assert WINDOW is not None


def gateway(*, with_window=True, max_hours=744, limit_cap=500):
    fields = {
        "deviceId": {"type": "string"},
        "limit": {"type": "integer", "maximum": limit_cap},
        "hoursBack": {"type": "integer", "maximum": max_hours},
    }
    if with_window:
        fields.update({"since": {"type": "string"}, "until": {"type": "string"}})
    return MCPTool("hub_read_devices", "Verified read gateway", {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": ["hub_list_device_events"]},
            "args": {"type": "object", "properties": fields,
                     "required": ["deviceId"], "additionalProperties": False},
        },
        "required": ["tool", "args"], "additionalProperties": False,
    }, annotations={"readOnlyHint": True, "mutates": False})


def apps_gateway():
    return MCPTool("hub_read_apps_code", "Verified app read gateway", {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": ["hub_list_apps", "hub_get_app_config",
                                               "hub_list_device_dependents"]},
            "args": {"type": "object"},
        },
        "required": ["tool", "args"], "additionalProperties": False,
    }, annotations={"readOnlyHint": True, "mutates": False})


def test_old_calendar_window_supported_when_schema_allows_it():
    proposals = incident_first_proposals([gateway()], ["7103"], WINDOW)
    assert len(proposals) == 1
    inner = proposals[0]["arguments"]["args"]
    assert inner["since"] == WINDOW.start_utc
    assert inner["until"] == WINDOW.end_utc
    assert inner["hoursBack"] >= 300
    assert inner["limit"] == 150
    assert "attribute" not in inner


def test_no_window_schema_uses_live_horizon_and_clamps_page_limit():
    result = incident_first_proposals(
        [gateway(with_window=False, limit_cap=200)], ["7103"], WINDOW, limit=500)
    assert result[0]["arguments"]["args"]["limit"] == 200
    assert result[0]["arguments"]["args"]["hoursBack"] >= 300
    assert "since" not in result[0]["arguments"]["args"]


def test_beyond_live_horizon_fails_closed_without_window_and_uses_bounded_window():
    assert incident_first_proposals([gateway(with_window=False, max_hours=168)],
                                    ["7103"], WINDOW) == []
    allowed = incident_first_proposals([gateway(with_window=True, max_hours=168)],
                                       ["7103"], WINDOW)
    assert len(allowed) == 1
    assert "hoursBack" not in allowed[0]["arguments"]["args"]
    assert "since" in allowed[0]["arguments"]["args"]
    assert incident_first_proposals([gateway()], ["7103", "7104"], WINDOW) == []
    hostile = MCPTool("hub_read_devices", "Write", gateway().input_schema,
                      annotations={"readOnlyHint": False, "mutates": True})
    assert incident_first_proposals([hostile], ["7103"], WINDOW) == []


def test_model_cannot_spend_reads_on_unsupported_projection():
    tool = apps_gateway()
    case = build_case_file(QUESTION, [])
    bad = {"tool": "hub_read_apps_code",
           "arguments": {"tool": "hub_list_device_dependents",
                         "args": {"deviceId": "7103"}},
           "discriminator": "Find consumers", "information_gain": "Check dependencies",
           "hypothesis_ids": []}
    rejected = review_model_read_proposals(
        case, [bad], [tool], verified_entity_ids=["7103"])
    assert rejected.approved == []
    assert "no reviewed V2 typed evidence projection" in rejected.rejected[0].reason

    async def mock_chat(messages, tools):
        return {"content": '{"hypotheses":[],"reads":[],"finish":true}'}
    proposer = V2ModelProposer(mock_chat, [tool], verified_entity_ids=["7103"])
    advertised = next(x for x in proposer.available_read_schema
                      if x["name"] == "hub_read_apps_code")
    assert "hub_get_app_config" in advertised["operations"]
    assert "hub_list_device_dependents" not in advertised["operations"]


EVENTS = [
    {"deviceId": "7103", "name": "voltage", "value": 245,
     "date": "2026-10-12T01:26:40+01:00", "producedBy": {"id": "7103"}},
    {"deviceId": "7103", "name": "command-off", "type": "command",
     "date": "2026-10-12T01:30:01.743+01:00", "producedBy": {"id": "3950"}},
    {"deviceId": "7103", "name": "switch", "value": "off",
     "date": "2026-10-12T01:30:01.914+01:00", "producedBy": {"id": "7103"}},
    {"deviceId": "7103", "name": "healthStatus", "value": "offline",
     "date": "2026-10-12T01:33:46+01:00", "producedBy": {"id": "7103"}},
]


class FakeMCP:
    async def list_tools(self):
        return [gateway(), apps_gateway(),
                MCPTool("hub_manage_devices", "Unsafe write", {"type": "object"},
                        annotations={"readOnlyHint": False, "mutates": True})]


class FakeExecutor:
    def __init__(self, mcp):
        self.mcp = mcp
        self.calls = []

    async def execute(self, name, arguments, *, tool, record_evidence):
        assert record_evidence is False
        assert name.startswith("hub_read_")
        assert arguments["tool"] in ("hub_list_device_events",
                                      "hub_list_apps", "hub_get_app_config")
        self.calls.append((name, arguments))
        op = arguments["tool"]
        if op == "hub_list_device_events":
            data = {"deviceId": "7103", "events": EVENTS}
        elif op == "hub_list_apps":
            # The app inventory may omit the event-attested issuer.
            data = {"apps": [{"id": "3103", "name": "Button Controller"}]}
        else:
            assert arguments["args"]["appId"] == "3950"
            data = {"success": True, "app": {"id": "3950"},
                    "settings": {"onOff.3": False, "privatePassword": "DO_NOT_COPY"}}
        result = MCPToolResult(name, arguments, raw={}, text="DO_NOT_COPY",
                               data=data, is_error=False)
        return ToolExecution(name=name, arguments=arguments, effect=ToolEffect.READ,
                             success=True, elapsed_ms=1, content="DO_NOT_COPY",
                             result=result)


@pytest.mark.asyncio
async def test_dated_investigation_collects_event_and_controller_before_first_model_call():
    mcp = FakeMCP()
    executor = FakeExecutor(mcp)
    observed = []

    async def model(case, round_index):
        observed.append((round_index, len(case.records),
                         [(r.stage, r.action, r.producer_id) for r in case.records]))
        assert any(r.stage == "command_issued" and r.producer_id == "3950"
                   for r in case.records)
        assert any(r.stage == "config_stored" and r.target_id == "3950"
                   for r in case.records)
        return {"hypotheses": [], "reads": [], "finish": True}

    result = await run_read_only_investigation(
        question=QUESTION, mcp=mcp, executor=executor, propose=model,
        verified_entity_ids=["7103"], incident_window=WINDOW,
        max_total_reads=8, max_rounds=1,
        bootstrap_source_identity=True, bootstrap_device_context=True,
    )
    operations = [args["tool"] for _, args in executor.calls]
    assert operations[:2] == ["hub_list_device_events", "hub_list_device_events"]
    assert operations[-1] == "hub_get_app_config"
    assert len(observed) == 1
    assert observed[0][1] >= 5
    assert result.stopped_because == "model_finished"
    assert result.executed_reads == len(executor.calls)
    assert result.read_failures == []
    assert any(row.get("stage") == "controller_config"
               and row.get("typed_settings_fields", 0) > 0
               for row in result.bootstrap_diagnostics)
    report = format_investigation_report(result.case, [], result.stopped_because, WINDOW)
    assert "Current stored controller settings" in report
    assert "Incident-linked sequence" in report
    assert "DO_NOT_COPY" not in json.dumps(result.to_dict())
    assert all(not name.startswith("hub_manage_") for name, _ in executor.calls)

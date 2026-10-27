"""0.18.160 architectural integration: canonical incident evidence + write fence.

All examples are synthetic. READ tests exercise V2's production host gates.
WRITE tests exercise the real same-session confirmation coordinator against
a fake executor; nothing can reach an actual hub or another device.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from confirmation_policy import ConfirmationPolicy
from confirmation_store import PendingConfirmation
from confirmed_action_coordinator import ConfirmedActionCoordinator
from investigation_v2.evidence import build_case_file
from investigation_v2.transition_links import incident_links
from investigation_v2.planning_evidence import planning_evidence
from investigation_v2.source_identity import source_configuration_proposals
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.planning import review_model_read_proposals
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.receipt_projection import project_read_receipt
from mcp_client import MCPTool, MCPToolResult
from tool_catalog_assembly import build_request_tool_catalog
from tool_executor import ToolExecution
from tool_registry import ToolEffect


def _case(extra=None):
    args = {"tool": "hub_list_device_events", "args": {"deviceId": "7103"}}
    rows = [
        {"deviceId": "7103", "name": "command-off", "type": "command",
         "date": "2026-10-12T00:30:01+00:00", "producedBy": {"id": "3950"}},
        {"deviceId": "7103", "name": "switch", "value": "off",
         "date": "2026-10-12T00:30:01.17+00:00", "producedBy": {"id": "7103"}},
        {"deviceId": "7103", "name": "healthStatus", "value": "offline",
         "date": "2026-10-12T00:33:46+00:00", "producedBy": {"id": "7103"}},
        {"deviceId": "7103", "name": "command-on", "type": "command",
         "date": "2026-10-24T20:51:12+00:00", "producedBy": {"id": "3103"}},
    ]
    rows.extend(extra or [])
    response = MCPToolResult("hub_read_devices", args, raw={}, text="SECRET",
                             data={"deviceId": "7103", "events": rows}, is_error=False)
    receipt = project_read_receipt(
        "hub_read_devices", args, response, source_request_id="incident")
    return build_case_file("Investigate offline; make no changes.", [receipt])


def _read_manifest():
    return MCPTool("hub_read_apps_code", "Read-only app configuration", {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": ["hub_get_app_config"]},
            "args": {"type": "object"},
        },
        "required": ["tool", "args"],
    }, annotations={"readOnlyHint": True, "mutates": False})


def test_shared_incident_link_drives_controller_priority_and_report():
    case = _case()
    links = incident_links(case)
    assert len(links) == 1
    link = links[0]
    assert link.command.producer_id == "3950"
    assert link.reported_state.action == "switch"
    assert link.adverse_state.action == "healthStatus"
    assert 220 < link.seconds_to_adverse < 230
    proposals = source_configuration_proposals([_read_manifest()], case)
    assert proposals[0]["arguments"]["args"]["appId"] == "3950"
    report = format_investigation_report(case, [], "planning_timeout")
    assert "**Incident-linked sequence:**" in report
    assert "does not independently prove" in report
    assert "Another OFF was issued" not in report


def test_missing_off_report_is_not_inferred_from_subsequent_offline_status():
    case = _case()
    case.records = [row for row in case.records if row.action != "switch"]
    link = incident_links(case)[0]
    assert link.reported_state is None
    report = format_investigation_report(case, [], "planning_timeout")
    assert "switch=off state was reported" not in report
    assert "physical execution remains unverified" in report


def test_large_case_prompt_is_bounded_without_erasing_commands_or_source_case():
    from datetime import datetime, timedelta, timezone
    start = datetime(2026, 10, 22, tzinfo=timezone.utc)
    extra = []
    for i in range(70):
        extra.append({
            "deviceId": "7103", "name": "deviceHealth",
            "value": "stale" if i % 2 else "unknown",
            "date": (start + timedelta(minutes=5 * i)).isoformat(),
            "producedBy": {"id": "7103"},
        })
    case = _case(extra)
    original_count = len(case.records)
    payload = json.loads(planning_evidence(case, None))
    assert len(case.records) == original_count
    assert payload["total_case_records"] == original_count
    assert len(payload["records"]) < original_count
    assert sum(r["rows"] for r in payload["coalesced_context"]) > 0
    original_commands = {r.record_id for r in case.records
                         if r.stage == "command_issued"}
    projected_commands = {r["id"] for r in payload["records"]
                          if r["stage"] == "command_issued"}
    assert original_commands == projected_commands
    assert all(not item["physical_cause_verified"]
               for item in payload["incident_links"])
    assert "SECRET" not in json.dumps(payload)


def test_read_only_planner_rejects_write_gateway_and_disguised_write_operation():
    case = _case()
    proper = _read_manifest()
    write = MCPTool("hub_manage_devices", "Write", {"type": "object"},
                    annotations={"readOnlyHint": False, "mutates": True})
    # Including a write name in a model plan does not confer permission.
    proposals = [
        {"tool": "hub_manage_devices", "arguments": {"tool": "hub_call_device_command",
            "args": {"deviceId": "7103", "command": "on"}},
         "discriminator": "switch", "information_gain": "do it", "hypothesis_ids": []},
        {"tool": "hub_read_apps_code", "arguments": {"tool": "hub_set_app_disabled",
            "args": {"appId": "3950"}},
         "discriminator": "settings", "information_gain": "do it", "hypothesis_ids": []},
    ]
    reviewed = review_model_read_proposals(
        case, proposals, [proper, write], verified_entity_ids=["7103"])
    assert not reviewed.approved
    assert len(reviewed.rejected) == 2


@pytest.mark.asyncio
async def test_host_v2_never_invokes_executor_for_model_requested_write():
    case = _case()
    write = MCPTool("hub_manage_devices", "Write", {"type": "object"},
                    annotations={"readOnlyHint": False, "mutates": True})

    class MCP:
        async def list_tools(self):
            return [write]

    class FailIfCalled:
        calls = 0
        async def execute(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("No device or network tool may execute")

    mcp = MCP()
    executor = FailIfCalled()
    executor.mcp = mcp  # production contract: executor and reader share one connection
    async def propose(_casefile, _round):
        return {"hypotheses": [], "reads": [{
            "tool": "hub_manage_devices",
            "arguments": {"tool": "hub_call_device_command",
                          "args": {"deviceId": "7103", "command": "on"}},
            "discriminator": "make online", "information_gain": "write",
            "hypothesis_ids": [],
        }], "finish": True}
    # Explicit read-only V2 never shares the confirmed-write execution path.
    result = await run_read_only_investigation(
        question="Why offline?", mcp=mcp, executor=executor, propose=propose,
        verified_entity_ids=["7103"], max_rounds=1, max_total_reads=2,
        bootstrap_source_identity=False, bootstrap_device_context=False,
        initial_receipts=[],
    )
    assert result.executed_reads == 0
    assert executor.calls == 0
    assert result.stopped_because == "no_approved_discriminating_reads"


@pytest.mark.asyncio
async def test_confirmed_write_path_mock_requires_receipt_and_reports_one_write():
    # Unlike investigation, this represents a pre-consumed SAME-SESSION
    # confirmation. Exercise actual production coordinator with fake transport.
    gateway = "hub_manage_rule_machine"
    args = {"tool": "hub_set_rule", "args": {"name": "SIMULATED ONLY",
        "addAction": {"capability": "runCommand", "command": "off",
                      "deviceIds": ["99991"], "capabilityFilter": "Switch"}}}
    pending = PendingConfirmation(
        expires_at=999.0,
        actions=[(gateway, args)],
        messages=[{"role": "user", "content": "make simulated rule"}],
        assistant_message={"role": "assistant", "content": "Please confirm"},
    )

    class FakeWrite:
        def __init__(self):
            self.calls = []
        async def execute(self, name, arguments, **kwargs):
            self.calls.append((name, arguments, kwargs))
            result = MCPToolResult(name, arguments, {}, "",
                {"success": True, "appId": 90001, "health": {"ok": True}},
                is_error=False)
            return ToolExecution(name=name, arguments=arguments,
                effect=ToolEffect.SENSITIVE_WRITE, success=True,
                elapsed_ms=1, content="{}", result=result)
    writes = FakeWrite()
    mutation_marks = []
    async def no_model(*_args, **_kwargs):
        raise AssertionError("Verified rule result must not rely on model narration")
    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True), writes, no_model,
        lambda: mutation_marks.append("confirmed"),
    )
    catalog = build_request_tool_catalog(
        [MCPTool(gateway, gateway, {"type": "object"})])
    report = await coordinator.resume(pending, catalog)
    assert "appId: 90001" in report
    assert len(writes.calls) == len(mutation_marks) == 1
    assert writes.calls[0][1]["args"]["confirm"] is True

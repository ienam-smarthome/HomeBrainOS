"""Regressions derived from two read-only live native V2 investigations.

Test data is minimal, synthetic evidence shaped like the observed MCP receipts:
hub_get_logs uses entries/time/type/name, not logs/date/source.
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool, MCPToolResult
from investigation_v2.native_source_adapters import (
    compact_logs, attested_source_ids, log_source,
)
from investigation_v2.native_read_agent import (
    _payload, run_native_read_agent,
)
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG, call,
)

LIVE_INFO = {
    "total": 13552, "count": 100, "entries": [
        {"name": "System alert: Hub C8 - Low Memory <200MB",
         "level": "INFO", "type": "app",
         "message": "app|2084|System alert: Hub C8 - Low Memory <200MB|Event: Hub Info freeMemory 933.96",
         "time": "2026-10-28 15:49:12.065"},
        {"name": "Hub Info", "level": "INFO", "type": "dev",
         "message": "dev|1089|Hub Info|freeMemory : 933.96MB",
         "time": "2026-10-28 15:49:11.942"},
    ],
}
LIVE_WARN = {
    "total": 13622, "count": 100, "entries": [
        {"name": "Bedroom 3 Mesh", "level": "WARN", "type": "dev",
         "message": "dev|7103|Bedroom 3 Mesh|Bedroom 3 Mesh: Watchdog fired after 30822s without data — reconnecting",
         "time": "2026-10-28 15:50:18.200"},
        {"name": "00 Google Calendar Notifier", "level": "WARN",
         "type": "app",
         "message": "app|4080|00 Google Calendar Notifier|Speech announcement was never confirmed",
         "time": "2026-10-28 15:50:13.981"},
        {"name": "Motion Sensor", "level": "INFO", "type": "dev",
         "message": "dev|7000|Motion Sensor|motion active",
         "time": "2026-10-28 15:50:20.000"},
    ],
}


def test_live_log_entries_no_longer_look_like_a_clean_hub():
    projection = _payload(MCPToolResult(
        "hub_read_diagnostics", {}, {}, "", LIVE_INFO), "hub_get_logs")
    audit = projection["log_summary"]
    assert audit["returned_rows"] == 2
    assert audit["level_counts_in_returned_rows"] == {"INFO": 2}
    assert audit["warning_error_group_count"] == 0
    assert audit["warning_error_audit_complete"] is False
    assert "NOT evidence" in audit["interpretation_guard"]
    assert audit["truncated_or_partial"] is True
    assert "Low Memory" not in str(audit["warning_error_groups"])


def test_live_warn_entries_are_typed_and_usable_for_followup():
    audit = compact_logs(LIVE_WARN)
    assert audit["level_counts_in_returned_rows"] == {"WARN": 2, "INFO": 1}
    assert audit["warning_error_group_count"] == 2
    assert "30822s" in str(audit["warning_error_groups"])
    assert attested_source_ids("hub_get_logs", LIVE_WARN) == {"7103", "4080"}
    assert log_source(LIVE_WARN["entries"][0]) == ("dev", "7103", "Bedroom 3 Mesh")


def test_log_message_without_matching_metadata_cannot_grant_id():
    impostor = {"entries": [
        {"type": "dev", "name": "Someone else",
         "message": "dev|7103|Bedroom 3 Mesh|pretend source"},
    ]}
    assert attested_source_ids("hub_get_logs", impostor) == set()


def test_bounded_unknown_projection_is_disclosed_not_treated_as_source_fact():
    result = MCPToolResult("hub_read_diagnostics", {}, {}, "", {
        "meshCustomField": {"unknown_secret": "must-not-leak"},
        "api_key": "private",
        "token": "secret",
    })
    projection = _payload(result, "hub_get_hub_mesh")
    assert projection["projection_empty"] is True
    assert "meshCustomField" in projection["source_field_names"]
    assert "token" not in str(projection)
    assert "must-not-leak" not in str(projection)


@pytest.mark.asyncio
async def test_model_must_complete_explanation_after_no_approved_reads():
    mcp=FakeMCP([READ_DIAG])
    executor=FakeExecutor(mcp,[LIVE_WARN])
    step=0
    async def model(messages, tools):
        nonlocal step
        step+=1
        if step == 1:
            return {"tool_calls":[call("hub_get_logs", level="warn", limit=100)]}
        if tools and step == 2:
            return {"tool_calls":[{"function":{"name":"hub_manage_rules",
                                                 "arguments":{"command":"delete"}}}]}
        assert tools == []
        return {"content":"The returned warnings include Bedroom 3 Mesh watchdog and Google Calendar announcement; exact root causes remain unverified."}
    out=await run_native_read_agent(
        question="Investigate overall issues",chat=model,mcp=mcp,executor=executor)
    assert out["native_diagnostics"]["stop_reason"]=="no_approved_reads"
    assert out["native_diagnostics"]["final_synthesis"]=="completed"
    assert "Bedroom 3 Mesh watchdog" in out["answer"]["text"]
    assert "Watchdog fired" in out["answer"]["text"]
    assert out["native_diagnostics"]["reads_executed"]==1
    assert len(executor.calls)==1


@pytest.mark.asyncio
async def test_verified_target_can_be_lazily_confirmed_without_full_device_listing():
    device_tool=MCPTool(
        "hub_read_devices","Read device",
        {"type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_device"]},
            "args":{"type":"object","additionalProperties":True},
        },"required":["tool","args"]},annotations={"readOnlyHint":True},
    )
    mcp=FakeMCP([device_tool])
    called=[]
    async def identities():
        called.append("identity_snapshot")
        return [{"id":"7103","label":"Bedroom 3 Mesh"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{"success":True,"device":{"id":"7103","name":"Bedroom 3 Mesh"}}])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[{
                "function":{"name":"hub_read_devices","arguments":{
                    "tool":"hub_get_device","args":{"deviceId":"7103"}
                }}
            }]}
        return {"content":"Device 7103 returned its current snapshot; historical contact is unverified."}
    out=await run_native_read_agent(
        question="Investigate Bedroom 3 Mesh", chat=model,mcp=mcp,
        executor=executor)
    assert called==["identity_snapshot"]
    assert out["native_diagnostics"]["lazy_identity_lookup_attempted"] is True
    assert out["native_diagnostics"]["successful_reads"]==1
    assert out["native_diagnostics"]["verified_source_ids"]==1
    assert executor.calls[0][1]["args"]["deviceId"]=="7103"



@pytest.mark.asyncio
async def test_fluid_model_cannot_make_info_only_logs_look_like_full_audit():
    mcp=FakeMCP([READ_DIAG])
    executor=FakeExecutor(mcp,[LIVE_INFO])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[call("hub_get_logs", limit=100)]}
        return {"content":"There are no critical system failures."}
    output=await run_native_read_agent(
        question="check hub logs for any issues",chat=model,
        mcp=mcp,executor=executor)
    assert output["native_diagnostics"]["reads_executed"]==1
    assert output["answer"]["human_review_required"] is True
    assert "warning_error_log_coverage_unverified" in output["answer"]["validation_issues"]
    assert "not proof that there are no WARN/ERROR entries" in output["answer"]["text"]
    assert "no WARN/ERROR in returned sample" in output["answer"]["text"]



@pytest.mark.asyncio
async def test_model_gets_one_evidence_coverage_challenge_then_reads_warnings():
    mcp=FakeMCP([READ_DIAG])
    executor=FakeExecutor(mcp,[LIVE_INFO,LIVE_WARN])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[call("hub_get_logs", limit=100)]}
        if step==2:
            assert tools
            return {"content":"No problems identified."}
        if step==3:
            assert "Evidence coverage check" in messages[-1]["content"]
            return {"tool_calls":[call("hub_get_logs", level="warn", limit=100)]}
        return {"content":"Bedroom 3 Mesh watchdog warning is present; causes still unverified."}
    result=await run_native_read_agent(
        question="check hub logs for any issues",chat=model,
        mcp=mcp,executor=executor)
    assert result["native_diagnostics"]["coverage_challenge_used"] is True
    assert result["native_diagnostics"]["reads_executed"]==2
    assert result["native_diagnostics"]["stop_reason"]=="model_finished"
    assert "Bedroom 3 Mesh watchdog" in result["answer"]["text"]
    assert result["native_diagnostics"]["read_summaries"][1]["read_filters"]["level"]=="warn"

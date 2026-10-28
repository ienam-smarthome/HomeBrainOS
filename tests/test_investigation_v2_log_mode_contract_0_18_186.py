"""Native MCP read argument contract and evidence-coverage regression.

Live source: 28 Oct 2026 21:15 Google Nest Hub investigation attempted
mode='devices' + level='warn'; the hub logged the invalid combination as an
MCP Rule Server ERROR and the model stopped without target-specific evidence.
This is a shared operation-schema problem, not a prompt-specific route.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from investigation_v2.native_tool_protocol import operation_problem, guidance_for
from investigation_v2.native_read_agent import _guard, run_native_read_agent
from investigation_v2.native_evidence_focus import focused_highlights
from investigation_v2.native_source_adapters import compact_logs
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeExecutor, FakeMCP, READ_DIAG,
)
from investigation_v2.native_entity_lookup import NAME


def read_args(mode=None, level=None, **filters):
    inner = dict(filters)
    if mode is not None:
        inner["mode"] = mode
    if level is not None:
        inner["level"] = level
    return {"tool": "hub_get_logs", "args": inner}


def tool_call(gateway, args):
    return {"function": {"name": gateway, "arguments": args}}


@pytest.mark.parametrize("mode", [
    "devices", "apps", "scheduledJobs", "runningJobs", "hubEvents", "status",
    ["past", "devices"],
])
def test_log_tabs_cannot_be_combined_with_severity_filter(mode):
    args = read_args(mode, "warn", limit=100)
    assert operation_problem("hub_read_diagnostics", args) == "log_mode_level_incompatible"
    assert _guard("hub_read_diagnostics", args, {
        "hub_read_diagnostics": READ_DIAG}, {}, set()) == "log_mode_level_incompatible"
    hint = guidance_for("log_mode_level_incompatible")
    assert "mode='past'" in hint
    assert "mode='devices'" in hint


@pytest.mark.parametrize("args", [
    read_args(mode="past", level="warn", limit=100),
    read_args(level="error", limit=100),
    read_args(mode="past", level="info", limit=50, deviceId="7934"),
    read_args(mode="devices", limit=100),
    read_args(mode=["past", "devices"], limit=50),
])
def test_supported_log_mode_and_level_combinations_remain_usable(args):
    assert operation_problem("hub_read_diagnostics", args) is None


@pytest.mark.asyncio
async def test_model_recovers_from_invalid_device_tab_level_without_hub_error():
    mcp = FakeMCP([READ_DIAG])
    async def identities():
        return [{"id": "7934", "label": "Google Nest Hub - [Google Nest Hub]"}]
    mcp.get_device_identities = identities
    log_sample = {
        "total": 11480,
        "entries": [
            {"type": "dev", "name": "Google Nest Hub - [Google Nest Hub]",
             "level": "WARN", "time": "2026-10-28 19:55:19.399",
             "message": "dev|7934|Google Nest Hub - [Google Nest Hub]|Device 7934 generates excessive hub load"},
            {"type": "dev", "name": "Google Nest Hub - [Google Nest Hub]",
             "level": "WARN", "time": "2026-10-28 17:58:24.126",
             "message": "dev|7934|Google Nest Hub - [Google Nest Hub]|method runQ ran for 147,429ms"},
        ],
    }
    executor = FakeExecutor(mcp, [log_sample])
    step = 0
    async def model(messages, tools):
        nonlocal step
        step += 1
        if step == 1:
            return {"tool_calls": [tool_call(NAME, {"name": "Google Nest Hub"})]}
        if step == 2:
            return {"tool_calls": [tool_call(
                "hub_read_diagnostics", read_args("devices", "warn", deviceId="7934")
            )]}
        if step == 3:
            assert "log_mode_level_incompatible" in messages[-1]["content"]
            assert "mode='past'" in messages[-1]["content"]
            return {"tool_calls": [tool_call(
                "hub_read_diagnostics", read_args(
                    "past", "warn", deviceId="7934", limit=100)
            )]}
        return {"content": (
            "Google Nest Hub has source-reported performance warnings including "
            "a runQ call lasting 147,429ms. This does not establish the "
            "underlying driver mechanism or hub-wide causation."
        )}
    out = await run_native_read_agent(
        question="Why is Google Nest Hub generating excessive hub-load warnings?",
        chat=model, mcp=mcp, executor=executor,
    )
    assert out["native_diagnostics"]["reads_executed"] == 1
    assert out["native_diagnostics"]["successful_reads"] == 1
    assert len(executor.calls) == 1
    assert executor.calls[0][1]["args"]["mode"] == "past"
    assert executor.calls[0][1]["args"]["level"] == "warn"
    assert executor.calls[0][1]["args"]["deviceId"] == "7934"
    assert any(e["code"] == "log_mode_level_incompatible"
               for e in out["native_diagnostics"]["failures"])
    assert out["native_diagnostics"]["focus_ids"] == ["7934"]
    assert "runQ" in out["native_diagnostics"]["source_highlights"][2]


def test_recent_no_target_warning_sample_is_not_misreported_as_historical_clearance():
    witness = {
        "read": 4, "operation": "hub_get_logs",
        "read_filters": {"mode": "past", "limit": 100},
        "source_data": {"log_summary": {
            "returned_rows": 100,
            "level_counts_in_returned_rows": {"ERROR": 1, "INFO": 98, "WARN": 1},
            "oldest_returned": "2026-10-28 21:12:18.067",
            "newest_returned": "2026-10-28 21:14:18.762",
            "warning_error_groups": [
                {"source_id": "4151", "source_name": "MCP Rule Server",
                 "level": "ERROR", "message": "Parameters level do not apply to log mode 'devices'"},
                {"source_id": "7103", "source_name": "Bedroom 3 Mesh",
                 "level": "WARN", "message": "Watchdog fired after 50173s"},
            ],
        }},
    }
    highlights = focused_highlights([witness], ["7934"])
    assert "no target-specific warnings" in highlights[0]
    assert "21:12:18.067" in highlights[0]
    assert "21:14:18.762" in highlights[0]
    assert "NOT evidence" in highlights[0]
    assert "no target-specific warnings" not in str(
        focused_highlights([witness], ["7103"]))


def test_unfiltered_sample_error_is_not_fabricated_target_warning():
    sample = {"entries": [
        {"type": "app", "name": "MCP Rule Server", "level": "ERROR",
         "message": "app|4151|MCP Rule Server|Parameters level do not apply to log mode 'devices'"},
        {"type": "dev", "name": "Bedroom 3 Mesh", "level": "WARN",
         "message": "dev|7103|Bedroom 3 Mesh|Watchdog fired after 50173s"},
    ]}
    summary = compact_logs(sample)
    assert summary["warning_error_group_count"] == 2
    assert {r["source_id"] for r in summary["warning_error_groups"]} == {"4151", "7103"}

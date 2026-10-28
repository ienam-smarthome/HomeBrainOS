"""Golden tests for native MCP READ agent across unrelated investigation scopes.

No question-keyword router, no device gate, no writes, and no raw secrets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_registry import ToolEffect
from investigation_v2.native_read_agent import (
    run_native_read_agent, _guard, _read_manifest, _observed_operations,
    _group_logs, _payload, _ids_from_read,
)

READ_DIAG = MCPTool(
    "hub_read_diagnostics", "Read Hubitat diagnostics",
    {"type": "object", "properties": {
        "tool": {"type": "string", "enum": [
            "hub_get_metrics", "hub_get_logs", "hub_get_device_health",
            "hub_delete_device",
        ]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]}, annotations={"readOnlyHint": True}
)
MANAGE = MCPTool(
    "hub_manage_rules", "Delete a rule", {"type": "object"},
    annotations={"readOnlyHint": False}
)
READ_APPS = MCPTool(
    "hub_read_apps_code", "Apps and rules",
    {"type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_get_app_config"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]}, annotations={"readOnlyHint": True}
)
SEARCH = MCPTool(
    "hub_search_tools", "Search tools",
    {"type": "object", "properties": {"query": {"type": "string"}},
     "required": ["query"]}, annotations={"readOnlyHint": True}
)


class FakeMCP:
    def __init__(self, manifest=None):
        self.manifest = manifest or [READ_DIAG, READ_APPS, MANAGE, SEARCH]
        self.listed = 0
    async def list_tools(self):
        self.listed += 1
        return self.manifest
    async def get_audit_devices(self, **kwargs):
        raise AssertionError("Native mode must not prefetch inventory")


class FakeExecutor:
    def __init__(self, mcp, outputs):
        self.mcp = mcp
        self.outputs = list(outputs)
        self.calls = []
    async def execute(self, name, arguments, *, tool=None, record_evidence=True):
        assert record_evidence is False
        assert name not in ("hub_manage_rules", "hub_write_device")
        self.calls.append((name, arguments))
        output = self.outputs.pop(0)
        if output is None:
            result = MCPToolResult(name, arguments, {}, "error", {},
                                   is_error=True)
            success = False
        else:
            result = MCPToolResult(name, arguments, {}, "UNTRUSTED", output)
            success = True
        return SimpleNamespace(
            name=name, arguments=arguments, effect=ToolEffect.READ,
            success=success, elapsed_ms=10, content="unused",
            result=result, error=None,
        )


def call(operation, **args):
    return {"function": {"name": "hub_read_diagnostics",
                         "arguments": {"tool": operation, "args": args}}}


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "check hub logs for any issues",
    "any errors today?",
    "is the hub healthy?",
    "which process is causing network backup alerts?",
])
async def test_general_hub_question_no_inventory_or_device_gate(question):
    mcp = FakeMCP()
    logs = [
        {"level": "warn", "source": {"id": "7103"},
         "date": "2026-10-28T10:00:00Z",
         "message": "Watchdog fired after 26000s without data"},
        {"level": "warn", "source": {"id": "7103"},
         "date": "2026-10-28T10:05:00Z",
         "message": "Watchdog fired after 26300s without data"},
        {"level": "error", "source": {"id": "4129"},
         "date": "2026-10-28T10:06:00Z",
         "message": "SenseCap D1 408 request timed out"},
    ]
    executor = FakeExecutor(mcp, [
        {"alerts": ["NETWORK_BACKUP_FAILED"], "uptime": "7h 28m",
         "safeMode": False, "freeMemory": 910},
        {"logs": logs, "count": 3},
    ])
    calls = []
    async def model(messages, tools):
        calls.append((messages, tools))
        assert not any(x["function"]["name"].startswith("hub_manage_") for x in tools)
        if len(calls) == 1:
            return {"role": "assistant", "content": "", "tool_calls": [
                call("hub_get_metrics"), call("hub_get_logs",
                                              mode="past", level="warn", limit=100)]}
        return {"role": "assistant",
                "content": "The hub has a network backup alert; the logs contain a mesh watchdog and a SenseCap timeout."}
    result = await run_native_read_agent(
        question=question, chat=model, mcp=mcp, executor=executor)
    assert result["answer_mode"] == "native_mcp_investigation"
    assert result["native_diagnostics"]["reads_executed"] == 2
    assert result["native_diagnostics"]["successful_reads"] == 2
    assert result["native_diagnostics"]["stop_reason"] == "model_finished"
    assert result["native_diagnostics"]["verified_source_ids"] == 2
    assert "Watchdog fired" in result["report"]["text"]
    assert "SenseCap D1" in result["report"]["text"]
    assert mcp.listed == 1
    assert len(calls) == 2
    assert executor.calls[0][1]["tool"] == "hub_get_metrics"


def test_host_denies_any_write_even_when_model_invents_permissions():
    manifest = _read_manifest([READ_DIAG, READ_APPS, MANAGE, SEARCH])
    assert "hub_manage_rules" not in manifest
    assert _guard("hub_manage_rules", {"tool": "hub_delete_rule"},
                  manifest, {}, set()) == "tool_not_on_live_read_manifest"
    assert _guard("hub_read_diagnostics",
                  {"tool": "hub_delete_device", "args": {}},
                  manifest, {}, set()) == "unsafe_or_missing_operation"
    assert _guard("hub_read_diagnostics",
                  {"tool": "hub_get_logs", "args": {"command": "off"}},
                  manifest, {}, set()) == "unsafe_arguments"
    assert _guard("hub_read_apps_code",
                  {"tool": "hub_get_app_config", "args": {"appId": "4129"}},
                  manifest, {}, set()) == "target_id_not_verified_from_live_source"
    assert _guard("hub_read_apps_code",
                  {"tool": "hub_get_app_config", "args": {"appId": "4129"}},
                  manifest, {}, {"4129"}) is None


@pytest.mark.asyncio
async def test_rejected_write_is_not_executed_and_no_verified_reads_are_claimed():
    mcp = FakeMCP()
    executor = FakeExecutor(mcp, [])
    count = 0
    async def model(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return {"tool_calls": [{"function": {"name": "hub_manage_rules",
                                                 "arguments": {"tool": "hub_delete_rule"}}}]}
        return {"content": "There are no errors."}
    result = await run_native_read_agent(
        question="Check my system", chat=model, mcp=mcp, executor=executor)
    assert executor.calls == []
    assert result["native_diagnostics"]["successful_reads"] == 0
    assert "No verified MCP evidence" in result["answer"]["text"]


def test_verified_search_mapping_only_accepts_live_read_gateway():
    manifest = _read_manifest([READ_DIAG, READ_APPS, MANAGE, SEARCH])
    result = MCPToolResult("hub_search_tools", {}, {}, "", {
        "results": [
            {"tool": "hub_get_logs", "gateway": "hub_read_diagnostics"},
            {"tool": "hub_delete_rule", "gateway": "hub_manage_rules"},
            {"tool": "hub_get_secret", "gateway": "unlisted_gateway"},
        ]
    })
    assert _observed_operations(result, manifest) == {
        "hub_read_diagnostics": {"hub_get_logs"}
    }


def test_log_compaction_groups_varying_watchdog_counters_and_redacts_secrets():
    groups = _group_logs({"logs": [
        {"level": "warn", "source": {"id": "7103"},
         "date": "2026-10-28T10:00:00Z",
         "message": "Watchdog fired after 26591s without data"},
        {"level": "warn", "source": {"id": "7103"},
         "date": "2026-10-28T10:05:00Z",
         "message": "Watchdog fired after 26289s without data"},
        {"level": "error", "source": "4129",
         "date": "2026-10-28T10:05:00Z",
         "message": "No route to http://10.1.1.1/?token=secret"},
    ]})
    assert groups["group_count"] == 2
    assert groups["groups"][1]["count"] == 2
    assert "token=secret" not in json.dumps(groups)


def test_typed_metric_projection_never_exposes_credentials():
    result = MCPToolResult("hub_read_diagnostics", {}, {}, "untrusted", {
        "alerts": ["NETWORK_BACKUP_FAILED"], "safeMode": False,
        "api_key": "super-secret", "password": "do-not-display",
        "details": {"token": "private", "uptime": "7h 28m"},
    })
    data = _payload(result, "hub_get_metrics")
    assert "NETWORK_BACKUP_FAILED" in json.dumps(data)
    assert "do-not-display" not in json.dumps(data)
    assert "super-secret" not in json.dumps(data)
    assert "private" not in json.dumps(data)


def test_log_row_id_is_not_mistaken_for_verified_app_or_device():
    rows = {"logs": [
        {"id": "99999", "message": "Some log row", "appId": "4129"},
        {"id": 88888, "message": "Other log", "source": {
            "type": "app", "id": "3970"}},
        {"id": 77777, "message": "Unknown source", "source": {
            "type": "unknown", "id": "7103"}},
    ]}
    assert _ids_from_read("hub_get_logs", rows) == {"4129", "3970"}
    assert "99999" not in _ids_from_read("hub_get_logs", rows)


def test_nested_control_argument_cannot_be_smuggled_through_open_read_schema():
    manifest = _read_manifest([READ_DIAG])
    assert _guard("hub_read_diagnostics", {
        "tool": "hub_get_logs",
        "args": {"filter": {"nested": {"command": "off"}}},
    }, manifest, {}, set()) == "write_argument_rejected"


def test_same_millisecond_repeats_count_as_burst_even_when_unsorted():
    rec = {"level": "warn", "source": {"id": "4129", "type": "app"},
           "message": "HTTP 408 timeout"}
    rows = {"logs": [
        {**rec, "date": "2026-10-28T10:00:00Z"},
        {**rec, "date": "2026-10-28T10:01:00Z"},
        {**rec, "date": "2026-10-28T10:00:00Z"},
    ]}
    group = _group_logs(rows)["groups"][0]
    assert group["count"] == 3
    assert group["duplicate_timestamp_rows"] == 1


def test_source_reported_response_size_limit_is_not_an_invented_success():
    from investigation_v2.native_read_agent import _oversized_hint
    big = MCPToolResult("hub_read_diagnostics", {}, {}, "", {
        "success": False, "error": {
            "code": "response_too_large",
            "suggestion": "Narrow since window or use cursor pagination",
        },
    }, is_error=True)
    assert "Narrow since" in _oversized_hint(big)
    other = MCPToolResult("hub_read_diagnostics", {}, {}, "", {
        "success": False, "error": {"code": "unknown_gateway_failure"}
    }, is_error=True)
    assert _oversized_hint(other) is None

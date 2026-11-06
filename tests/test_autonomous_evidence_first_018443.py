"""Autonomous evidence-first phase 1: offline, no Hubitat, cloud or writes.

The model chooses *what* history it needs. The host validates the optional
read-only request shape, installed permissions and resolver; progress through
new distinct read evidence replaces the short fixed read budget.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_first_checkpoint_plan import SourceCheckpointBudget  # noqa: E402
from general_task_engine import GeneralTaskPlan  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from reasoning_policy import (  # noqa: E402
    register_model_tool_execution,
    reasoning_budget_status,
    reset_reasoning_budget,
    set_reasoning_profile,
)
from tool_discovery_catalog import ToolDiscoveryCatalog  # noqa: E402


def plan(*, operation="investigate", requests=None, kinds=None):
    return json.dumps({
        "version": "1", "domain": "device", "operation": operation,
        "objective": "Answer a historical sensor interval from recorded events",
        "skills": ["diagnostics"],
        "capabilityQueries": ["device attribute history"],
        "evidenceGoals": ["Last reading above threshold", "First later below threshold"],
        "requiredEvidenceKinds": (
            ["device_history"] if kinds is None else kinds
        ),
        "readRequests": ([
            {"tool": "homebrain_device_history",
             "args": {"name": "Lab Environment Sensor", "attribute": "humidity",
                      "hours_back": 168, "limit": 50}},
        ] if requests is None else requests),
    })


def test_planner_requests_real_history_for_noncausal_numeric_thresholds():
    parsed = GeneralTaskPlan.from_model(plan(operation="read"))
    assert parsed is not None
    assert parsed.required_evidence_kinds == ("device_history",)
    assert len(parsed.read_requests) == 1
    request = parsed.read_requests[0]
    assert request.tool == "homebrain_device_history"
    assert request.arguments == {
        "name": "Lab Environment Sensor", "attribute": "humidity",
        "hours_back": 168, "limit": 50,
    }
    # A plan is explicitly NOT a receipt or authority to claim history existed.
    assert "model-proposed-not-yet-executed" in parsed.instruction()


def test_planner_cannot_drop_its_own_validated_history_requirement():
    parsed = GeneralTaskPlan.from_model(
        plan(operation="read", kinds=[])
    )
    assert parsed is not None
    assert parsed.read_requests
    assert parsed.required_evidence_kinds == ("device_history",)
    # The host still must execute through installed read-only tools;
    # inclusion in the plan cannot serve as evidence.
    assert "model-proposed-not-yet-executed" in parsed.instruction()


def test_planned_source_arguments_reject_writes_invalid_target_and_horizon():
    forbidden = [
        {"tool": "hub_manage_devices",
         "args": {"tool": "hub_call_device_command", "parameters": ["off"]}},
        {"tool": "homebrain_control_devices",
         "args": {"name": "Lab Sensor", "action": "off"}},
        {"tool": "homebrain_device_history",
         "args": {"name": "Lab Sensor", "attribute": "humidity",
                  "deviceId": "123", "hours_back": 168}},
        {"tool": "homebrain_device_history",
         "args": {"name": "Lab Sensor", "attribute": "humidity",
                  "hours_back": 9999, "limit": 50}},
        {"tool": "homebrain_device_history",
         "args": {"name": "Lab Sensor", "attribute": "humidity",
                  "limit": True}},
        {"tool": "homebrain_device_history",
         "args": {"name": "Lab Sensor", "attribute": "../humidity"}},
        {"tool": "homebrain_device_history",
         "args": {"name": "", "attribute": "humidity"}},
    ]
    parsed = GeneralTaskPlan.from_model(plan(requests=forbidden))
    assert parsed is not None
    assert parsed.read_requests == ()
    # A model calling the task a write cannot authorise a proposed read either.
    assert GeneralTaskPlan.from_model(
        plan(operation="write")
    ).read_requests == ()


def test_read_requests_deduplicate_and_support_cross_device_comparison():
    items = [
        {"tool": "homebrain_device_history",
         "args": {"name": name, "attribute": "temperature",
                  "hours_back": 24, "limit": 50}}
        for name in ("Room A", "Room B", "Room A")
    ]
    parsed = GeneralTaskPlan.from_model(plan(requests=items))
    assert len(parsed.read_requests) == 2
    assert [row.arguments["name"] for row in parsed.read_requests] == [
        "Room A", "Room B"
    ]


def test_autonomous_reasoning_does_not_stop_on_arbitrary_read_counts():
    try:
        set_reasoning_profile("autonomous")
        reset_reasoning_budget(preserve_profile=True)
        for index in range(40):
            assert register_model_tool_execution(
                name="homebrain_device_history",
                arguments={"name": f"Test {index}"},
                mutates=False,
            )
        state = reasoning_budget_status()
        assert state["profile"] == "autonomous"
        assert state["readCalls"] == 40
        assert state["maxReadCalls"] is None
        assert state["maxToolRounds"] is None
        assert state["exhausted"] is False
    finally:
        reset_reasoning_budget()


def test_legacy_read_budget_remains_for_opt_out_compatibility():
    try:
        set_reasoning_profile("standard")
        reset_reasoning_budget(preserve_profile=True)
        from reasoning_policy import DEFAULT_MAX_READ_TOOL_CALLS
        for _ in range(DEFAULT_MAX_READ_TOOL_CALLS):
            assert register_model_tool_execution(mutates=False)
        assert not register_model_tool_execution(mutates=False)
        assert reasoning_budget_status()["exhausted"] is True
    finally:
        reset_reasoning_budget()


def test_source_checkpoints_follow_new_read_progress_without_fixed_count():
    gate = SourceCheckpointBudget(max_offers=None)
    assert gate.offer("initial", [])
    for index in range(5):
        receipt = [
            {"tool": "homebrain_device_history", "effect": "read",
             "success": True, "arguments": {"name": f"test-{j}"}}
            for j in range(index + 1)
        ]
        assert gate.offer(f"new-evidence-{index}", receipt)
        assert not gate.offer("duplicate-without-progress", receipt)
    assert len(gate.offered_kinds) == 6
    denied = SourceCheckpointBudget(max_offers=None)
    assert denied.offer("initial", [])
    assert not denied.offer("failed-read", [{
        "tool": "homebrain_device_history", "effect": "read",
        "success": False, "arguments": {"name": "unavailable"},
    }])


def test_exact_operation_discovery_keeps_multiple_verified_read_gateways():
    tools = [
        MCPTool(name, name, {"type": "object"})
        for name in ("hub_search_tools", "hub_read_diagnostics",
                     "hub_read_rules", "hub_read_devices", "hub_read_apps_code")
    ]
    catalog = ToolDiscoveryCatalog(tools)
    response = MCPToolResult(
        "hub_search_tools", {}, {}, "", {
            "results": [
                {"tool": "hub_get_performance_stats",
                 "gateway": "hub_read_diagnostics"},
                {"tool": "hub_get_rule",
                 "gateway": "hub_read_rules"},
                {"tool": "hub_get_device",
                 "gateway": "hub_read_devices"},
            ],
        },
    )
    # Query names are exact live advertised operations. The old limit of two
    # hid a third genuinely relevant source even when all were explicitly found.
    additions = catalog.discovered_tools(
        response, {t.name: t for t in tools},
        query="hub_get_performance_stats hub_get_rule hub_get_device",
    )
    assert [t.name for t in additions] == [
        "hub_read_diagnostics", "hub_read_rules", "hub_read_devices",
    ]


def test_current_release_defaults_enable_planning_but_preserve_safety():
    config = (APP.parents[1] / "config.yaml").read_text()
    assert "general_task_engine_enabled: true" in config
    assert "unified_mcp_max_tool_rounds: 18" in config
    assert "require_sensitive_confirmation: true" in config
    assert "investigation_deadline_seconds: 0" in config
    assert "investigation_stall_timeout_seconds: 180" in config
    assert "investigation_emergency_watchdog_seconds: 1800" in config
    source = (APP / "mcp_agent_orchestrator.py").read_text()
    assert "task_plan.read_requests" in source
    assert "classify_tool_effect(tool, request.arguments).mutates" in source
    assert "autonomous_planned_read_success" in source
    # Only actual evidence collected in this turn may resolve user questions.
    assert "self.executor.execute(" in source

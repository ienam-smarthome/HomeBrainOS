"""Generic history recovery and reported demand arithmetic; no live/model claims."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai/rootfs/app"))
from device_history_service import DeviceHistoryService
from history_temporal_analysis import analyze_state_intervals, history_temporal_evidence_details
from history_result_enrichment import enrich_history_result
from general_task_engine import GeneralTaskPlan
from mcp_client import MCPTool, MCPToolResult
from mcp_agent_orchestrator import UnifiedMCPAgent


def state(name, value, stamp):
    return {"name": name, "value": value, "date": stamp, "isStateChange": True}


def demand_rows(start="2026-11-07T10:49:00Z"):
    return [
        state("thermostatOperatingState", "idle", "2026-11-07T10:58:00Z"),
        state("temperature", "21", "2026-11-07T10:55:00Z"),
        state("thermostatOperatingState", "heating", start),
        state("thermostatMode", "heat", "2026-11-07T08:00:00Z"),
    ]


class HistoryMCP:
    def __init__(self, rows=None, fail=False):
        self.rows = demand_rows() if rows is None else rows
        self.fail = fail
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        assert name == "hub_read_devices" and args["tool"] == "hub_list_device_events"
        return MCPToolResult(name, args, {}, "read failed" if self.fail else "ok",
                             {"events": self.rows} if not self.fail else {"success": False},
                             is_error=self.fail)


def target():
    return {"id": "42", "label": "Example Thermostat",
            "attributes": {"temperature": 21, "thermostatMode": "heat"},
            "capabilities": ["Thermostat"], "commands": []}


@pytest.mark.asyncio
async def test_rejected_attribute_discovers_actual_history_on_same_verified_device():
    mcp = HistoryMCP()
    service = DeviceHistoryService(mcp, lambda *a, **k: None,
        now=lambda: datetime(2026, 11, 7, 12, tzinfo=timezone.utc))
    result = await service.history({
        "name": "Example Thermostat", "attribute": "switch", "limit": 3,
        "_resolved_target": target(), "_discover_rejected_attribute": True})
    assert not result.is_error and result.data["success"] is True
    assert result.data["attribute"] is None
    assert result.data["historyAttributeRecovery"]["requestedAttribute"] == "switch"
    assert result.data["historyAttributeRecovery"]["requestedAttributeVerified"] is False
    assert "thermostatOperatingState" in result.data["observedEventAttributes"]
    assert mcp.calls == [("hub_read_devices", {"tool": "hub_list_device_events",
        "args": {"deviceId": "42", "hoursBack": 168, "limit": 50}})]
    result = enrich_history_result("homebrain_device_history", result)
    assert result.data["attribute"] == "thermostatoperatingstate"
    assert result.data["temporalAnalysis"]["totalActiveSeconds"] == 540
    details = history_temporal_evidence_details(result.data)
    assert details["historyAttributeRecovery"]["doesNotProveAttributeAbsence"] is True
    assert details["observedStateAnalyses"]["thermostatOperatingState"]["totalActiveSeconds"] == 540


@pytest.mark.asyncio
async def test_recovery_is_opt_in_and_never_reports_guessed_switch_absence():
    mcp = HistoryMCP()
    service = DeviceHistoryService(mcp, lambda *a, **k: None)
    result = await service.history({"name": "Example Thermostat", "attribute": "switch",
                                   "_resolved_target": target()})
    assert result.is_error and result.data["unsupportedAttribute"] == "switch"
    assert not mcp.calls


@pytest.mark.asyncio
async def test_failed_discovery_remains_failed_without_fabricated_state():
    mcp = HistoryMCP(fail=True)
    service = DeviceHistoryService(mcp, lambda *a, **k: None)
    result = await service.history({"name": "Example Thermostat", "attribute": "switch",
        "_resolved_target": target(), "_discover_rejected_attribute": True})
    assert result.is_error and result.data["success"] is False
    assert "temporalAnalysis" not in result.data


@pytest.mark.asyncio
async def test_generic_recovery_also_handles_sensor_dimension_mismatch():
    mcp = HistoryMCP(rows=[state("humidity", "54", "2026-11-07T10:49:00Z")])
    service = DeviceHistoryService(mcp, lambda *a, **k: None)
    result = await service.history({"name": "Example Sensor", "attribute": "motion",
        "_resolved_target": {"id": "77", "label": "Example Sensor",
                             "attributes": {"humidity": 54}},
        "_discover_rejected_attribute": True})
    assert not result.is_error
    assert result.data["observedEventAttributes"] == ["humidity"]
    assert not result.data["observedStateAnalyses"]
    assert mcp.calls[0][1]["args"]["deviceId"] == "77"


def test_configured_heat_mode_cannot_be_used_as_reported_heating_interval():
    assert analyze_state_intervals("thermostatMode", demand_rows()) is None
    result = analyze_state_intervals("thermostatOperatingState", demand_rows())
    assert result["activeState"] == "heating" and result["inactiveState"] == "idle"
    assert result["intervals"][0]["durationSeconds"] == 540


@pytest.mark.parametrize("other", ["cooling", "pending heat", "fan only", "unknown"])
def test_other_operating_states_are_not_silently_bridged_as_heating(other):
    rows = demand_rows() + [state("thermostatOperatingState", other, "2026-11-07T10:52:00Z")]
    assert analyze_state_intervals("thermostatOperatingState", rows) is None


def test_semantic_plan_can_request_source_discovery_without_guessing_attribute():
    plan = GeneralTaskPlan.from_model(json.dumps({
        "version": "1", "domain": "device", "operation": "read",
        "objective": "Establish interval and related demand",
        "requiredEvidenceKinds": ["device_history"],
        "readRequests": [{"tool": "homebrain_device_history",
                          "args": {"name": "Example Thermostat", "attribute": ""}}],
    }))
    assert plan is not None and plan.read_requests[0].arguments["attribute"] == ""


class AgentMCP:
    def __init__(self):
        self.calls = []
        self.devices = [
            {**target(), "room": "Lab"},
            {"id": "43", "label": "Example Radiator", "room": "Lab",
             "attributes": {"thermostatOperatingState": "idle"},
             "capabilities": ["Thermostat"], "commands": []},
        ]

    async def get_cached_devices(self):
        return self.devices

    async def list_tools(self):
        return [MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                MCPTool("hub_read_devices", "Read device evidence", {"type": "object"}),
                MCPTool("hub_get_info", "Read hub timezone", {"type": "object"})]

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == "hub_get_info":
            return MCPToolResult(name, args, {}, "ok", {"timeZone": "Europe/London"})
        if name == "hub_search_tools":
            return MCPToolResult(name, args, {}, "ok",
                                 {"results": [{"gateway": "hub_read_devices",
                                               "tool": "hub_list_device_events"}]})
        assert name == "hub_read_devices"
        if args.get("tool") == "hub_list_devices":
            label = str(args.get("args", {}).get("labelFilter", ""))
            return MCPToolResult(name, args, {}, "ok",
                                 {"devices": [d for d in self.devices if d["label"] == label]})
        assert args.get("tool") == "hub_list_device_events"
        ident = str(args["args"]["deviceId"])
        return MCPToolResult(name, args, {}, "ok",
                             {"events": demand_rows("2026-11-07T10:46:57Z" if ident == "43"
                                                    else "2026-11-07T10:49:00Z")})


@pytest.mark.asyncio
async def test_single_user_request_recovers_history_and_continues_related_device_reads():
    from _entity_first_orchestrator_cases import FakeAI
    mcp = AgentMCP()
    expected = ("The thermostat reported heating from 10:49 to 10:58 GMT, about 9 minutes. "
                "The radiator reported demand before that interval; the controller's "
                "actual decision and physical boiler firing remain unverified.")
    ai = FakeAI([
        {"message": {"role": "assistant", "content": json.dumps({
            "version": "1", "domain": "device", "operation": "read",
            "objective": "Establish the interval and related demand",
            "skills": ["diagnostics"],
            "evidenceGoals": ["Most recent interval", "Duration", "Related demand"],
            "requiredEvidenceKinds": ["device_history"],
        })}},
        {"message": {"role": "assistant", "tool_calls": [{"function": {
            "name": "homebrain_device_history",
            "arguments": {"name": "Example Thermostat", "attribute": "switch", "limit": 3}
        }}]}},
        {"message": {"role": "assistant", "tool_calls": [{"function": {
            "name": "homebrain_device_history",
            "arguments": {"name": "Example Radiator", "attribute": "thermostatOperatingState",
                          "hours_back": 24, "limit": 50}
        }}]}},
        *[{"message": {"role": "assistant", "content": expected}} for _ in range(8)],
    ])
    agent = UnifiedMCPAgent(mcp, "fake-key", "test-model", ai_client=ai,
                             causal_subject_prefetch_enabled=False,
                             general_task_engine_enabled=True)
    outcome = await agent.process_user_request_result(
        "When did Example Thermostat last request heat, how long, "
        "and did Example Radiator report demand before it? Do not change anything.")
    ids = [str(args["args"]["deviceId"]) for name, args in mcp.calls
           if name == "hub_read_devices" and args.get("tool") == "hub_list_device_events"]
    assert "42" in ids and "43" in ids
    assert "does not advertise" not in outcome.message
    assert "10:49" in outcome.message and "10:58" in outcome.message
    assert outcome.request_class == "live-read" and not outcome.confirmation_required
    assert all(not row.get("mutates") for row in outcome.evidence)

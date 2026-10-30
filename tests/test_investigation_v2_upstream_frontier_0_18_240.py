"""v0.18.240: live-style upstream-evidence gaps, model autonomy, read safety.

Replays the Oct 30 failure after collecting only target lights and app config.
The cause of missing upstream reads is tested independently of presentation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_upstream_frontier import upstream_evidence_frontier
from investigation_v2.native_read_agent import run_native_read_agent
from investigation_v2.native_entity_lookup import NAME
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG,
)
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_complete_interval_0_18_236 import READ as EVENT_TOOL
from test_investigation_v2_event_narrative_0_18_238 import candidate, ev


QUESTION = (
    "Investigate why Bathroom Light 1 and Bathroom Light 2 turned on and "
    "off on 30 October 2026. Which sensor or controller initiated them? "
    "Read-only."
)

def target_witnesses():
    return [
        {"read": 1, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7818"},
         "source_data": {"events": [
             ev("switch", "2026-10-30T03:40:21.668+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T03:40:21.768+0000", app="4013"),
             ev("level", "2026-10-30T03:40:22.120+0000", "30", device="7790"),
             ev("command-off", "2026-10-30T03:46:05.251+0000", app="1569"),
             ev("switch", "2026-10-30T03:46:05.928+0000", "off", device="7790"),
             ev("switch", "2026-10-30T07:12:33.514+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T07:12:33.560+0000", app="4013"),
         ]}},
        {"read": 2, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7821"},
         "source_data": {"events": [
             ev("switch", "2026-10-30T03:40:22.678+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T03:40:22.778+0000", app="4013"),
             ev("switch", "2026-10-30T07:12:34.589+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T07:12:34.622+0000", app="4013"),
         ]}},
    ]


def test_live_light_histories_expose_missing_upstream_instead_of_command_counts():
    frontier = upstream_evidence_frontier(target_witnesses(), ["7818", "7821"], QUESTION)
    assert frontier["status"] == "upstream_evidence_gap"
    assert set(frontier["verified_target_device_ids"]) == {"7818", "7821"}
    assert frontier["reported_on_observations"] == 4
    assert frontier["reported_on_without_preceding_issuer_command_in_returned_samples"] == 4
    assert frontier["missing_evidence_classes"] == [
        "independent_input_sensor_history", "historical_execution_or_hub_logs"]
    assert frontier["execution_log_read_ids"] == []
    assert "limits" in frontier and "not prove" in frontier["limits"]
    assert not any("Home Assistant caused" in item
                   for item in frontier["recommended_model_choices"])


def test_app_config_metadata_is_not_independent_execution_proof():
    case = target_witnesses() + [{
        "read": 3, "operation": "hub_get_app_config",
        "read_filters": {"appId": "4013"},
        "source_data": {"id": "4013", "settings_key_count": 95,
                        "settings_values_projected": False},
    }]
    frontier = upstream_evidence_frontier(case, ["7818", "7821"], QUESTION)
    assert frontier["configuration_metadata_read_ids"] == [3]
    assert "historical_execution_or_hub_logs" in frontier["missing_evidence_classes"]


def test_sensor_read_and_logs_are_distinct_independent_coverage_classes():
    case = target_witnesses() + [
        {"read": 3, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7908"},
         "source_data": {"events": [
             ev("motion", "2026-10-30T07:12:33.200+0000", "active", device="7908"),
         ]}},
    ]
    frontier = upstream_evidence_frontier(case, ["7818", "7821", "7908"], QUESTION)
    assert frontier["independent_input_history_read_ids"] == [3]
    assert frontier["missing_evidence_classes"] == ["historical_execution_or_hub_logs"]
    case.append({"read": 4, "operation": "hub_get_logs",
                 "read_filters": {"appId": "4013", "mode": "past"},
                 "source_data": {"log_summary": {"returned_rows": 1}}})
    assert upstream_evidence_frontier(case, ["7818", "7821", "7908"], QUESTION) is None


def test_no_unverified_scope_single_target_or_wrong_date_triggers_challenge():
    case = target_witnesses()
    assert upstream_evidence_frontier(case, [], QUESTION) is None
    assert upstream_evidence_frontier(case, ["7818"], QUESTION) is None
    assert upstream_evidence_frontier(case, ["7818", "7821"],
        QUESTION.replace("30 October 2026", "20 October 2026")) is None


@pytest.mark.asyncio
async def test_budget_boundary_allows_model_selected_independent_app_execution_read():
    """Two target histories + source-attested issuer; no host-initiated tool."""
    mcp = FakeMCP([EVENT_TOOL, READ_DIAG])
    async def identities():
        return [{"id": "7818", "label": "Bathroom Light 1"},
                {"id": "7821", "label": "Bathroom Light 2"}]
    mcp.get_device_identities = identities
    data = target_witnesses()
    executor = FakeExecutor(mcp, [
        data[0]["source_data"], data[1]["source_data"],
        {"logs": [{"level": "info", "source": {"id": "4013", "type": "app"},
                   "date": "2026-10-30T07:12:33.900+00:00",
                   "message": "Brightness decision checked"}], "count": 1}
    ])
    rounds = 0
    async def model(messages, tools):
        nonlocal rounds
        rounds += 1
        if rounds <= 2:
            return {"tool_calls": [native(NAME, {
                "name": ("Bathroom Light 1", "Bathroom Light 2")[rounds - 1]})]}
        if rounds <= 4:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": ("7818", "7821")[rounds - 3]},
            })]}
        if rounds == 5:
            assert tools
            assert "independent input" in messages[-1]["content"]
            return {"tool_calls": [native("hub_read_diagnostics", {
                "tool": "hub_get_logs",
                "args": {"mode": "past", "appId": "4013", "limit": 100},
            })]}
        assert tools == []
        assert "upstream_evidence_frontier" in messages[-1]["content"]
        packet = json.loads(messages[-1]["content"])["event_evidence"]
        # The model is still constrained to independently returned events.
        good = {
            "answer": "Both lights reported ON before brightness commands from the controller.",
            "breakdown": [
                {"text": "Bathroom Light 1 reported ON at 03:40.",
                 "supporting_events": [next(
                     {k:e[k] for k in ("read", "device_id", "name", "date")}
                     for e in packet["event_examples"]
                     if e["device_id"] == "7818" and e["name"] == "switch"
                     and "T03:40:" in e["date"])]},
                {"text": "Bathroom Light 2 reported ON at 03:40.",
                 "supporting_events": [next(
                     {k:e[k] for k in ("read", "device_id", "name", "date")}
                     for e in packet["event_examples"]
                     if e["device_id"] == "7821" and e["name"] == "switch"
                     and "T03:40:" in e["date"])]},
            ],
            "uncertainty": "The missing independently attested occupancy input history does not identify the activating controller.",
        }
        return {"content": json.dumps(good)}

    out = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=4, max_reads=6,
    )
    diag = out["native_diagnostics"]
    assert diag["upstream_evidence_challenge_used"] is True
    assert diag["successful_reads"] == 3
    assert diag["read_transport_health"]["state"] == "normal"
    assert diag["upstream_evidence_frontier"] is not None
    assert diag["upstream_evidence_frontier"]["execution_log_read_ids"] == [3]
    assert "independent_input_sensor_history" in diag[
        "upstream_evidence_frontier"]["missing_evidence_classes"]
    assert diag["model_event_narrative"]["accepted"] is True
    assert diag["concise_answer_source"] == "model_scoped_event_narrative"
    assert len(executor.calls) == 3
    assert all(x[0] != "hub_manage_rules" for x in executor.calls)

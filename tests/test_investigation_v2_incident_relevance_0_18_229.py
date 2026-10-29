"""v0.18.229: causal question relevance is not a count of MCP facts.

Replays the independently supplied 24–25 October Livingroom Light 1 failure:
a large command catalog from 28–29 October plus a 24–25 October history
containing only unrelated network events is NOT a natural-language answer.
No device-specific wording or ID is used to trigger the coverage rule.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
from mcp_client import MCPTool

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from investigation_v2.native_incident_relevance import (
    dated_incident_evidence, natural_incident_gap_answer,
)
from investigation_v2.native_answer_brief import evidence_readiness
from investigation_v2.native_history_recovery import normalize_selected_history_read
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor, READ_APPS
from test_investigation_v2_native_entity_lookup_0_18_184 import native

QUESTION = (
    "Investigate why Livingroom Light 1 remained on overnight "
    "24–25 October 2026. Check the actual switch-state history, "
    "controlling automation decisions and motion sensor events during "
    "the relevant period. Identify the most likely reason, using a "
    "concise natural-language answer. Read only; change nothing."
)

READ_EVENTS = MCPTool(
    "hub_read_devices", "Read device and event history",
    {"type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_list_device_events", "hub_get_device"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]},
    annotations={"readOnlyHint": True},
)


def history(read, events, *, device="7805"):
    return {
        "read": read, "operation": "hub_list_device_events",
        "read_filters": {"deviceId": device},
        "source_data": {"events": events},
    }


def old_events():
    return [
        {"name": "networkStatus",
         "date": "2026-10-25T00:20:16.543+01:00",
         "value": "offline"},
        {"name": "command-refresh",
         "date": "2026-10-25T21:12:18.868+00:00",
         "producedBy": {"appId": "4209", "name": "Google Home"}},
    ]


def late_events():
    return [
        {"name": "command-on",
         "date": "2026-10-29T16:14:01.445+00:00",
         "producedBy": {"appId": "1251", "name": "button 1 pushed"}},
        {"name": "command-setLevel",
         "date": "2026-10-28T16:14:01.759+00:00",
         "producedBy": {"appId": "4019", "name": "Light Mode Controller"}},
    ]


def test_bounded_later_command_counts_are_not_incident_evidence():
    rows = [history(1, late_events()), history(2, old_events())]
    coverage = dated_incident_evidence(QUESTION, rows, ["7805"])
    assert coverage is not None
    assert coverage["scoped_event_reads"] == [1, 2]
    assert coverage["material_event_count"] == 0
    assert coverage["outside_incident_command_rows"] == 2
    assert coverage["later_command_rows"] == 2
    result = natural_incident_gap_answer(
        QUESTION, rows, [{"status": "unique", "query": "Livingroom Light 1"}],
        ["7805"])
    assert result is not None
    text, evidence = result
    assert "Livingroom Light 1" in text
    assert "couldn't determine why" in text
    assert "later dates" in text
    assert "controlling automation" in text
    assert "7805" not in text and "4019" not in text and "1251" not in text
    assert "18 recorded commands" not in text
    assert not evidence["incident_answer_evidence_present"]


def test_contemporaneous_device_state_prevents_false_missing_evidence():
    rows = [history(1, old_events() + [{
        "name": "switch", "value": "on",
        "date": "2026-10-24T23:00:00+01:00",
        "producedBy": {"deviceId": "7805", "name": "Livingroom Light 1"},
    }])]
    coverage = dated_incident_evidence(QUESTION, rows, ["7805"])
    assert coverage["material_event_count"] == 1
    assert natural_incident_gap_answer(
        QUESTION, rows, [{"status": "unique", "query": "Livingroom Light 1"}],
        ["7805"]) is None


@pytest.mark.parametrize("text,ids", [
    ("Why is Livingroom Light 1 currently on?", ["7805"]),
    (QUESTION, []),
    (QUESTION, ["7805", "7806"]),
])
def test_no_arbitrary_missing_incident_claim_for_other_scopes(text, ids):
    assert dated_incident_evidence(
        text, [history(1, old_events())], ids) is None


def test_unrelated_device_receipt_does_not_count_toward_target():
    assert dated_incident_evidence(
        QUESTION, [history(1, late_events(), device="7806")],
        ["7805"]) is None


def test_readiness_does_not_mistake_unrelated_fact_types_for_answer():
    sample = [
        {"read": 1, "operation": "hub_list_device_events", "source_data": {}},
        {"read": 2, "operation": "hub_get_app_config", "source_data": {}},
    ]
    catalog = [
        {"id": "claim-1", "kind": "command_issuer", "statement": "issuer",
         "root_cause_verified": False},
        {"id": "claim-2", "kind": "app_metadata", "statement": "metadata",
         "root_cause_verified": False},
        {"id": "claim-3", "kind": "device_observation", "statement": "device",
         "root_cause_verified": False},
    ]
    assert evidence_readiness(sample, catalog,
        stop_reason="round_budget_reached")["host_factual_brief_ready"]
    assert not evidence_readiness(sample, catalog,
        stop_reason="round_budget_reached",
        incident_evidence_present=False)["host_factual_brief_ready"]


def test_too_short_hours_back_replaced_by_requested_date_not_app_choice():
    fixed, receipt = normalize_selected_history_read(
        "hub_read_devices",
        {"tool": "hub_list_device_events",
         "args": {"deviceId": "7805", "hoursBack": 96, "limit": 100}},
        focus_ids={"7805"}, verified_device_ids={"7805"},
        question=QUESTION)
    assert "hoursBack" not in fixed["args"]
    assert "since" in fixed["args"] and "until" in fixed["args"]
    assert receipt["noncovering_relative_window_replaced"]
    assert receipt["historical_window"]["source"] == "explicit_user_calendar_date"
    wrong = {"tool": "hub_list_device_events", "args": {
        "deviceId": "7806", "hoursBack": 96}}
    unchanged, proof = normalize_selected_history_read(
        "hub_read_devices", wrong, focus_ids={"7805"},
        verified_device_ids={"7805"}, question=QUESTION)
    assert unchanged == wrong and proof is None


@pytest.mark.asyncio
async def test_live_like_investigation_stops_publishing_irrelevant_device_ids():
    mcp = FakeMCP([READ_EVENTS, READ_APPS])
    async def identities():
        return [{"id": "7805", "name": "Hue Matter Light",
                 "label": "Livingroom Light 1"}]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [{
        "events": late_events() + old_events()
    }, {
        "settingsPage": {"app": {"id": "4019",
                                 "label": "Light Mode Controller"}},
        "id": "4019", "label": "Light Mode Controller",
    }])
    step = 0
    async def model(messages, tools):
        nonlocal step
        step += 1
        if step == 1:
            return {"tool_calls": [native(
                "homebrain_find_device", {"name": "Livingroom Light 1"})]}
        if step == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7805", "hoursBack": 96, "limit": 100}})]}
        if step == 3:
            # App 4019 is source verified by the event's producedBy.appId.
            return {"tool_calls": [native("hub_read_apps_code", {
                "tool": "hub_get_app_config", "args": {"appId": "4019"}})]}
        return {"content": '{"claims":[]}'}
    out = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=3, max_reads=3)
    diag = out["native_diagnostics"]
    assert len(executor.calls) == 2
    assert executor.calls[0][1]["args"]["since"].startswith("2026-10-23")
    assert "hoursBack" not in executor.calls[0][1]["args"]
    assert diag["requested_incident_evidence_coverage"][
        "incident_answer_evidence_present"] is False
    assert diag["general_evidence_readiness"][
        "dated_incident_evidence_present"] is False
    assert diag["concise_answer_source"] == "requested_incident_evidence_gap"
    assert "Livingroom Light 1" in out["answer"]["text"]
    assert "couldn't determine why" in out["answer"]["text"]
    assert "7805" not in out["answer"]["text"]
    assert "Evidence-based summary" not in out["answer"]["text"]
    assert out["answer"]["root_cause_verified"] is False
    assert diag["successful_reads"] == 2

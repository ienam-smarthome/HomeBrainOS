"""0.17.84 regression: incomplete historical ON still receives bounded follow-up."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from skill_investigation_followup import (
    plan_unverified_next_reads, execute_unverified_next_reads, render_followup_findings,
)
from skill_focal_window import build_focal_source_plan, render_unverified_focal_outcome
from test_skill_missing_focal_0_17_76 import _evicted, QUESTION


def _plan():
    candidate = build_focal_source_plan(_evicted(), QUESTION)
    assert candidate and candidate["producerAppId"] == "4129"
    return candidate


def test_only_exact_command_producer_and_source_gated_reads():
    plan = _plan()
    assert plan_unverified_next_reads(plan, [], app_source_available=False) == []
    selected = plan_unverified_next_reads(plan, [], app_source_available=True)
    assert len(selected) == 1
    assert selected[0]["arguments"] == {"appId": "4129", "includeSettings": False}
    assert selected[0]["gateway"] == "hub_read_apps_code"
    invalid = dict(plan, producerAppId="bad-guess")
    assert plan_unverified_next_reads(invalid, [], app_source_available=True) == []
    wrong_day = dict(plan, requestedOn="2026-10-15T19:55:00+01:00")
    assert plan_unverified_next_reads(wrong_day, [], app_source_available=True) == []


def test_do_not_requery_previous_config_or_verified_focal_source():
    plan = _plan()
    receipt = {"tool":"hub_read_apps_code", "sub_tool":"hub_get_app_config",
               "success":True, "arguments":{"tool":"hub_get_app_config",
                                              "args":{"appId":"4129"}}}
    assert plan_unverified_next_reads(plan, [receipt], app_source_available=True) == []
    verified = {"success": True, "evidence_kind":"focal_archived_state_history",
                "details":{"sourceVerifiedOn":True}}
    assert plan_unverified_next_reads(plan, [verified], app_source_available=True) == []


@pytest.mark.asyncio
async def test_one_read_provides_redacted_current_topology_without_proving_cause():
    plan = _plan()
    invocations = []
    saved = []
    class Catalog:
        def available_tool(self, tool):
            return object() if tool == "hub_read_apps_code" else None
    class MCP:
        async def call_tool(self, gateway, args):
            invocations.append((gateway, args))
            return SimpleNamespace(success=True, data={
                "app": {"id": 4129},
                "page": {"sections": [{"title": "Controls",
                    "paragraphs": [
                        "Event trigger: MQTT touch panel message received",
                        "MQTT password: this-must-not-appear",
                    ]}],
                }
            })
    class Recorder:
        def record(self, tool, arguments, **kw):
            saved.append({"tool":tool, "arguments":arguments, **kw})
    counters = []
    outcomes = await execute_unverified_next_reads(
        plan, receipts=_evicted(), catalog=Catalog(),
        mcp=MCP(), journal=None, recorder=Recorder(),
        tool_succeeded=lambda result: result.success,
        increment_metric=counters.append,
    )
    assert outcomes["producer_config"] == "configuration-checked"
    assert len(invocations) == 1
    assert invocations[0][1]["args"]["appId"] == "4129"
    assert invocations[0][1]["args"]["includeSettings"] is False
    assert saved[0]["evidence_kind"] == "investigator_producer_config"
    assert saved[0]["effect"] == "read" and saved[0]["mutates"] is False
    assert "this-must-not-appear" not in repr(saved)
    assert saved[0]["details"]["historicalExecutionNotProven"] is True
    text = render_followup_findings(saved, "4129")
    assert "MQTT touch panel" in text
    assert "not establish the historical command input" in text


@pytest.mark.asyncio
async def test_allowlisted_archive_counts_only_no_private_messages():
    plan = _plan()
    class Journal:
        enabled=True
        _started=True
        capture_logs=True
        log_app_ids=frozenset({"4129"})
        def query(self, **kwargs):
            assert kwargs["app_id"] == "4129"
            return {"events": [{
                "stream":"logs", "app_id":"4129",
                "message":"password=my-important-secret"
            }], "gaps":[], "truncated":False}
    collected = []
    class Recorder:
        def record(self, tool, arguments, **kw):
            collected.append({"tool":tool, "arguments":arguments, **kw})
    results = await execute_unverified_next_reads(
        plan, receipts=[], catalog=None, mcp=None,
        journal=Journal(), recorder=Recorder(), tool_succeeded=lambda x: True,
        increment_metric=lambda x: None,
    )
    assert results == {"archived_logs":"queried"}
    assert collected[0]["details"]["retainedLogCount"] == 1
    assert "my-important-secret" not in repr(collected)
    assert "password" not in repr(collected)
    assert collected[0]["details"]["redactedMessageBodiesNotReturned"] is True


def test_unverified_answer_cites_new_current_topology_not_execution():
    plan = _plan()
    receipts = _evicted()
    receipts.extend([
        {
            "tool":"hub_read_devices", "sub_tool":"hub_list_device_events",
            "success":True, "evidence_kind":"focal_exact_state_history",
            "arguments":{"tool":"hub_list_device_events", "args":plan["stateRead"]},
            "details":{"label":"Livingroom Light 1",
                       "deviceId":"7805","events":[],
                       "requestedOn":plan["requestedOn"]},
        },
        {
            "tool":"hub_read_apps_code", "sub_tool":"hub_get_app_config",
            "success":True, "evidence_kind":"investigator_producer_config",
            "arguments":{"tool":"hub_get_app_config",
                         "args":{"appId":"4129", "includeSettings":False}},
            "details":{"appId":"4129","identityVerified":True,
                       "configured":["Controls: Event trigger MQTT message"],
                       "historicalExecutionNotProven":True},
        }
    ])
    answer = render_unverified_focal_outcome(plan, receipts, QUESTION)
    assert answer and "Producer topology follow-up" in answer
    assert "Controls: Event trigger MQTT message" in answer
    assert "not independently verified" in answer

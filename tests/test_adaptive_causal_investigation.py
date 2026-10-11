"""Scenario benchmarks for generalized adaptive causal investigation.

All data is synthetic: the bathroom-style case exercises algorithmic search,
not a hardcoded LWR01 exception or a claim about the user's live installation.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_investigation_engine import (
    MAX_EXTRA_SENSOR_READS,
    has_strong_requested_correlated_candidate,
    plan_cross_integration_candidates,
    rank_causal_hypotheses,
    render_ranked_clue,
)
from causal_evidence_planner import (
    build_reporting_source_secondary_analysis,
    render_reporting_source_secondary_summary,
)
from mcp_agent_orchestrator import UnifiedMCPAgent
from mcp_client import MCPToolResult
from request_metrics import RequestMetrics
from technical_metrics_presenter import present_request_metrics


ON_TIMES = [
    "2026-10-11T21:40:26.805+01:00",
    "2026-10-11T21:34:38.228+01:00",
    "2026-10-11T21:32:59.400+01:00",
]
PRECEDING = [
    "2026-10-11T21:40:26.616+01:00",
    "2026-10-11T21:34:38.010+01:00",
    "2026-10-11T21:32:59.218+01:00",
]


def _device(id_: str, label: str, room: str, *,
            state: dict | None = None,
            caps: list[str] | None = None) -> dict:
    return {
        "id": id_,
        "label": label,
        "room": room,
        "capabilities": caps or ["MotionSensor"],
        "attributes": state if state is not None else {"motion": "inactive"},
    }


def _subject():
    return {
        "label": "Bathroom Light 1",
        "deviceId": "7818",
        "room": "Bathroom",
        "correlationEvents": [
            {"name": "switch", "value": "on", "date": stamp}
            for stamp in ON_TIMES
        ],
    }


def _history(label: str, activity: list[str], *,
             values: list[str] | None = None) -> dict:
    return {
        "label": label,
        "attribute": "motion",
        "room": "Integration Devices" if label == "LWR01" else "Bathroom",
        "events": [
            {
                "name": "motion", "value": (values or ["active"] * len(activity))[idx],
                "date": stamp,
                "producedBy": {
                    "label": "HA Device Bridge" if label == "LWR01"
                    else "Matter Aqara Bridge",
                    "type": "device",
                },
            }
            for idx, stamp in enumerate(activity)
        ],
    }


def _analyse(*histories: dict, transition="on") -> dict:
    return build_reporting_source_secondary_analysis(
        _subject(), transition=transition,
        requested_boundary=ON_TIMES[0], sensor_histories=list(histories),
    )


def test_synthetic_cross_integration_candidate_is_discoverable_without_room_match():
    candidates = [
        _device("7818", "Bathroom Light 1", "Bathroom", caps=["Switch"]),
        _device("7746", "Bathroom Hi-P", "Bathroom"),
        _device("8022", "Shower MS605", "Bathroom"),
        _device("9001", "LWR01", "Integration Devices"),
        _device("9002", "Lux-only inherited motion", "Bridge",
                state={"illuminance": 1}, caps=["MotionSensor"]),
        _device("9003", "Unidentified virtual state", "System",
                state={}, caps=["MotionSensor"]),
    ]
    plan = plan_cross_integration_candidates(
        candidates,
        subject="Bathroom Light 1",
        subject_room="Bathroom",
        transition="on",
        tried_ids={"7746", "8022", "7818"},
    )
    labels = [item["name"] for item in plan]
    assert "LWR01" in labels
    assert "Lux-only inherited motion" not in labels
    assert all(item["candidate"]["id"] not in {"7818", "7746", "8022"} for item in plan)


def test_configured_cross_platform_sources_outrank_unrelated_room_sensors():
    identities = [
        _device("1", "Hallway first motion", "Hallway"),
        _device("2", "Kitchen unrelated", "Kitchen"),
        _device("3", "Anonymized occupancy child", "Integration Devices"),
    ]
    known = [{
        "name": "Example external motion lighting",
        "platform": "External controller",
        "triggers": [{"device": "Anonymized occupancy child"}],
        "actions": [{"device": "Hallway Light 1", "transition": "on"}],
    }]
    plan = plan_cross_integration_candidates(
        identities, subject="Hallway Light 1", subject_room="Hallway",
        transition="on", known_automations=known,
    )
    assert plan[0]["name"] == "Anonymized occupancy child"
    assert plan[0]["candidate"]["matchBasis"] == "configured-trigger"
    assert plan[0]["planTier"] == 0


def test_repeated_earlier_events_make_strong_temporal_clue_not_command_proof():
    analysis = _analyse(
        _history("Bathroom Hi-P", ["2026-10-11T21:40:39.109+01:00"]),
        _history("LWR01", PRECEDING),
    )
    ranked = rank_causal_hypotheses(analysis)
    assert ranked[0]["label"] == "LWR01"
    assert ranked[0]["tier"] == "repeated-upstream-correlation"
    assert ranked[0]["precedingMatches"] == 3
    assert ranked[0]["claimLevel"] == "temporal-correlation-only"
    assert has_strong_requested_correlated_candidate(analysis)
    analysis["hypotheses"] = ranked
    clue = render_ranked_clue(analysis)
    assert "LWR01 reported occupancy activity about 0.19s before" in clue
    assert "2 other recent matching transitions" in clue
    assert "NOT proof" in clue
    summary = render_reporting_source_secondary_summary(analysis)
    assert "Best-supported upstream clue" in summary
    assert "Exact initiator unresolved" in summary


def test_nearby_but_later_event_cannot_be_promoted_to_upstream_cause():
    after = [
        "2026-10-11T21:40:27.080+01:00",
        "2026-10-11T21:34:39.100+01:00",
        "2026-10-11T21:32:59.900+01:00",
    ]
    analysis = _analyse(_history("Unrelated motion", after))
    assert not has_strong_requested_correlated_candidate(analysis)
    assert rank_causal_hypotheses(analysis)[0]["tier"] == "reported-after-device"
    assert render_ranked_clue(analysis) is None
    summary = render_reporting_source_secondary_summary(analysis)
    assert "Best-supported upstream clue" not in summary


def test_timezone_mismatched_clock_text_is_not_a_false_requested_match():
    analysis = _analyse(_history("Source", [
        "2026-10-11T21:40:26.616+00:00",  # one hour apart in real time
    ]))
    assert rank_causal_hypotheses(analysis) == []
    assert render_ranked_clue(analysis) is None


def test_bounded_planner_does_not_claim_negative_coverage_for_unread_devices():
    identities = [
        _device(str(i), f"Other sensor {i}", "Integration Devices")
        for i in range(1, 60)
    ]
    plan = plan_cross_integration_candidates(
        identities, subject="Any Light", subject_room="Bathroom",
        transition="on", max_candidates=64,
    )
    assert len(plan) == 59
    assert MAX_EXTRA_SENSOR_READS < len(plan)
    analysis = _analyse()
    analysis["discoveryCoverage"] = {
        "roomFirstAttempted": 2,
        "outsideRoomAttempted": MAX_EXTRA_SENSOR_READS,
        "unexaminedIndexedCandidates": len(plan) - MAX_EXTRA_SENSOR_READS,
        "crossIntegrationInventoryAvailable": True,
    }
    summary = render_reporting_source_secondary_summary(analysis)
    assert "49 indexed cross-integration candidate(s) were not examined" in summary
    assert "not evidence that they did not activate" in summary


class _FakeMCP:
    def __init__(self, *, external_times=None) -> None:
        self.identities = [
            _device("7818", "Bathroom Light 1", "Bathroom",
                    caps=["Switch"], state={"switch": "on"}),
            _device("7746", "Bathroom Hi-P", "Bathroom"),
            _device("8000", "Shower MS605", "Bathroom"),
            _device("9001", "LWR01", "Integration Devices"),
        ]
        self.external_times = external_times or PRECEDING

    def peek_device_identities(self):
        return [dict(row) for row in self.identities]


class _FakeExecutor:
    def __init__(self, mcp: _FakeMCP):
        self.mcp = mcp
        self.calls: list[dict] = []

    async def execute(self, name, arguments, **kwargs):
        self.calls.append(dict(arguments))
        subject = arguments["name"]
        if subject == "Bathroom Light 1":
            data = {**_subject(), "events": []}
        elif subject == "Bathroom Hi-P":
            data = _history(subject, ["2026-10-11T21:40:39.109+01:00"])
        elif subject == "Shower MS605":
            data = _history(subject, ["2026-10-11T21:40:27.000+01:00"])
        elif subject == "LWR01":
            data = _history(subject, self.mcp.external_times)
        else:
            raise AssertionError("Unexpected sensor history " + subject)
        return SimpleNamespace(
            success=True,
            result=MCPToolResult(name, arguments, {}, "ok", data),
        )


class _Catalog:
    def declared_tool(self, _name):
        return object()


class _Recorder:
    def __init__(self):
        self.rows = []

    def record(self, tool, arguments, **kwargs):
        self.rows.append({"tool": tool, "arguments": arguments, **kwargs})


@pytest.mark.asyncio
async def test_host_pipeline_escapes_room_candidate_limit_and_finds_bridge_sensor():
    mcp = _FakeMCP()
    executor, recorder = _FakeExecutor(mcp), _Recorder()
    host = SimpleNamespace(
        mcp=mcp, executor=executor, evidence=recorder,
        known_automations=[],
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        await UnifiedMCPAgent._collect_reporting_source_secondary_correlation(
            host, subject_history=_subject(), transition="on",
            boundary_match={"stateBoundary": ON_TIMES[0]},
            catalog=_Catalog(), completed_calls=set(),
        )
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)
    result = next(
        r for r in recorder.rows
        if r["tool"] == "homebrain_causal_secondary_correlation"
    )["details"]
    assert result["hypotheses"][0]["label"] == "LWR01"
    assert result["hypotheses"][0]["tier"] == "repeated-upstream-correlation"
    assert result["discoveryCoverage"]["outsideRoomAttempted"] == 1
    assert snapshot["counters"]["causal_adaptive_sensor_reads"] == 1
    assert snapshot["counters"]["causal_adaptive_sufficient_stop"] == 1
    assert [c["name"] for c in executor.calls].count("LWR01") == 1
    assert "NOT proof" in render_reporting_source_secondary_summary(result)


@pytest.mark.asyncio
async def test_host_pipeline_does_not_treat_late_bridge_event_as_initiator():
    mcp = _FakeMCP(external_times=[
        "2026-10-11T21:40:27.080+01:00",
        "2026-10-11T21:34:39.100+01:00",
        "2026-10-11T21:32:59.900+01:00",
    ])
    recorder = _Recorder()
    host = SimpleNamespace(
        mcp=mcp, executor=_FakeExecutor(mcp), evidence=recorder,
        known_automations=[],
    )
    await UnifiedMCPAgent._collect_reporting_source_secondary_correlation(
        host, subject_history=_subject(), transition="on",
        boundary_match={"stateBoundary": ON_TIMES[0]},
        catalog=_Catalog(), completed_calls=set(),
    )
    result = recorder.rows[-1]["details"]
    assert not has_strong_requested_correlated_candidate(result)
    assert not any(
        row["tier"] == "repeated-upstream-correlation"
        for row in result["hypotheses"]
    )
    assert "Best-supported upstream clue" not in (
        render_reporting_source_secondary_summary(result) or ""
    )


def test_adaptive_counters_have_presenter_labels():
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_adaptive_expansion")
        metrics.increment("causal_adaptive_sensor_reads", 3)
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)
    rendered = present_request_metrics(snapshot)
    assert {"label": "Cross-integration history reads", "value": "3"} in rendered

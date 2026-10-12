"""Request-scoped evidence-budgets, reused command reads and repair observability.

Tests model a generic physical-controller ON sequence. The same invariants
must hold for any platform or room: repeat correlation is a SEARCH STOP, not
proof of native mapping; never claim universal history from partial matches.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_investigation_engine import (  # noqa: E402
    has_repeated_requested_controller_candidate,
)
from causal_evidence_graph import (  # noqa: E402
    build_causal_evidence_graph, supports_one_pass_deep_synthesis,
)
from causal_coverage_claim_guard import (  # noqa: E402
    guard_causal_controller_history_coverage,
)
from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402
from test_causal_physical_event_0_17_12 import (  # noqa: E402
    _physical_evidence, QUESTION,
)


def _controller_analysis():
    rows = _physical_evidence()
    analysis = dict(rows[1]["details"])
    analysis.update(
        transition="on",
        requestedBoundary="2026-10-12T08:16:10.861+0100",
    )
    return analysis


def test_repeated_button_alignment_stops_cross_room_discovery_but_is_not_proof():
    analysis = _controller_analysis()
    assert has_repeated_requested_controller_candidate(analysis)
    graph = build_causal_evidence_graph(_physical_evidence(), QUESTION)
    assert graph["controllerCandidate"]["directControllerToDeviceMappingProven"] is False

    competitor = {
        "label": "Other dimmer",
        "relevantAlignments": list(analysis["controllers"][0]["relevantAlignments"]),
    }
    analysis["controllers"].append(competitor)
    assert not has_repeated_requested_controller_candidate(analysis)


def test_later_unrelated_or_mixed_button_values_do_not_qualify():
    analysis = _controller_analysis()
    analysis["controllers"][0]["relevantAlignments"][0]["eventValue"] = "2"
    analysis["controllers"][0]["relevantAlignments"][1]["eventValue"] = "3"
    assert not has_repeated_requested_controller_candidate(analysis)
    analysis = _controller_analysis()
    for row in analysis["controllers"][0]["relevantAlignments"]:
        row["signedDeltaSeconds"] = 4.0
    assert not has_repeated_requested_controller_candidate(analysis)
    analysis = _controller_analysis()
    analysis["transition"] = "off"
    assert not has_repeated_requested_controller_candidate(analysis)


def _coverage_evidence():
    evidence = _physical_evidence()
    # One earlier ON had a genuinely different direct command producer.
    evidence[0]["details"]["commandEvents"].append({
        "name": "command-on",
        "date": "2026-10-12T07:25:37.504+0100",
        "description": "Command called: on()",
        "producedBy": {
            "type": "app", "id": "2355", "label": "Dashboard API"
        },
    })
    return evidence


def test_graph_coverage_exposes_unmatched_start_and_other_command_origin():
    graph = build_causal_evidence_graph(_coverage_evidence(), QUESTION)
    coverage = graph["controllerCoverage"]
    assert coverage["observedStartCount"] == 4
    assert coverage["alignedObservedStartCount"] == 3
    assert coverage["unmatchedObservedStartCount"] == 1
    assert coverage["scope"] == "returned-observed-intervals-only"
    assert coverage["confirmedOtherCommandStarts"][0]["appId"] == "2355"


def test_universal_button_history_claim_corrected_without_downgrading_valid_scope():
    draft = (
        "The correlation between the dimmer button and every light-on interval "
        "in the provided history is strong.\n"
        "It also matched all three recent button-aligned events.\n"
        "The direct command from App 4015 adjusted brightness after ON."
    )
    corrected, changed = guard_causal_controller_history_coverage(
        draft, _coverage_evidence(), QUESTION
    )
    assert changed
    assert "3 of 4 observed ON intervals" in corrected
    assert "all three recent button-aligned events" in corrected
    assert "App 4015" in corrected
    corrected_again, repeat = guard_causal_controller_history_coverage(
        corrected, _coverage_evidence(), QUESTION
    )
    assert not repeat
    assert corrected_again == corrected


def test_api_stage_can_derive_focal_event_from_verified_correlation_not_model_text():
    rows = _coverage_evidence()
    rows[1]["details"]["requestedBoundary"] = (
        "2026-10-12T08:16:10.861+0100"
    )
    draft = "The dimmer button was linked to every light-on interval in the recorded history."
    fixed, changed = guard_causal_controller_history_coverage(draft, rows)
    assert changed
    assert "3 of 4 observed ON intervals" in fixed


class _Catalogue:
    def available_tool(self, name):
        return object()


class _Recorder:
    def __init__(self):
        self.rows = []

    def record(self, tool, arguments, **kwargs):
        self.rows.append({"tool": tool, "arguments": arguments, **kwargs})


class _MCP:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        leaf = arguments["tool"]
        if leaf == "hub_get_app_config":
            data = {"app": {"id": "4015"}, "settings": {}}
        elif leaf == "hub_get_logs":
            data = {"logs": []}
        else:
            raise AssertionError(f"Already-known command must not be read again: {leaf}")
        return MCPToolResult(name, arguments, {}, "ok", data)


@pytest.mark.asyncio
async def test_host_reuses_existing_positive_post_on_command_without_second_mcp_read():
    from test_causal_physical_event_0_17_12 import _base_history
    subject = dict(_base_history()[0]["details"])
    subject["deviceId"] = "7840"
    subject["commandEvents"] = [{
        "name": "command-setLevel",
        "date": "2026-10-12T08:16:10.912+0100",
        "description": "Command called: setLevel(45)",
        "producedBy": {"type": "app", "id": "4015"},
    }]
    mcp, recorder = _MCP(), _Recorder()
    host = SimpleNamespace(mcp=mcp, evidence=recorder)
    metric = RequestMetrics()
    token = metric.begin()
    try:
        await UnifiedMCPAgent._collect_physical_response_evidence(
            host, subject_history=subject,
            boundary_match={
                "stateBoundary": "2026-10-12T08:16:10.861+0100",
                "event": {"triggered": [
                    {"appId": 4015, "handler": "lightSwitchHandler"}
                ]},
            },
            catalog=_Catalogue(), completed_calls=set()
        )
        snapshot = metric.snapshot()
    finally:
        metric.reset(token)
    leaves = [args["tool"] for _, args in mcp.calls]
    assert leaves == ["hub_get_app_config", "hub_get_logs"]
    assert snapshot["counters"]["causal_physical_command_reused"] == 1
    assert snapshot["counters"]["causal_physical_response_reads"] == 2


def test_graph_accepts_already_prefetched_positive_level_provenance():
    rows = _physical_evidence(include_post=False)
    rows[0]["details"]["commandEvents"] = [{
        "name": "command-setLevel",
        "date": "2026-10-12T08:16:10.912+0100",
        "description": "Command called: setLevel(45)",
        "producedBy": {"id": "4015", "type": "app", "label": "Example Lighting Mode Controller"},
    }]
    graph = build_causal_evidence_graph(rows, QUESTION)
    assert graph["postOnCommandHistoryChecked"]
    assert graph["physicalEvidenceComplete"]
    assert supports_one_pass_deep_synthesis(graph, QUESTION)


@pytest.mark.asyncio
async def test_complete_graph_uses_localized_fix_without_repeating_provider_round(monkeypatch):
    from importlib import import_module
    module = import_module("final_answer_coordinator")
    monkeypatch.setattr(
        module, "validate_synthesis",
        lambda draft, *_args, **_kwargs: (
            draft.replace("every ON interval", "3 of 4 recorded intervals"),
            ["causal_controller_history_coverage"],
        )
    )
    calls = []
    async def chat(messages, tools):
        calls.append((messages, tools))
        return {"content": "The dimmer button aligned with every ON interval."}
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        coordinator = FinalAnswerCoordinator(
            chat, evidence_supplier=lambda: _physical_evidence()
        )
        result = await coordinator.answer([{"role": "user", "content": QUESTION}])
        state = metrics.snapshot()
    finally:
        metrics.reset(token)
    assert "3 of 4 recorded intervals" in result
    assert len(calls) == 1
    assert state["counters"]["synthesis_validation_issues"] == 1
    assert state["counters"]["synthesis_localized_corrections"] == 1
    assert state["counters"].get("synthesis_repair_rounds", 0) == 0


@pytest.mark.asyncio
async def test_genuine_coverage_gap_records_why_second_provider_round_was_needed(monkeypatch):
    from importlib import import_module
    module = import_module("final_answer_coordinator")
    calls = []
    async def chat(messages, tools):
        calls.append((messages, tools))
        return {"content": "Rewritten with caveat." if len(calls) > 1 else "Initial answer."}
    def fake_validator(draft, *_args, **_kwargs):
        if draft == "Initial answer.":
            return draft, ["causal_timeline_coverage:missing-interval"]
        return draft, []
    monkeypatch.setattr(module, "validate_synthesis", fake_validator)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        coordinator = FinalAnswerCoordinator(chat, evidence_supplier=lambda: [])
        result = await coordinator.answer([{"role": "user", "content": QUESTION}])
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)
    assert result == "Rewritten with caveat."
    assert len(calls) == 2
    assert snapshot["counters"]["synthesis_repair_rounds"] == 1
    assert snapshot["counters"]["synthesis_repair_causal_coverage"] == 1
    assert {"label": "Extra synthesis model rounds", "value": "1"} in (
        present_request_metrics({"counters": snapshot["counters"], "timings_ms": {}})
    )

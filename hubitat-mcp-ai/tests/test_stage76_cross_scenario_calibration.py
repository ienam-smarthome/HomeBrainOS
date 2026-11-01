"""Stage 7.6 cross-scenario synthetic causal calibration and clock provenance.

No production device calls, no Ollama inference, no semantic self-certification.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import _CASES, Stage6Benchmark  # noqa: E402
from stage75_evidence_answer_review import _command_order  # noqa: E402
from webui import render_page  # noqa: E402


def sentence(text, kind, ids, *, position="affirmed", atoms=None):
    return {
        "text": text, "kind": kind, "evidence_ids": ids,
        "atoms": [] if atoms is None else atoms,
        "epistemic": {"position": position, "scope": "examined_records"},
    }


def model_answer(case):
    if case == "clock_conflict":
        statements = [
            sentence("The bridge-reported OFF device time predates the ON source time.",
                     "time_order_conflict", ["E2", "E3"]),
            sentence("The report receipt order is different from device source-time order.",
                     "timestamp_basis", ["E2", "E3"]),
            sentence("Actual physical operation and clock accuracy are not established.",
                     "physical_confirmation", ["E2", "E3"], position="not_established"),
        ]
    elif case == "stale_connectivity":
        statements = [
            sentence("The MQTT driver reported its broker connection active.",
                     "broker_session", ["E1"]),
            sentence("The last independent plug packet was recorded separately.",
                     "device_telemetry", ["E2"]),
            sentence("The OFF command is recorded, but whether it caused disconnection is unknown.",
                     "unique_cause", ["E2", "E3", "I1"], position="not_established"),
        ]
    else:
        statements = [
            sentence("The Inactivity App issued an OFF command.", "command_record", ["E1"]),
            sentence("The Button App issued setLevel 40.", "command_record", ["E2"]),
            sentence("The collector reported OFF, not a verified physical response.",
                     "state_report", ["I1"]),
            sentence("The unique cause is not established by examined records.",
                     "unique_cause", ["E1", "E2", "I1"], position="not_established"),
        ]
    return {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": statements,
        "uncertainties": ["Physical cause and/or clock accuracy require independent evidence"],
        "next_evidence": "Obtain command-correlated execution records with source and collector clocks",
    }


class ScenarioCloud:
    api_key = "synthetic-private-key"
    base_url = "https://ollama.com"
    model_name = "gemma4:31b-cloud"
    timeout_seconds = 60
    configured = True

    def __init__(self, case):
        self.case = case
        self.calls = []

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append(messages)
        assert tools == [] and kwargs["disable_thinking"] is True
        all_messages = json.dumps(messages)
        assert "synthetic-private-key" not in all_messages
        assert "reference_evidence_record_ids" not in all_messages
        assert "stage75_evidence_answer_review" not in all_messages
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            index = len(body["sources_already_examined"])
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1", "action": "read",
                "source_id": ["S1", "S2", "S3"][index],
                "reason": "Inspect fictional evidence relevant to this question",
            })}
        assert "device observation from" in messages[0]["content"]
        assert "command-correlated execution receipt" in messages[0]["content"]
        return {"content": json.dumps(model_answer(self.case))}


@pytest.mark.parametrize("case", list(_CASES))
def test_full_three_scenario_mock_no_extra_requests_or_publisher(case):
    model = ScenarioCloud(case)
    result = asyncio.run(Stage6Benchmark().run_case(
        model, case, confirmed=True))
    assert len(model.calls) == result["cloud_requests_attempted"] == 4
    assert result["independent_review_packet"]["publisher_approval"] is False
    review = result["independent_review_packet"]["stage75_evidence_answer_review"]
    assert review["source_evidence"]["host_observable_reference_type_coverage"] == (
        f"{len(_CASES[case]['required_types'])}/{len(_CASES[case]['required_types'])}")
    assert review["additional_cloud_requests"] == 0
    assert review["natural_language_factual_semantics_verified"] is False
    assert review["causal_evidence_ladder"]["unique_causal_attribution_proven"] is False
    assert result["independent_review_packet"]["suggested_next_evidence_review"][
        "human_review_verdict"] == "not_reviewed"
    assert "synthetic-private-key" not in json.dumps(result)
    if case == "competing_commands":
        ladder = review["causal_evidence_ladder"]
        assert ladder["recorded_command_ids"] == ["E1", "E2"]
        assert ladder["recorded_command_display_order_basis"] == (
            "recorded_utc_time_of_day_only_not_cross_day_or_execution_proof")
        assert [x["recorded_at"] for x in ladder["recorded_command_timeline"]] == [
            "23:10:27Z", "23:10:29Z"]
        assert review["source_evidence"]["model_declared_reference_type_coverage"] == "2/3"
    if case == "clock_conflict":
        reports = review["causal_evidence_ladder"]["state_report_clock_receipts"]
        assert next(x for x in reports if x["record_id"] == "E2")[
            "source_time"] == "20:01:10Z"
        assert next(x for x in reports if x["record_id"] == "E2")[
            "received_at"] == "20:02:18Z"
        assert review["causal_evidence_ladder"]["source_timestamp_is_not_independent_telemetry"]
    if case == "stale_connectivity":
        ladder = review["causal_evidence_ladder"]
        assert ladder["driver_broker_session_ids"] == ["E1"]
        assert ladder["broker_session_alone_proves_device_online"] is False
        assert ladder["independent_device_telemetry_ids"] == ["E2"]


@pytest.mark.parametrize("bad", [None, "", "bad", "23:60:00Z", "24:00:00Z",
                                  "23:00:60Z", "2026-11-01T23:00:00Z"])
def test_noncomparable_command_clock_does_not_claim_chronology(bad):
    records = [{"id": "A", "at": bad}, {"id": "B", "at": "23:10:29Z"}]
    ordered, basis = _command_order(records)
    assert [x["id"] for x in ordered] == ["A", "B"]
    assert basis == "source_order_not_chronological"


def test_mixed_clock_bases_do_not_get_sorted():
    records = [
        {"id": "B", "at": "23:10:29Z", "clock_basis": "collector"},
        {"id": "A", "at": "23:10:27Z", "clock_basis": "device"},
    ]
    ordered, basis = _command_order(records)
    assert [x["id"] for x in ordered] == ["B", "A"]
    assert basis == "mixed_clock_bases_not_comparable"


def test_same_clock_record_order_not_physical_execution():
    records = [
        {"id": "later", "at": "23:10:29Z"},
        {"id": "earlier", "at": "23:10:27Z"},
    ]
    ordered, basis = _command_order(records)
    assert [x["id"] for x in ordered] == ["earlier", "later"]
    assert "not_cross_day_or_execution_proof" in basis


def test_stage76_mobile_and_human_followup_review_not_autocertified():
    html = render_page("HomeBrainOS", "0.18.308")
    for phrase in [
        "Recorded times do not prove actual execution or cross-day order",
        "Broker session evidence:", "source time ", "collector receipt ",
        "Can the suggested next evidence establish what Gemma claims?",
        "next_evidence_quality", "followupControl.value!=='not_reviewed'",
        "Other unsupported typed statements (not a false-fact count)",
        "Not fully source-value-audited:",
        "production_publication_approval:false",
    ]:
        assert phrase in html


def test_production_source_isolation():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        source = (APP / name).read_text()
        assert "stage75_evidence_answer_review" not in source
        assert "stage76" not in source

"""Stage 7.7: independently observed time inversions and source coverage.

All fixtures are fictional, model calls mocked; no production routing changes.
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
from stage72_answer_coverage import build_answer_coverage_review  # noqa: E402
from stage77_relationship_review import build_stage77_review  # noqa: E402
from stage7_review_packet import build_review_packet  # noqa: E402
from webui import render_page  # noqa: E402


def draft(case):
    initial = _CASES[case]["initial"]
    return {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": [{
            "text": "The reported state is not proof of an actual physical outcome.",
            "kind": "state_report", "evidence_ids": ["I1"], "atoms": [],
            "epistemic": {"position": "affirmed", "scope": "examined_records"},
        }],
        "uncertainties": ["Cause and source clock accuracy are unresolved"],
        "next_evidence": "Read independently sourced device and controller execution logs",
    }


def review(case, selected):
    fixture = _CASES[case]
    return build_stage77_review(
        fixture, selected,
        build_answer_coverage_review(case, fixture, selected, draft(case)),
    )


def test_temporal_inversion_detects_source_vs_receipt_without_physical_certainty():
    x = review("clock_conflict", ["S1", "S2", "S3"])
    assert x["source_receipt_inversion_count"] == 1
    inv = x["source_receipt_order_inversions"][0]
    assert inv["source_time_order_ids"] == ["E2", "E3"]
    assert inv["receipt_time_order_ids"] == ["E3", "E2"]
    assert inv["source_times"] == ["20:01:10Z", "20:02:09Z"]
    assert inv["receipt_times"] == ["20:02:13Z", "20:02:18Z"]
    assert inv["source_clock_accuracy_proven"] is False
    assert inv["proves_physical_event_order"] is False
    assert not x["postrun_critical_reference_gaps"]


def test_stale_mqtt_run_reports_skipped_broker_evidence_without_controlling_reads():
    x = review("stale_connectivity", ["S4", "S3", "S2"])
    assert x["source_receipt_order_inversions"] == []
    missing = x["postrun_critical_reference_gaps"]
    assert missing == [{"obligation_id": "broker_vs_device",
                        "missing_record_ids": ["E1"]}]
    status = x["transport_and_device_evidence"]
    assert status["broker_session_ids"] == []
    assert status["watchdog_tick_ids"] == ["E4"]
    assert status["independent_device_packet_ids"] == ["E2"]
    assert status["watchdog_tick_is_not_device_origin_telemetry"]
    assert status["device_packet_origin_does_not_authenticate_source_clock_accuracy"]
    assert x["postrun_reference_gaps_never_control_model_reads"]


def test_broker_evidence_read_removes_missing_critical_obligation():
    x = review("stale_connectivity", ["S1", "S2", "S3"])
    assert x["postrun_critical_reference_gaps"] == []
    assert x["transport_and_device_evidence"]["broker_session_ids"] == ["E1"]
    assert x["transport_and_device_evidence"]["broker_connection_is_not_device_online_proof"]


@pytest.mark.parametrize("choices", [["S1", "S1"], ["S999"], ["S1"] * 4])
def test_rejects_invalid_source_selections(choices):
    with pytest.raises(ValueError):
        review("stale_connectivity", choices)


def test_dishonest_text_never_becomes_source_or_semantic_proof():
    fixture = _CASES["clock_conflict"]
    bad = draft("clock_conflict")
    bad["sentences"][0]["text"] = "These records prove the light physically turned OFF after it turned ON."
    packet = build_review_packet("clock_conflict", fixture, ["S1", "S2", "S3"], bad)
    assert packet["stage77_relationship_review"]["source_receipt_inversion_count"] == 1
    assert packet["stage77_relationship_review"]["natural_language_semantics_certified"] is False
    assert packet["prose_fully_verified"] is False
    assert packet["publisher_approval"] is False
    assert len(json.dumps(packet)) < 32000


class FakeCloud:
    base_url = "https://ollama.com"
    model_name = "gemma4:31b-cloud"
    api_key = "mock-private-secret"
    timeout_seconds = 60
    configured = True

    def __init__(self):
        self.calls = []

    async def _chat_post(self, messages, tools, **kwargs):
        assert tools == [] and kwargs["disable_thinking"]
        self.calls.append(messages)
        text = json.dumps(messages)
        assert "mock-private-secret" not in text
        assert "reference_evidence_record_ids" not in text
        assert "postrun_critical_reference_gaps" not in text
        input_data = json.loads(messages[1]["content"])
        assert input_data["scenario_title"] == _CASES["stale_connectivity"]["title"]
        if "remaining_source_titles" in input_data:
            assert "SCENARIO TITLE" in messages[0]["content"]
            index = len(input_data["sources_already_examined"])
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1", "action": "read",
                "source_id": ["S1", "S2", "S3"][index],
                "reason": "Read a distinct source relevant to the original question",
            })}
        assert "explicitly compare their event-report orders" in messages[0]["content"]
        return {"content": json.dumps(draft("stale_connectivity"))}


def test_stage77_four_request_mock_does_not_leak_reference_or_publish():
    model = FakeCloud()
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "stale_connectivity", confirmed=True))
    assert result["cloud_requests_attempted"] == len(model.calls) == 4
    review_packet = result["independent_review_packet"]
    assert review_packet["stage77_relationship_review"]["postrun_critical_reference_gaps"] == []
    assert review_packet["stage77_relationship_review"]["additional_cloud_requests"] == 0
    assert review_packet["publisher_approval"] is False
    assert "mock-private-secret" not in json.dumps(result)


def test_mobile_shows_temporal_inversion_and_missing_critical_record():
    html = render_page("HomeBrainOS", "0.18.309")
    for fragment in (
        "Stage 7.7 · Missing evidence and clock-order comparisons",
        "source_receipt_order_inversions",
        "postrun_critical_reference_gaps",
        "Watchdog ticks:",
        "physical sequence not proven",
        "production_publication_approval:false",
    ):
        assert fragment in html


def test_no_production_imports_or_publication_authority():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage77_relationship_review" not in (APP / name).read_text()

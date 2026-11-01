"""Stage 7.8.1: recover factual reports from malformed *optional* advice only.

Synthetic fixtures and mocked cloud requests. Never recover invalid claims or
source citations, and never render the rejected follow-up payload.
"""
import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import _CASES, _validate_answer, Stage6Benchmark
from stage7_review_packet import build_review_packet
from webui import render_page


def example():
    return {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": [{
            "text": "The device was reported offline by the watchdog.",
            "kind": "state_report", "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "offline"}],
            "epistemic": {"position": "affirmed", "scope": "examined_records"},
        }],
        "uncertainties": ["Physical cause not established from examined records"],
        "next_evidence": "Inspect a bounded history of device-origin telemetry.",
        "next_evidence_assessment": {
            "proposal_kind": "device_telemetry",
            "could_establish": "The recorded sequence of device packets.",
            "cannot_establish": "Which application caused the final state.",
            "additional_proof_needed": "A command-correlated execution acknowledgement.",
        },
    }


@pytest.mark.parametrize("bad", [None, 123, [], {},
                                {"proposed_source": "watchdog"},
                                "x", "a" * 221])
def test_invalid_v3_next_evidence_is_withheld_not_fatal(bad):
    raw = example()
    raw["next_evidence"] = bad
    validated = _validate_answer(json.dumps(raw), [_CASES["stale_connectivity"]["initial"]])
    assert validated["next_evidence"] == ""
    assert validated["_followup_validation"] == {
        "next_evidence": "invalid_or_missing"}
    packet = build_review_packet("stale_connectivity", _CASES["stale_connectivity"],
                                 ["S1", "S2", "S3"], validated)
    model = packet["stage78_followup_sufficiency_review"]["model_proposal"]
    assert model["next_evidence_text"] == ""
    assert model["next_evidence_validated_as_bounded_string"] is False
    assert packet["publisher_approval"] is False
    assert packet["author_suggested_next_evidence"] == ""
    assert packet["prose_fully_verified"] is False


def test_missing_optional_fields_yield_explicit_unaudited_review():
    raw = example()
    del raw["next_evidence"]
    del raw["next_evidence_assessment"]
    validated = _validate_answer(json.dumps(raw), [_CASES["stale_connectivity"]["initial"]])
    assert validated["_followup_validation"]["next_evidence"] == "invalid_or_missing"
    packet = build_review_packet("stale_connectivity", _CASES["stale_connectivity"],
                                 ["S1", "S2", "S3"], validated)
    review = packet["stage78_followup_sufficiency_review"]
    assert review["model_proposal"]["assessment"] is None
    assert review["human_review"]["could_prove_claimed_conclusion"] == "not_reviewed"


@pytest.mark.parametrize("bad", [
    None, [], "device_telemetry", {"proposal_kind": "device_telemetry"},
    {"proposal_kind": "watchdog_tick", "could_establish": "x",
     "cannot_establish": "anything", "additional_proof_needed": "nothing"},
])
def test_invalid_v3_declaration_is_withheld_not_fatal(bad):
    raw = example()
    raw["next_evidence_assessment"] = bad
    validated = _validate_answer(json.dumps(raw), [_CASES["stale_connectivity"]["initial"]])
    assert "next_evidence_assessment" not in validated
    assert validated["_followup_validation"] == {"next_evidence_assessment": "invalid"}
    assert validated["next_evidence"] == raw["next_evidence"]
    packet = build_review_packet("stale_connectivity", _CASES["stale_connectivity"],
                                 ["S1", "S2", "S3"], validated)
    m = packet["stage78_followup_sufficiency_review"]["model_proposal"]
    assert m["declaration_present"] is False
    assert m["next_evidence_validated_as_bounded_string"] is True
    assert m["field_status"]["next_evidence_assessment"] == "invalid"


def test_invalid_optional_fields_do_not_waive_core_checks():
    sample = example()
    sample["next_evidence"] = {"bad": "shape"}
    sample["sentences"][0]["evidence_ids"] = ["Unknown"]
    with pytest.raises(ValueError, match="citation"):
        _validate_answer(json.dumps(sample), [_CASES["stale_connectivity"]["initial"]])
    sample["sentences"][0]["evidence_ids"] = ["I1"]
    sample["sentences"][0]["atoms"][0]["value"] = "on"
    # Source-value claims remain independently audited, not auto-certified.
    validated = _validate_answer(json.dumps(sample), [_CASES["stale_connectivity"]["initial"]])
    assert validated["sentences"][0]["atoms"][0]["value"] == "on"
    assert validated["_followup_validation"]["next_evidence"] == "invalid_or_missing"
    sample["sentences"][0]["text"] = "x"
    with pytest.raises(ValueError, match="sentence text"):
        _validate_answer(json.dumps(sample), [_CASES["stale_connectivity"]["initial"]])


def test_valid_v3_model_output_unchanged():
    original = example()
    assert _validate_answer(json.dumps(original), [_CASES["stale_connectivity"]["initial"]]) == original


def test_previous_versions_remain_strict_about_next_evidence():
    old = example()
    old["schema"] = "homebrain-stage6-answer.v2"
    old["sentences"][0].pop("epistemic")
    old.pop("next_evidence_assessment")
    old["next_evidence"] = {}
    with pytest.raises(ValueError, match="follow-up"):
        _validate_answer(json.dumps(old), [_CASES["stale_connectivity"]["initial"]])


class MockCloud:
    base_url = "https://ollama.com"
    model_name = "gemma4:31b-cloud"
    api_key = "not-for-output"
    timeout_seconds = 60
    configured = True

    def __init__(self):
        self.calls = []

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append(messages)
        assert tools == [] and kwargs["disable_thinking"] is True
        assert "gold_sources" not in json.dumps(messages)
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            i = len(body["sources_already_examined"])
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1",
                "action": "read", "source_id": ["S2", "S3", "S1"][i],
                "reason": "Select a relevant independent record",
            })}
        data = example()
        data["next_evidence"] = {"suggestion": "malformed optional output"}
        return {"content": json.dumps(data)}


def test_four_cloud_calls_and_preserved_primary_answer():
    cloud = MockCloud()
    out = asyncio.run(Stage6Benchmark().run_case(
        cloud, "stale_connectivity", confirmed=True))
    assert len(cloud.calls) == out["cloud_requests_attempted"] == 4
    assert out["success"] is True
    assert "reported offline" in out["answer"]
    assert out["recommended_next_evidence"] == ""
    assert out["independent_review_packet"]["publisher_approval"] is False
    assert out["independent_review_packet"]["stage78_followup_sufficiency_review"][
        "model_proposal"]["field_status"]["next_evidence"] == "invalid_or_missing"


def test_mobile_displays_invalid_optional_advice_without_false_approval():
    html = render_page("HomeBrainOS", "0.18.311")
    for item in ("No validated AI follow-up suggestion was provided",
                 "The optional AI follow-up suggestion was missing or invalid",
                 "still require independent review",
                 "production_publication_approval:false"):
        assert item in html


def test_production_modules_remain_unmodified():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage78_followup_contract" not in (APP / name).read_text()

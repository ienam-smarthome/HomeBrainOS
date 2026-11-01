"""Stage 7.8 evidence sufficiency contract and independent human reviewer.

Mock-only. No real Cloud calls, device reads, publisher activation or
automatic natural-language entailment certification.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import (  # noqa: E402
    _CASES, _validate_answer, Stage6Benchmark,
)
from stage78_followup_sufficiency import (  # noqa: E402
    build_stage78_review, validate_followup_assessment,
)
from stage7_review_packet import build_review_packet  # noqa: E402
from webui import render_page  # noqa: E402


def model_proposal(kind="watchdog_history"):
    return {
        "proposal_kind": kind,
        "could_establish": "Observe a bounded series of periodic driver checks.",
        "cannot_establish": "A single tick cannot pinpoint when the physical connection was lost.",
        "additional_proof_needed": "Time-bounded watchdog transitions and independent plug activity.",
    }


def draft(kind="watchdog_history", *, include=True):
    base = {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": [{
            "text": "The plug was reported offline by the watchdog.",
            "kind": "state_report", "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "offline"}],
            "epistemic": {"position": "affirmed", "scope": "examined_records"},
        }],
        "uncertainties": ["Physical execution and precise loss time are unproven"],
        "next_evidence": "Inspect time-bounded watchdog history for a detection interval.",
    }
    if include:
        base["next_evidence_assessment"] = model_proposal(kind)
    return base


def test_additive_optional_v3_declares_separate_proposal_limits_without_proving_them():
    fixture = _CASES["stale_connectivity"]
    selected = ["S1", "S2", "S3"]
    val = _validate_answer(json.dumps(draft()), [fixture["initial"]] + [
        r for s in fixture["catalog"] if s["id"] in selected for r in s["records"]])
    result = build_stage78_review(fixture, selected, val)
    assert result["model_proposal"]["declaration_present"] is True
    assert result["model_proposal"]["assessment"]["proposal_kind"] == "watchdog_history"
    assert "single tick" in result["proposal_kind_host_limit"]
    assert result["reviews_the_meaning_of_model_proposal_automatically"] is False
    assert result["publisher_approval"] is False
    assert result["additional_cloud_requests"] == 0


def test_existing_legacy_v3_without_assessment_is_allowed_but_not_credited():
    original = draft(include=False)
    records = [_CASES["stale_connectivity"]["initial"]]
    assert _validate_answer(json.dumps(original), records) == original
    r = build_stage78_review(_CASES["stale_connectivity"], ["S1"], original)
    assert r["model_proposal"]["declaration_present"] is False
    assert r["proposal_kind_host_limit"] is None
    assert r["human_review"]["could_prove_claimed_conclusion"] == "not_reviewed"


@pytest.mark.parametrize("mutation", [
    {"proposal_kind": "fabricated"},
    {"could_establish": ""},
    {"cannot_establish": "x"},
    {"additional_proof_needed": 10},
    {"extra": "unsupported"},
])
def test_bad_assessment_rejected(mutation):
    proposal = model_proposal()
    proposal.update(mutation)
    with pytest.raises(ValueError):
        validate_followup_assessment(proposal)


def test_unexpected_keys_and_legacy_version_cannot_claim_v3_assessment():
    x = draft()
    x["extra"] = 1
    with pytest.raises(ValueError):
        _validate_answer(json.dumps(x), [_CASES["stale_connectivity"]["initial"]])
    old = draft()
    old["schema"] = "homebrain-stage6-answer.v2"
    old["sentences"][0].pop("epistemic")
    with pytest.raises(ValueError):
        _validate_answer(json.dumps(old), [_CASES["stale_connectivity"]["initial"]])


def test_source_type_limitations_do_not_promote_misleading_prose_to_truth():
    fixture = _CASES["stale_connectivity"]
    bad = draft()
    bad["next_evidence"] = "A watchdog tick proves the precise moment that the device disconnected."
    bad["next_evidence_assessment"]["could_establish"] = (
        "Proves exact physical loss instantly from any heartbeat.")
    selected = ["S2", "S3", "S4"]
    packet = build_review_packet("stale_connectivity", fixture, selected, bad)
    review = packet["stage78_followup_sufficiency_review"]
    caps = review["host_source_capability_reference"]
    watchdog = next(row for row in caps if row["record_kind"] == "watchdog_tick")
    assert watchdog["examined_record_ids"] == ["E4"]
    assert "cannot establish the exact time" in watchdog["cannot_alone_establish"]
    assert review["reviews_the_meaning_of_model_proposal_automatically"] is False
    assert review["human_review"]["acknowledges_evidence_limits"] == "not_reviewed"
    assert packet["publisher_approval"] is False


def test_type_capability_is_generic_across_synthetic_scenarios():
    for case in _CASES:
        selected = ["S1", "S2", "S3"]
        result = build_stage78_review(_CASES[case], selected, draft())
        assert result["synthetic_only"] and result["publisher_approval"] is False
        assert result["no_hidden_reference_data_sent_to_model"] is True
        assert result["source_type_capability_is_not_semantic_certification"] is True
        assert result["human_review"]["additional_verification_is_appropriate"] == "not_reviewed"


@pytest.mark.parametrize("selected", [["S1", "S1"], ["S999"], ["S1"] * 4])
def test_invalid_source_selection_fails_closed(selected):
    with pytest.raises(ValueError):
        build_stage78_review(_CASES["stale_connectivity"], selected, draft())


class FakeCloud:
    base_url = "https://ollama.com"
    model_name = "gemma4:31b-cloud"
    api_key = "private-example-key"
    timeout_seconds = 60
    configured = True

    def __init__(self):
        self.calls = []

    async def _chat_post(self, messages, tools, **kwargs):
        assert tools == [] and kwargs["disable_thinking"]
        self.calls.append(messages)
        all_messages = json.dumps(messages)
        assert "private-example-key" not in all_messages
        assert "host_source_capability_reference" not in all_messages
        assert "gold_sources" not in all_messages
        prompt = json.loads(messages[1]["content"])
        if "remaining_source_titles" in prompt:
            i = len(prompt["sources_already_examined"])
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1", "action": "read",
                "source_id": ["S1", "S2", "S3"][i],
                "reason": "Investigate a distinct part of the fictional question",
            })}
        assert "next_evidence_assessment" in messages[0]["content"]
        assert "cannot_establish" in messages[0]["content"]
        return {"content": json.dumps(draft())}


def test_four_model_requests_no_extra_cloud_or_production_approval():
    cloud = FakeCloud()
    result = asyncio.run(Stage6Benchmark().run_case(
        cloud, "stale_connectivity", confirmed=True))
    assert len(cloud.calls) == result["cloud_requests_attempted"] == 4
    r = result["independent_review_packet"]["stage78_followup_sufficiency_review"]
    assert r["model_proposal"]["declaration_present"] is True
    assert r["additional_cloud_requests"] == 0
    assert result["independent_review_packet"]["publisher_approval"] is False


def test_mobile_shows_followup_limitations_and_preserves_manual_review():
    html = render_page("HomeBrainOS", "0.18.310")
    for phrase in (
        "Stage 7.8 · Can the next evidence prove the claim?",
        "Could establish", "Cannot establish alone", "Additional proof needed",
        "host_source_capability_reference", "next_evidence_quality:followupControl?",
        "production_publication_approval:false",
    ):
        assert phrase in html


def test_unchanged_production_modules_cannot_import_stage78():
    for file in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage78_followup_sufficiency" not in (APP / file).read_text()

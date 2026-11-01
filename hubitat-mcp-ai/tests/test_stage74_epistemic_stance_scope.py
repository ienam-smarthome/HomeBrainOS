"""Stage 7.4: topic versus epistemic position / source scope.

Mock inference and static fictional evidence only. A model self-declaration
is not natural-language semantic validation, even when all atoms match.
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
    _CASES, _audit, _validate_answer, Stage6Benchmark,
)
from stage74_epistemic_claims import (  # noqa: E402
    assess_epistemic_claim, validate_epistemic_declaration,
)
from stage7_review_packet import build_review_packet  # noqa: E402
from webui import render_page  # noqa: E402


def draft(kind="unique_cause", position="not_established",
          scope="examined_records", wording=None, atoms=None):
    return {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": [{
            "text": wording or (
                "The final OFF report does not establish which app caused it."
            ),
            "kind": kind,
            "evidence_ids": ["I1", "E1", "E2"],
            "atoms": atoms if atoms is not None else [],
            "epistemic": {"position": position, "scope": scope},
        }],
        "uncertainties": ["Independent actuation and cause remain unresolved"],
        "next_evidence": "Obtain independent actuator receipt tied to a specific command",
    }


def gathered():
    case = _CASES["competing_commands"]
    return [case["initial"]] + [
        r for source in case["catalog"]
        if source["id"] in ("S1", "S2", "S3") for r in source["records"]
    ]


def test_v3_scoped_unresolved_causality_is_not_positive_unique_cause_proof():
    case = _CASES["competing_commands"]
    answer = draft()
    assert _validate_answer(json.dumps(answer), gathered()) == answer
    result = _audit(case, ["S1", "S2", "S3"], answer)
    row = result["sentence_citation_checks"][0]
    assert row["epistemic_annotation"]["model_declared_position"] == "not_established"
    assert row["epistemic_annotation"]["model_declared_scope"] == "examined_records"
    assert row["epistemic_annotation"]["epistemic_category"] == "scoped_unresolved_model_declaration"
    assert row["typed_source_supported"] is False
    assert result["scoped_unresolved_model_declarations"] == 1
    assert result["high_risk_unsupported_sentences"] == 0
    assert result["high_risk_assertion_or_refutation_declarations"] == 0
    assert result["unsupported_typed_sentence_citations"] == 1
    assert result["prose_semantics_fully_verified"] is False
    assert result["publisher_approval"] is False


@pytest.mark.parametrize("position,category", [
    ("affirmed", "affirmative_high_risk_claim"),
    ("refuted", "categorical_refutation_high_risk"),
])
def test_positive_or_categorical_refutation_of_unique_cause_stays_high_risk(position, category):
    case = _CASES["competing_commands"]
    data = draft(position=position)
    assert _validate_answer(json.dumps(data), gathered()) == data
    checks = _audit(case, ["S1", "S2", "S3"], data)
    assert checks["high_risk_unsupported_sentences"] == 1
    assert checks["high_risk_assertion_or_refutation_declarations"] == 1
    assert checks["scoped_unresolved_model_declarations"] == 0
    assert checks["sentence_citation_checks"][0]["epistemic_annotation"]["epistemic_category"] == category
    assert checks["publisher_approval"] is False


def test_universal_not_established_is_unscoped_and_not_falsely_verified():
    data = draft(position="not_established", scope="universal")
    checks = _audit(_CASES["competing_commands"], ["S1", "S2", "S3"], data)
    assert checks["unscoped_unresolved_model_declarations"] == 1
    assert checks["high_risk_unsupported_sentences"] == 1
    assert checks["scoped_unresolved_model_declarations"] == 0
    assert checks["publisher_approval"] is False


def test_self_reported_safe_position_does_not_certify_overconfident_prose():
    malicious = draft(
        position="not_established", scope="examined_records",
        wording="The Inactivity App definitely physically caused the OFF state.")
    result = _audit(_CASES["competing_commands"], ["S1", "S2", "S3"], malicious)
    assert result["scoped_unresolved_model_declarations"] == 1
    assert result["epistemic_declarations_are_model_authored_not_prose_verified"]
    packet = build_review_packet(
        "competing_commands", _CASES["competing_commands"],
        ["S1", "S2", "S3"], malicious)
    entry = packet["author_sentences"][0]
    assert entry["text"].startswith("The Inactivity App definitely")
    assert entry["model_supplied_epistemic"]["position"] == "not_established"
    assert entry["epistemic_meaning_agrees_with_prose"] == "not_reviewed"
    assert packet["prose_fully_verified"] is False
    assert packet["publisher_approval"] is False
    assert "contradicts_declaration" in packet["reviewer_rubric"]["epistemic_prose_alignment"]


@pytest.mark.parametrize("bad", [
    None, [], "not_established",
    {}, {"position": "unknown", "scope": "examined_records"},
    {"position": "affirmed", "scope": "all of space"},
    {"position": "not_established", "scope": "examined_records", "fake": True},
    {"position": None, "scope": "universal"},
])
def test_malformed_epistemic_envelope_fails_closed(bad):
    with pytest.raises(ValueError, match="invalid epistemic declaration"):
        validate_epistemic_declaration(bad)
    data = draft()
    data["sentences"][0]["epistemic"] = bad
    with pytest.raises(ValueError, match="invalid epistemic declaration"):
        _validate_answer(json.dumps(data), gathered())


def test_no_self_classified_refutation_inherits_source_support():
    data = draft(kind="state_report", position="refuted", scope="examined_records")
    # The cited initial observation really IS a state report, but the
    # model's declared refutation is not thereby a proven refutation.
    checks = _audit(_CASES["competing_commands"], ["S1", "S2", "S3"], data)
    assert checks["sentence_citation_checks"][0]["typed_source_supported"] is False
    assert checks["typed_source_supported_sentences"] == 0
    assert checks["publisher_approval"] is False


def test_backward_compatibility_v2_and_v1_have_no_invented_position():
    case = _CASES["competing_commands"]
    base = draft(kind="state_report", position="affirmed")
    base["sentences"][0]["evidence_ids"] = ["I1"]
    base["sentences"][0]["atoms"] = [
        {"record_id": "I1", "field": "state", "value": "off"}
    ]
    old = json.loads(json.dumps(base))
    old["schema"] = "homebrain-stage6-answer.v2"
    del old["sentences"][0]["epistemic"]
    assert _validate_answer(json.dumps(old), gathered()) == old
    audit = _audit(case, ["S1", "S2", "S3"], old)
    assert audit["typed_source_supported_sentences"] == 1
    assert audit["sentence_citation_checks"][0]["epistemic_annotation"] is None
    assert audit["prose_semantics_fully_verified"] is False
    old["schema"] = "homebrain-stage6-answer.v1"
    del old["sentences"][0]["atoms"]
    assert _validate_answer(json.dumps(old), gathered()) == old


@pytest.mark.parametrize("kind", ["unique_cause", "physical_confirmation", "absence_proven"])
def test_bounded_unknown_does_not_become_global_absence_or_physical_proof(kind):
    row = assess_epistemic_claim(kind, {
        "position": "not_established", "scope": "examined_records"
    })
    assert not row["universal_absence_proven"]
    assert not row["unique_physical_causation_proven"]
    assert row["independent_human_semantic_review_required"]
    assert not row["publication_approval"]


class FakeOllama:
    def __init__(self):
        self.base_url = "https://ollama.com"
        self.api_key = "mock-key-private"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == [] and kwargs["disable_thinking"]
        content = json.dumps(messages)
        assert "mock-key-private" not in content
        assert "gold_sources" not in content
        assert "reference_evidence_record_ids" not in content
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            chosen = ["S1", "S2", "S3"][len(body["sources_already_examined"])]
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1",
                "action": "read", "source_id": chosen,
                "reason": "Inspect this fictional source for incident evidence",
            })}
        assert "homebrain-stage6-answer.v3" in messages[0]["content"]
        return {"content": json.dumps(draft())}


def test_live_mock_stage6_v3_4_calls_and_independent_review_not_certified():
    cloud = FakeOllama()
    result = asyncio.run(Stage6Benchmark().run_case(
        cloud, "competing_commands", confirmed=True))
    assert result["success"] is True
    assert len(cloud.calls) == 4
    assert result["relevant_source_recall"] == "3/3"
    assert result["scoped_unresolved_model_declarations"] == 1
    assert result["high_risk_assertion_or_refutation_declarations"] == 0
    assert result["independent_review_packet"]["author_sentences"][0][
        "model_supplied_epistemic"] == {
            "position": "not_established", "scope": "examined_records",
        }
    assert result["independent_review_packet"]["publisher_approval"] is False
    assert result["prose_semantics_fully_verified"] is False
    assert "mock-key-private" not in json.dumps(result)


def test_mobile_ui_requires_human_alignment_judgement_and_separate_epistemic_counts():
    html = render_page("HomeBrainOS", "0.18.306")
    for phrase in (
        "Epistemic declarations:",
        "scoped_unresolved_model_declarations",
        "unscoped_unresolved_model_declarations",
        "high_risk_assertion_or_refutation_declarations",
        "Does sentence meaning match its declared position/scope?",
        "reviewer_epistemic_alignment",
        "meaningReview.value!=='not_reviewed'",
        "stance-to-prose match NOT verified",
        "production_publication_approval:false",
    ):
        assert phrase in html


def test_production_publisher_mcp_and_agent_do_not_import_stance_pilot():
    for filename in (
        "mcp_agent_orchestrator.py", "tool_executor.py",
        "causal_claim_publication.py", "final_answer_coordinator.py",
    ):
        assert "stage74_epistemic_claims" not in (APP / filename).read_text()

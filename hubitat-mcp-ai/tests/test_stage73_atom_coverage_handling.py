"""Stage 7.3: absence of model-provided atoms is not an invented proof.

No new model calls, retries, production publisher activation, device access
or source-key leakage. Missing declarations are explicit, typed-high-risk
claims remain unsupported, excessive/malformed/invalid values remain unsafe.
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
from stage66_answer_diagnostics import answer_failure_category  # noqa: E402
from webui import render_page  # noqa: E402


def response(*sentences):
    return {
        "schema": "homebrain-stage6-answer.v2",
        "sentences": list(sentences),
        "uncertainties": ["Physical execution has not been independently verified"],
        "next_evidence": "Examine independent actuator receipt history",
    }


def sentence(kind="state_report", *, atoms=None, text=None, ids=None):
    return {
        "text": text or "The fictional device was reported in a state.",
        "kind": kind,
        "evidence_ids": ids or ["I1"],
        "atoms": [] if atoms is None else atoms,
    }


def test_empty_atoms_do_not_require_invented_source_values():
    case = _CASES["competing_commands"]
    draft = response(sentence(text="The incident's physical cause is not established by the examined records."))
    assert _validate_answer(json.dumps(draft), [case["initial"]]) == draft
    audit = _audit(case, [], draft)
    assert audit["typed_source_supported_sentences"] == 1
    assert audit["source_value_atoms_verified"] == 0
    assert audit["source_value_atoms_mismatched"] == 0
    assert audit["sentences_missing_declared_source_value_atoms"] == 1
    assert not audit["declared_source_value_coverage_complete"]
    assert audit["sentence_citation_checks"][0]["source_value_atom_coverage"] == "missing_declared_atoms_unverified"
    assert audit["sentences_with_unverified_free_prose"] == 1
    assert audit["prose_semantics_fully_verified"] is False
    assert audit["publisher_approval"] is False


def test_empty_atoms_cannot_silently_support_high_risk_physical_or_global_absence_claims():
    case = _CASES["competing_commands"]
    draft = response(sentence(
        kind="absence_proven", text="Neither recorded command ever physically executed.",
        ids=["E1", "E2"]))
    records = [case["initial"]] + [
        rec for src in case["catalog"] if src["id"] in ("S1", "S2")
        for rec in src["records"]]
    assert _validate_answer(json.dumps(draft), records) == draft
    result = _audit(case, ["S1", "S2"], draft)
    assert result["high_risk_unsupported_sentences"] == 1
    assert result["unsupported_typed_sentence_citations"] == 1
    assert result["sentences_missing_declared_source_value_atoms"] == 1
    assert result["publisher_approval"] is False



def test_relation_without_atoms_uses_structural_host_proof_not_missing_atom_penalty():
    case = _CASES["competing_commands"]
    draft = response(sentence(
        kind="competing_commands", ids=["E1", "E2"],
        text="Two different applications issued competing commands."))
    records = [case["initial"]] + [
        rec for src in case["catalog"] if src["id"] in ("S1", "S2")
        for rec in src["records"]]
    assert _validate_answer(json.dumps(draft), records) == draft
    checks = _audit(case, ["S1", "S2"], draft)
    assert checks["typed_source_supported_sentences"] == 1
    assert checks["sentences_missing_declared_source_value_atoms"] == 0
    assert checks["declared_source_value_coverage_complete"] is True
    assert checks["sentence_citation_checks"][0]["source_value_atom_coverage"] == (
        "not_applicable_relation_host_proof")
    assert checks["prose_semantics_fully_verified"] is False
    assert checks["publisher_approval"] is False


def test_partial_atom_coverage_is_not_a_complete_pass_even_if_present_atoms_match():
    case = _CASES["competing_commands"]
    draft = response(
        sentence("state_report", text="The light was reported off.",
                 atoms=[{"record_id": "I1", "field": "state", "value": "off"}]),
        sentence("state_report", text="Physical operation is still uncertain."),
    )
    audit = _audit(case, [], draft)
    assert audit["source_value_atoms_verified"] == 1
    assert audit["sentences_missing_declared_source_value_atoms"] == 1
    assert audit["declared_source_value_coverage_complete"] is False
    assert audit["declared_source_value_coverage_is_not_prose_verification"] is True
    assert audit["publisher_approval"] is False


@pytest.mark.parametrize("atom_field,atom_value", [
    ("state", "physically-on"),
    ("source_time", "23:59:59Z"),
])
def test_model_declared_false_values_remain_visible_mismatches(atom_field, atom_value):
    case = _CASES["competing_commands"]
    answer = response(sentence(
        atoms=[{"record_id": "I1", "field": atom_field, "value": atom_value}]))
    assert _validate_answer(json.dumps(answer), [case["initial"]]) == answer
    result = _audit(case, [], answer)
    assert result["source_value_atoms_mismatched"] == 1
    assert result["declared_source_value_coverage_complete"] is False


@pytest.mark.parametrize("atoms,category", [
    ([{"record_id": "I1", "field": "state", "value": "off"}] * 5, "atomic_assertion_count_exceeds_limit"),
    ({"record_id": "I1"}, "atomic_assertion_list_not_array"),
])
def test_bad_atom_arrays_still_fail_before_model_answer_accepted(atoms, category):
    case = _CASES["competing_commands"]
    draft = response(sentence(atoms=atoms))
    with pytest.raises(ValueError) as exc:
        _validate_answer(json.dumps(draft), [case["initial"]])
    assert answer_failure_category(exc.value) == category


def test_invalid_or_uncited_field_and_duplicate_are_not_accepted():
    case = _CASES["competing_commands"]
    for atoms in (
        [{"record_id": "E999", "field": "state", "value": "off"}],
        [{"record_id": "I1", "field": "api_key", "value": "never"}],
        [{"record_id": "I1", "field": "state", "value": "off"}] * 2,
    ):
        with pytest.raises(ValueError):
            _validate_answer(json.dumps(response(sentence(atoms=atoms))),
                             [case["initial"]])


class FakeModel:
    def __init__(self, *, high_risk=False):
        self.api_key = "private-dummy-secret"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []
        self.high_risk = high_risk

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert not tools and kwargs["disable_thinking"]
        serialized = json.dumps(messages)
        assert "private-dummy-secret" not in serialized
        assert "gold_sources" not in serialized
        assert "required_types" not in serialized
        payload = json.loads(messages[1]["content"])
        if "remaining_source_titles" in payload:
            n = len(payload["sources_already_examined"])
            sid = ["S1", "S2", "S3"][n]
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1",
                "action": "read", "source_id": sid,
                "reason": "Inspect an independent fictional source",
            })}
        if self.high_risk:
            answer = response(sentence(
                kind="absence_proven", ids=["E1", "E2"],
                text="Neither application command ever physically executed."))
        else:
            answer = response(sentence(
                text="The light was reported off, but its physical cause is unresolved."))
        return {"content": json.dumps(answer)}


@pytest.mark.parametrize("high_risk", [False, True])
def test_no_retry_or_publisher_pass_from_missing_atoms(high_risk):
    model = FakeModel(high_risk=high_risk)
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "competing_commands", confirmed=True))
    assert result["success"] is True
    assert len(model.calls) == 4
    assert result["requested_source_reads"] == 3
    assert result["relevant_source_recall"] == "3/3"
    assert result["sentences_missing_declared_source_value_atoms"] == 1
    assert result["declared_source_value_coverage_complete"] is False
    assert result["independent_review_packet"]["publisher_approval"] is False
    assert result["publisher_approval"] is False
    assert result["prose_semantics_fully_verified"] is False
    if high_risk:
        assert result["high_risk_unsupported_sentences"] == 1
    assert "private-dummy-secret" not in json.dumps(result)


def test_phone_ui_cannot_label_missing_atoms_as_source_verified():
    html = render_page("HomeBrainOS", "0.18.305")
    for phrase in (
        "Declared atom coverage:",
        "sentences_missing_declared_source_value_atoms",
        "No declared source-value atoms — causal/negative prose not independently verified",
        "prose still unverified",
    ):
        assert phrase in html


def test_production_publisher_tool_and_agent_unchanged():
    for filename in (
        "mcp_agent_orchestrator.py", "tool_executor.py",
        "causal_claim_publication.py", "final_answer_coordinator.py",
    ):
        content = (APP / filename).read_text()
        assert "stage73" not in content

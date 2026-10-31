"""Stage 6.3 investigation question-coverage and value-of-information tests.

No external provider inference or live-device calls. The model never sees
the host's gold source IDs or required findings. A structurally valid STOP
may still be factually premature and must be reported as such.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import (  # noqa: E402
    _CASES, _validate_plan, Stage6Benchmark, BenchmarkError,
)
from webui import render_page  # noqa: E402


def _plan(remaining, *, action="read", selected=None, useful=(), questions=None):
    return {
        "schema": "homebrain-stage6-next.v2",
        "action": action,
        "source_id": selected if action == "read" else None,
        "reason": "A fresh source can resolve an unanswered part of the question"
                  if action == "read" else
                  "All remaining sources appear unable to change my answer",
        "open_questions": ["Which source can establish the issuing application?",
                           "Can reported states prove physical operation?"]
                          if questions is None else questions,
        "source_evaluations": [
            {"source_id": x,
             "could_change_answer": x in useful,
             "why": ("Directly relevant to the unanswered investigation question"
                     if x in useful else
                     "Does not add a materially different fact to the current answer")}
            for x in remaining
        ],
    }


def test_every_unread_source_must_be_assessed_before_stopping():
    remaining = {"S1", "S2", "S3"}
    good = _plan(sorted(remaining), action="stop", useful=())
    assert _validate_plan(json.dumps(good), remaining, can_read=True) == good
    for bad in (
        {**good, "source_evaluations": good["source_evaluations"][:-1]},
        {**good, "source_evaluations": [good["source_evaluations"][0]] * 3},
        {**good, "source_evaluations": [
            {**item, "could_change_answer": "false"} for item in good["source_evaluations"]]},
        {**good, "source_evaluations": [
            {**item, "source_id": "unknown"} for item in good["source_evaluations"]]},
        {**good, "open_questions": ["short"]},
        {**good, "open_questions": ["Question repeated here?"] * 2},
        {**good, "other": "unexpected"},
    ):
        with pytest.raises(ValueError):
            _validate_plan(json.dumps(bad), remaining, can_read=True)


def test_model_cannot_stop_while_its_own_ledger_flags_useful_evidence():
    left = {"S1", "S4", "S5"}
    bad = _plan(sorted(left), action="stop", useful={"S1"})
    with pytest.raises(ValueError, match="cannot stop"):
        _validate_plan(json.dumps(bad), left, can_read=True)
    cannot_read = _plan(sorted(left), action="read", selected="S4",
                        useful={"S1"})
    with pytest.raises(ValueError, match="must be assessed as useful"):
        _validate_plan(json.dumps(cannot_read), left, can_read=True)
    valid = _plan(sorted(left), action="read", selected="S1", useful={"S1"})
    assert _validate_plan(json.dumps(valid), left, can_read=True) == valid


class Stage63Fake:
    def __init__(self, *, picked=("S2", "S3", "S1"), stop_at=None,
                 contradict=False, underrate=False):
        self.api_key = "fake-credential-not-in-prompt"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []
        self.picked = list(picked)
        self.stop_at = stop_at
        self.contradict = contradict
        self.underrate = underrate

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == []
        assert kwargs["disable_thinking"] is True
        assert kwargs["api_key"] == self.api_key
        serialized = json.dumps(messages)
        for secret in (self.api_key, "gold_sources", "required_types",
                       "192.168.1", "Bedroom 3 Mesh"):
            assert secret not in serialized
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            already = [x["source_id"] for x in body["sources_already_examined"]]
            available = [x["id"] for x in body["remaining_source_titles"]]
            if self.stop_at is not None and len(already) >= self.stop_at:
                return {"content": json.dumps(_plan(
                    available, action="stop",
                    useful={"S1"} if self.contradict else (),
                    questions=["Which command could affect the incident?"],
                ))}
            choice = self.picked[len(already)]
            assert choice in available
            return {"content": json.dumps(_plan(
                available, selected=choice,
                useful={x for x in self.picked[len(already):] if x in available},
            ))}
        assert "examined_source_records" in body
        # The provider receives remaining source TITLES, never their record
        # contents; it must not claim that an unread command occurred.
        seen = {r["id"]: r for group in body["examined_source_records"]
                for r in group["records"]}
        sentence = [{
            "text": "The initial fictional light state was reported ON by the collector.",
            "kind": "state_report", "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "on"}],
        }]
        if "E1" in seen:
            sentence.append({
                "text": "The fictional lighting application issued a brightness command.",
                "kind": "command_record", "evidence_ids": ["E1"],
                "atoms": [{"record_id": "E1", "field": "command", "value": "setLevel"}],
            })
        if "E2" in seen and "E3" in seen:
            sentence.append({
                "text": "The state reports have inverted device source and collector receipt order.",
                "kind": "time_order_conflict", "evidence_ids": ["E2", "E3"],
                "atoms": [
                    {"record_id": "E2", "field": "source_time", "value": "20:01:10Z"},
                    {"record_id": "E3", "field": "source_time", "value": "20:02:09Z"},
                ],
            })
        return {"content": json.dumps({
            "schema": "homebrain-stage6-answer.v2",
            "sentences": sentence,
            "uncertainties": ["No independently verified physical execution"],
            "next_evidence": "Seek physical actuator feedback and any other command history",
        })}


def test_stage63_complete_source_discovery_and_question_ledger_without_oracle_leaks():
    model = Stage63Fake()
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "clock_conflict", confirmed=True))
    assert len(model.calls) == 4
    assert result["relevant_source_recall"] == "3/3"
    assert result["requested_source_reads"] == 3
    assert result["stop_reason"] == "read_budget_exhausted"
    assert result["expected_finding_type_coverage"] == "3/3"
    assert result["source_value_atoms_verified"] == 4
    assert result["source_value_atoms_mismatched"] == 0
    assert result["stop_source_value_review_complete"] is True
    assert len(result["source_value_review"]) == 3
    assert all(row["source_value_coverage_complete"]
               for row in result["source_value_review"])
    assert all(row["model_assessed_sources"]
               for row in result["source_value_review"])
    assert not result["publisher_approval"]
    assert not result["prose_semantics_fully_verified"]


def test_stop_with_remaining_material_source_is_a_structure_failure_not_forced_read():
    model = Stage63Fake(stop_at=2, contradict=True)
    with pytest.raises(BenchmarkError) as error:
        asyncio.run(Stage6Benchmark().run_case(
            model, "clock_conflict", confirmed=True))
    assert error.value.status == 502
    assert len(model.calls) == 3
    for messages, _, _ in model.calls:
        assert "gold_sources" not in json.dumps(messages)
    assert model.api_key not in error.value.detail


def test_model_can_still_underrate_unread_source_and_host_marks_incomplete():
    model = Stage63Fake(stop_at=2)
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "clock_conflict", confirmed=True))
    assert len(model.calls) == 4
    assert result["stop_reason"] == "model_stopped"
    assert result["stop_source_value_review_complete"]
    assert result["stop_unresolved_questions"] == [
        "Which command could affect the incident?"
    ]
    assert result["relevant_source_recall"] == "2/3"
    assert result["stop_left_host_reference_sources_unexamined"]
    assert result["premature_stop_missing_relevant_sources"]
    assert result["expected_finding_type_coverage"] == "2/3"
    assert result["source_utility_model_supplied_not_verified"]
    assert not result["publisher_approval"]


def test_old_planning_mock_schema_is_supported_but_not_called_complete():
    class OldPlan(Stage63Fake):
        async def _chat_post(self, messages, tools, **kwargs):
            body = json.loads(messages[1]["content"])
            if "remaining_source_titles" in body:
                self.calls.append((messages, tools, kwargs))
                remaining = body["remaining_source_titles"]
                return {"content": json.dumps({
                    "schema": "homebrain-stage6-next.v1",
                    "action": "stop", "source_id": None,
                    "reason": "Unexamined material sources may remain",
                })}
            return await super()._chat_post(messages, tools, **kwargs)

    model = OldPlan()
    outcome = asyncio.run(Stage6Benchmark().run_case(
        model, "clock_conflict", confirmed=True))
    assert outcome["stop_reason"] == "model_stopped"
    assert outcome["stop_source_value_review_complete"] is False
    assert outcome["source_value_review"][0]["model_assessed_sources"] == []
    assert outcome["premature_stop_missing_relevant_sources"] is True


def test_dashboard_includes_source_by_source_review_and_uncertainty():
    html = render_page("HomeBrain", "0.18.298")
    for expected in ("Unanswered questions and per-source value assessments",
                     "stop_source_value_review_complete",
                     "source_value_review", "stop_unresolved_questions",
                     "Assessed low value:", "Potentially useful:",
                     "Legacy/incomplete source-value ledger"):
        assert expected in html


def test_no_inference_without_explicit_consent_or_publisher_change():
    model = Stage63Fake()
    for consent in (False, None, "true"):
        with pytest.raises(BenchmarkError):
            asyncio.run(Stage6Benchmark().run_case(
                model, "clock_conflict", confirmed=consent))
    assert not model.calls
    for filename in ("mcp_agent_orchestrator.py", "tool_executor.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage6_adaptive_benchmark" not in (APP / filename).read_text()

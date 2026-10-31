"""Stage 6.4: independent control-decision and optional source-ledger contracts.

Simulated provider only: no Ollama credential or real Hubitat calls. A malformed
ledger may be evaluated as incomplete, but source IDs/actions must be valid,
and an explicitly contradictory STOP still fails closed without retries.
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
    _decode_plan_control, _validate_plan, _safe_stage6_error,
    Stage6Benchmark, PlanDecisionError, BenchmarkError,
)
from webui import render_page  # noqa: E402


def _input(*, action="read", source_id="S2", open_questions=None, evaluations=None):
    return {
        "schema": "homebrain-stage6-next.v2",
        "action": action,
        "source_id": source_id,
        "reason": "Review independent source timestamps and command history",
        "open_questions": (
            ["Which event time matches the device reports?"]
            if open_questions is None else open_questions
        ),
        "source_evaluations": (
            [
                {"source_id": k, "could_change_answer": True,
                 "why": "Independent evidence may change the incident account"}
                for k in ("S1", "S2", "S3")
            ] if evaluations is None else evaluations
        ),
    }


def test_complete_v2_plan_still_uses_strict_validator_and_full_audit():
    valid = _input()
    assert _validate_plan(json.dumps(valid), {"S1", "S2", "S3"}, can_read=True) == valid
    decoded, issues = _decode_plan_control(
        json.dumps(valid), {"S1", "S2", "S3"}, can_read=True)
    assert decoded == valid
    assert issues == []


@pytest.mark.parametrize("mutation,expected", [
    ({"open_questions": ["too"]}, "open_questions_invalid_or_missing"),
    ({"source_evaluations": []}, "source_assessment_coverage_incomplete"),
    ({"source_evaluations": [
        {"source_id": "S1", "could_change_answer": True,
         "why": "This source could explain an event"},
        {"source_id": "S2", "could_change_answer": "yes",
         "why": "This source could explain an event"},
        {"source_id": "S3", "could_change_answer": False,
         "why": "This source has a different focus"},
    ]}, "source_assessment_invalid"),
])
def test_incomplete_ledger_no_longer_blocks_valid_and_scored_read(mutation, expected):
    sample = {**_input(), **mutation}
    with pytest.raises(ValueError):
        _validate_plan(json.dumps(sample), {"S1", "S2", "S3"}, can_read=True)
    control, issues = _decode_plan_control(
        json.dumps(sample), {"S1", "S2", "S3"}, can_read=True)
    assert control["schema"] == "homebrain-stage6-next.v1"
    assert control["action"] == "read"
    assert control["source_id"] == "S2"
    assert expected in issues


def test_ledger_can_mark_selected_source_low_value_but_cannot_claim_complete():
    sample = _input(evaluations=[
        {"source_id": k, "could_change_answer": k == "S1",
         "why": "Independent source relevance assessment"}
        for k in ("S1", "S2", "S3")
    ])
    control, issues = _decode_plan_control(
        json.dumps(sample), {"S1", "S2", "S3"}, can_read=True)
    assert control["source_id"] == "S2"
    assert "read_disagrees_with_own_utility_assessment" in issues


def test_early_stop_with_absent_ledger_is_not_a_successful_review():
    sample = _input(action="stop", source_id=None, evaluations=[])
    control, issues = _decode_plan_control(
        json.dumps(sample), {"S1", "S2", "S3"}, can_read=True)
    assert control["action"] == "stop"
    assert "source_assessment_coverage_incomplete" in issues


def test_self_contradictory_stop_still_fails_before_asking_next_model_round():
    sample = _input(action="stop", source_id=None)
    with pytest.raises(PlanDecisionError) as err:
        _decode_plan_control(json.dumps(sample), {"S1", "S2", "S3"}, can_read=True)
    assert err.value.category == "self_contradictory_stop"


@pytest.mark.parametrize("alter,category", [
    ({"action": "read", "source_id": "S999"}, "invalid_or_unknown_source_choice"),
    ({"action": "delete", "source_id": "S2"}, "unknown_decision_action"),
    ({"action": "stop", "source_id": "S2"}, "invalid_stop_source"),
    ({"action": "read", "source_id": None}, "invalid_or_unknown_source_choice"),
    ({"schema": "unknown"}, "incorrect_plan_schema"),
    ({"reason": ""}, "invalid_decision_reason"),
    ({"unexpected": "source E99"}, "unexpected_decision_fields"),
])
def test_unknown_actions_sources_and_extra_control_keys_are_rejected(alter, category):
    sample = {**_input(), **alter}
    with pytest.raises(PlanDecisionError) as err:
        _decode_plan_control(json.dumps(sample), {"S1", "S2", "S3"}, can_read=True)
    assert err.value.category == category


@pytest.mark.parametrize("raw,category", [
    ("A paragraph from the cloud model", "not_one_json_object"),
    ("{}", "incorrect_plan_schema"),
    ("{" + '"schema":"homebrain-stage6-next.v2"' + "}", "missing_decision_fields"),
    ("{}{}","not_one_json_object"),
])
def test_nonjson_or_missing_control_fails_with_static_safe_reason(raw, category):
    with pytest.raises(PlanDecisionError) as err:
        _decode_plan_control(raw, {"S1", "S2"}, can_read=True)
    assert err.value.category == category
    message = _safe_stage6_error(err.value, "adaptive evidence selection").detail
    assert category in message
    assert raw not in message


class FakeCloud:
    def __init__(self):
        self.api_key = "fake-secret-not-returned"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []
    @property
    def configured(self):
        return True
    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == [] and kwargs["disable_thinking"]
        assert self.api_key not in json.dumps(messages)
        data = json.loads(messages[1]["content"])
        if "remaining_source_titles" in data:
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v2",
                "action": "stop", "source_id": None,
                "reason": "Unseen command evidence remains uncertain",
                "open_questions": ["What issued the original command?"],
                # Intentionally incomplete v2 ledger
                "source_evaluations": [],
            })}
        return {"content": json.dumps({
            "schema": "homebrain-stage6-answer.v1",
            "sentences": [{
                "text": "The fictional light was reported on; this is not a physical guarantee.",
                "kind": "state_report",
                "evidence_ids": ["I1"],
            }],
            "uncertainties": ["No independent hardware confirmation"],
            "next_evidence": "Read the pending app command and bridge logs",
        })}


def test_incomplete_stop_is_scored_and_visible_without_hidden_gold_autoread():
    mock = FakeCloud()
    output = asyncio.run(Stage6Benchmark().run_case(
        mock, "clock_conflict", confirmed=True))
    assert len(mock.calls) == 2  # no retry; one plan + one final answer
    assert output["requested_source_reads"] == 0
    assert output["relevant_source_recall"] == "0/3"
    assert output["premature_stop_missing_relevant_sources"]
    assert output["stop_reason"] == "model_stopped"
    assert output["stop_source_value_review_complete"] is False
    assert output["planning_contract_complete"] is False
    assert "source_assessment_coverage_incomplete" in output["planning_contract_issues"]
    assert output["source_value_review"][0]["planning_contract_issues"]
    assert output["publisher_approval"] is False
    for messages, _, _ in mock.calls:
        assert "gold_sources" not in json.dumps(messages)
        assert "required_types" not in json.dumps(messages)
    assert "fake-secret" not in json.dumps(output)


def test_mobile_ui_warns_unaudited_plan_is_not_validated_reasoning():
    page = render_page("HomeBrainOS", "0.18.299")
    assert "planning_contract_complete" in page
    assert "planning_contract_issues" in page
    assert "do not interpret source decisions as fully reviewed" in page


def test_production_publisher_never_imports_plan_recovery():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        content = (APP / name).read_text()
        assert "stage6_adaptive_benchmark" not in content

"""Stage 6.5 question-linked information gain and source discovery pilot.

All transport calls are fake. Gold labels stay host-side and never influence
the model's actual source action. Complete structured plans remain distinct
from subjectively correct choices and fully verified final prose.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from stage65_question_value import evaluate_question_value_ledger  # noqa: E402
from stage6_adaptive_benchmark import (  # noqa: E402
    _CASES, _decode_plan_control, PlanDecisionError, Stage6Benchmark,
)
from webui import render_page  # noqa: E402


def _plan(available, *, choice="S2", action="read", gains=None, missing=False):
    gains = gains or {s: ("material" if s in ("S1", "S2", "S3") else "context")
                      for s in available}
    return {
        "schema": "homebrain-stage6-next.v3",
        "action": action,
        "source_id": choice if action == "read" else None,
        "reason": "Prioritise the source that could change a remaining conclusion",
        "questions": [
            {"id": "Q1", "text": "Which source time correctly orders the device reports?",
             "status": "unresolved"},
            {"id": "Q2", "text": "Which application issued a command near the state change?",
             "status": "unresolved"},
        ],
        "source_evaluations": [] if missing else [
            {"source_id": sid,
             "question_ids": ["Q1"] if sid in ("S2", "S3") else ["Q2"],
             "gain": gains[sid],
             "why": "This source may independently address one remaining question"}
            for sid in available
        ],
    }


def test_complete_plan_ranks_command_history_above_router_timezone_source():
    available = {"S1", "S4", "S5"}
    plan = _plan(sorted(available), choice="S1",
                 gains={"S1": "material", "S4": "none", "S5": "context"})
    approved, issues = _decode_plan_control(json.dumps(plan), available, can_read=True)
    assert approved == plan and issues == []
    checks, review = evaluate_question_value_ledger(approved, available)
    assert checks == []
    assert review["model_selected_source_rank"] == "material"
    assert review["model_ranking_consistent"] is True
    assert review["model_unresolved_questions"] == 2
    assert not review["source_utility_oracle_used_for_control"]


def test_reproduced_s5_choice_is_visible_as_model_ranking_error_without_replacement():
    available = {"S1", "S4", "S5"}
    plan = _plan(sorted(available), choice="S5",
                 gains={"S1": "material", "S4": "none", "S5": "context"})
    actual, issues = _decode_plan_control(json.dumps(plan), available, can_read=True)
    assert actual["source_id"] == "S5"  # host must never silently insert gold source S1
    assert issues == ["selected_source_below_model_rank"]
    _, review = evaluate_question_value_ledger(plan, available)
    assert review["model_ranking_consistent"] is False


def test_stop_when_any_unread_material_source_fails_closed():
    remaining = {"S1", "S2"}
    plan = _plan(sorted(remaining), action="stop", choice=None)
    with pytest.raises(PlanDecisionError, match="self_contradictory_stop"):
        _decode_plan_control(json.dumps(plan), remaining, can_read=True)
    # The self-admission matters even with a broken question ledger.
    plan["questions"] = []
    with pytest.raises(PlanDecisionError, match="self_contradictory_stop"):
        _decode_plan_control(json.dumps(plan), remaining, can_read=True)


def test_stop_with_only_context_sources_does_not_invent_gold_or_require_more_reads():
    remaining = {"S4", "S5"}
    plan = _plan(sorted(remaining), action="stop", choice=None,
                 gains={"S4": "none", "S5": "context"})
    response, issues = _decode_plan_control(json.dumps(plan), remaining, can_read=True)
    assert response["action"] == "stop" and issues == []
    _, review = evaluate_question_value_ledger(plan, remaining)
    assert review["model_ranking_consistent"] is True
    assert review["model_unresolved_questions"] == 2  # self-report, not proof of completeness


@pytest.mark.parametrize("bad,expected", [
    ({"questions": []}, "questions_missing_or_invalid"),
    ({"source_evaluations": []}, "source_review_coverage_incomplete"),
    ({"questions": [{"id": "Q1", "text": "A sufficiently long open question?",
                      "status": ["invalid"]}]}, "questions_missing_or_invalid"),
])
def test_incomplete_v3_ledger_remains_explicitly_unaudited(bad, expected):
    plan = {**_plan(["S1", "S2"]), **bad}
    response, issues = _decode_plan_control(json.dumps(plan), {"S1", "S2"},
                                            can_read=True)
    assert response["action"] == "read"
    assert expected in issues


@pytest.mark.parametrize("mutate,expected", [
    ({"source_id": "S999"}, "invalid_or_unknown_source_choice"),
    ({"action": "delete"}, "unknown_decision_action"),
    ({"schema": "not-real"}, "incorrect_plan_schema"),
    ({"source_id": None}, "invalid_or_unknown_source_choice"),
    ({"extra": "injected"}, "unexpected_decision_fields"),
])
def test_host_never_guesses_or_executes_invalid_control(mutate, expected):
    plan = {**_plan(["S1", "S2"]), **mutate}
    with pytest.raises(PlanDecisionError, match=expected):
        _decode_plan_control(json.dumps(plan), {"S1", "S2"}, can_read=True)


class ModelChoice:
    def __init__(self, *, wrong_last=False):
        self.base_url = "https://ollama.com"
        self.api_key = "fake-secret"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []
        self.wrong_last = wrong_last

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == [] and kwargs["disable_thinking"] is True
        assert "gold_sources" not in json.dumps(messages)
        assert self.api_key not in json.dumps(messages)
        payload = json.loads(messages[1]["content"])
        if "remaining_source_titles" in payload:
            selected = [x["source_id"] for x in payload["sources_already_examined"]]
            titles = [x["id"] for x in payload["remaining_source_titles"]]
            desired = ["S2", "S3", "S5" if self.wrong_last else "S1"]
            choice = desired[len(selected)]
            assert choice in titles
            gain = {s: ("material" if s in ("S1", "S2", "S3") else "context")
                    for s in titles}
            plan = _plan(titles, choice=choice, gains=gain)
            return {"content": json.dumps(plan)}
        # Explicitly source-bound final answer with limited claims.
        seen = {r["id"] for group in payload["examined_source_records"]
                for r in group["records"]}
        sentences = [
            {"text": "The fictional light was reported on at the collector.",
             "kind": "state_report", "evidence_ids": ["I1"],
             "atoms": [{"record_id": "I1", "field": "state", "value": "on"}]},
        ]
        if "E1" in seen:
            sentences.append({
                "text": "The fictional controller issued a brightness command.",
                "kind": "command_record", "evidence_ids": ["E1"],
                "atoms": [{"record_id": "E1", "field": "command", "value": "setLevel"}],
            })
        if "E2" in seen and "E3" in seen:
            sentences.append({
                "text": "Source and receipt report times have opposing order.",
                "kind": "time_order_conflict", "evidence_ids": ["E2", "E3"],
                "atoms": [
                    {"record_id": "E2", "field": "source_time", "value": "20:01:10Z"},
                    {"record_id": "E3", "field": "source_time", "value": "20:02:09Z"},
                ],
            })
        return {"content": json.dumps({
            "schema": "homebrain-stage6-answer.v2",
            "sentences": sentences,
            "uncertainties": ["Physical light actuation remains unverified"],
            "next_evidence": "Seek independent confirmation of light physical state",
        })}


@pytest.mark.parametrize("wrong,expected_recall,expected_rank_defects", [
    (False, "3/3", 0),
    (True, "2/3", 1),
])
def test_full_stage6_v3_keeps_gold_hidden_and_exposes_model_utility_error(
    wrong, expected_recall, expected_rank_defects
):
    transport = ModelChoice(wrong_last=wrong)
    result = asyncio.run(Stage6Benchmark().run_case(
        transport, "clock_conflict", confirmed=True))
    assert result["cloud_requests_attempted"] == len(transport.calls) == 4
    assert result["requested_source_reads"] == 3
    assert result["model_question_value_audit"] is (not wrong)
    assert result["model_ranking_consistency_failures"] == expected_rank_defects
    assert result["relevant_source_recall"] == expected_recall
    assert result["source_ranking_is_model_authored_not_oracle_proven"]
    assert result["prose_semantics_fully_verified"] is False
    assert result["publisher_approval"] is False
    if wrong:
        assert "selected_source_below_model_rank" in result["planning_contract_issues"]
        assert result["missing_expected_finding_types"] == ["command_record"]
    else:
        assert result["planning_contract_complete"]
        assert result["expected_finding_type_coverage"] == "3/3"
    for messages, _, _ in transport.calls:
        assert "gold_sources" not in json.dumps(messages)
        assert "required_types" not in json.dumps(messages)


def test_mobile_dashboard_explains_model_rankings_not_truth_oracle():
    html = render_page("HomeBrainOS", "0.18.300")
    for phrase in ("Question/value audit", "information_gain",
                   "model_ranking_consistency_failures",
                   "source choice", "model-authored question-linked",
                   "Ranking accuracy is assessed separately"):
        assert phrase in html


def test_production_agent_and_publisher_unaffected():
    for filename in ("mcp_agent_orchestrator.py", "tool_executor.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage65_question_value" not in (APP / filename).read_text()

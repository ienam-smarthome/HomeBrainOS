"""v0.18.77: evidence-backed, Claude-style question-first synthesis quality.

The goal is improved reasoning/answers across domains, NOT another
app-specific Rule Machine extractor or an unrestricted model grader.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from analytical_answer_quality import (
    QUESTION_FIRST_CONTRACT, answer_quality_issues,
    quality_repair_instruction,
)
from final_answer_coordinator import FinalAnswerCoordinator


RECEIPTS = [
    {"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
     "success": True, "mutates": False, "evidence_kind": "app_config",
     "arguments": {"tool": "hub_get_app_config",
                   "args": {"appId": "4246"}},
     "summary": "id-verified configuration"},
    {"tool": "hub_read_rules", "sub_tool": "hub_get_rule_health",
     "success": True, "mutates": False, "evidence_kind": "native_rule_evidence",
     "arguments": {"tool": "hub_get_rule_health",
                   "args": {"appId": "4019"}},
     "summary": "native stopped=false"},
]


def test_general_contract_is_question_first_and_causally_bounded():
    c = QUESTION_FIRST_CONTRACT.casefold()
    assert "original" not in c or "question" in c
    assert "strongest" in c and "supported" in c
    assert "compares multiple systems" in c
    assert "configured capability" in c
    assert "actual event" in c
    assert "no tools" in c
    assert "hidden" in c


@pytest.mark.parametrize("question,draft,wanted", [
    ("Compare app 4246 with app 4019.",
     "App 4246 has a delay setting. App 4019 has an inactive OFF setting. "
     "Execution is unverified.", "missing_requested_comparison"),
    ("Could controller A switch the lamp OFF before the delayed automation?",
     "Controller A was queried. The reader returned configured settings. "
     "There were no runtime logs to corroborate execution.",
     "missing_possibility_assessment"),
    ("Explain why the kitchen lamp was switched on.",
     "The light was on at the most recent timestamp. "
     "The active mode is Evening. Events were queried for an hour.",
     "missing_explanation"),
    ("Investigate the system and summarize its behaviour.",
     "No verified information is currently available.", "uninformative_no_evidence_reply"),
])
def test_quality_gate_identifies_missing_objectives(question, draft, wanted):
    assert wanted in answer_quality_issues(question, draft, RECEIPTS)


def test_explicit_uncertainty_is_acceptable_when_missing_data():
    q = "Could controller 4019 switch light 7805 off before app 4246?"
    reply = (
        "The source does not establish whether controller 4019 can target "
        "the same light before the ten-minute delay. It may interfere, "
        "but no overlap has been observed, and that remains unverified."
    )
    assert answer_quality_issues(q, reply, RECEIPTS) == ()


def test_simple_answer_and_no_evidence_are_not_forced_into_more_model_calls():
    assert answer_quality_issues(
        "What is the current mode?", "The current mode is Evening.",
        RECEIPTS,
    ) == ()
    assert answer_quality_issues(
        "Could app 4019 act earlier?", "Read-only query failed.",
        [],
    ) == ()


@pytest.mark.asyncio
async def test_quality_repair_preserves_a_useful_cross_controller_analysis():
    responses = [
        "Rule 4246 has a ten-minute delay setting and 4019 has an inactive OFF "
        "configuration. Runtime execution was not verified.",
        "App 4246 has a ten-minute configured delay, whereas 4019 is configured "
        "for an inactive OFF path. This could create competing OFF behaviour "
        "if both manage the same lamp, but their actual runtime overlap was "
        "not verified. Check scoped commands and scheduling to establish it.",
    ]
    calls = []

    async def chat(messages, tools):
        assert tools == []
        calls.append(messages)
        return {"content": responses.pop(0)}

    coordinator = FinalAnswerCoordinator(chat, evidence_supplier=lambda: RECEIPTS)
    q = ("Compare existing Rule Machine app 4246 and controller app 4019: "
         "could one switch the same light off first?")
    response = await coordinator.answer([{"role": "user", "content": q}])
    assert "whereas" in response
    assert "could" in response
    assert "not verified" in response
    assert len(calls) == 2
    assert any("QUESTION-FIRST ANALYST CONTRACT" in x.get("content", "")
               for x in calls[0])
    assert "HOST ANSWER-QUALITY REVISION" in calls[1][-1]["content"]
    assert calls[1][-1]["role"] == "user"
    assert calls[1][-2]["role"] == "assistant"
    assert all(not m.get("tool_calls") for m in calls[1])


@pytest.mark.asyncio
async def test_good_substantive_answer_does_not_use_extra_provider_round():
    calls = []

    async def chat(messages, tools):
        calls.append((messages, tools))
        return {"content": (
            "The primary controller may turn off the light before the ten-minute "
            "delay, whereas the other controller's stored duration is unverified. "
            "The data does not establish actual overlap."
        )}
    q = "Compare controllers. Could one switch the device off sooner?"
    co = FinalAnswerCoordinator(chat, evidence_supplier=lambda: RECEIPTS)
    result = await co.answer([{"role": "user", "content": q}])
    assert "whereas" in result
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_unresolved_repair_does_not_replace_previously_verified_draft():
    responses = [
        "Controller A has a setting. Controller B has an OFF setting. "
        "Their effective timing remains unverified.",
        "Controller A has a setting. Controller B has an OFF setting. "
        "Their effective timing remains unverified.",
    ]
    calls = []

    async def chat(messages, tools):
        calls.append(messages)
        return {"content": responses.pop(0)}
    co = FinalAnswerCoordinator(chat, evidence_supplier=lambda: RECEIPTS)
    answer = await co.answer([{"role": "user",
                              "content": "Compare these two installed controllers."}])
    assert "timing remains unverified" in answer
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_quality_repair_uses_existing_factual_validator_and_falls_back(monkeypatch):
    import final_answer_coordinator as mod

    responses = [
        "Controller A is configured. Controller B is configured. Both "
        "settings were returned, but timing remains unverified.",
        "Controller A definitely causes the light to switch off before B; "
        "that causal claim is certain and proven.",
    ]
    calls = []

    async def chat(messages, tools):
        calls.append(messages)
        assert tools == []
        return {"content": responses.pop(0)}

    def validation(text, evidence, *, original_user="", causal=False):
        if "definitely causes" in text:
            return "Unsupported causal attribution.", ["configuration_only_causal_attribution"]
        return text, []

    monkeypatch.setattr(mod, "validate_synthesis", validation)
    co = FinalAnswerCoordinator(chat, evidence_supplier=lambda: RECEIPTS)
    answer = await co.answer([{"role": "user",
                              "content": "Compare existing Rule Machine app 4246 and controller app 4019; verify persisted actions and settings."}])
    assert "timing remains unverified" in answer
    assert "definitely causes" not in answer
    assert len(calls) == 2


def test_repair_instruction_is_fixed_bounded_and_never_echoes_arbitrary_data():
    instruction = quality_repair_instruction((
        "missing_requested_comparison", "password=PRIVATE_SECRET",
    ))
    assert "missing_requested_comparison" in instruction
    assert "PRIVATE_SECRET" not in instruction
    assert "NO TOOLS" in instruction
    assert "No tool calls" in instruction

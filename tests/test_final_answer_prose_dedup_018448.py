"""General final-answer prose hygiene with no model, hub, or device writes."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from api_response_builder import (
    build_agent_response,
    deduplicate_repeated_answer_prose,
)


REPORTER = (
    "For this observed state transition, a bridge reported OFF while "
    "a subscribed application appeared only as an event listener."
)
BOUNDARY = (
    "This evidence does not establish who instructed the bridge to "
    "switch the target device off at the reported timestamp."
)


def test_repeated_long_prose_sentences_are_removed_without_losing_distinct_evidence():
    source = (
        "**Causal Explanation**\n"
        + REPORTER + " " + BOUNDARY + "\n\n"
        + REPORTER + " The sensor confirmed the state 641ms later.\n\n"
        + REPORTER + " " + BOUNDARY + "\n\n"
        + "**Timeline**\n"
        + "| State | Time |\n|---|---|\n| OFF | 20:53:25 |\n"
    )
    result, count = deduplicate_repeated_answer_prose(source)
    assert count == 3
    assert result.count(REPORTER) == 1
    assert result.count(BOUNDARY) == 1
    assert "The sensor confirmed the state 641ms later." in result
    assert "| OFF | 20:53:25 |" in result
    assert "**Causal Explanation**" in result
    assert "**Timeline**" in result


def test_different_times_sources_and_negations_are_kept():
    base = (
        "The controller reported the observation at "
        "2026-11-06 20:53:25 GMT; its origin is unknown."
    )
    changed_time = base.replace("20:53:25", "20:53:26")
    changed_source = base.replace("controller", "secondary bridge")
    changed_negation = base.replace("is unknown", "is not unknown")
    result, count = deduplicate_repeated_answer_prose(
        "\n".join((base, changed_time, changed_source, changed_negation))
    )
    assert count == 0
    assert result.count("2026-11-06 20:53:25 GMT") == 3
    assert changed_time in result
    assert changed_source in result
    assert changed_negation in result


def test_structured_list_table_and_fenced_code_are_never_deduplicated():
    prose = "The evaluation records distinct source roles without identifying an initiating controller."
    fence = chr(96) * 3
    source = (
        "## Coverage\n"
        + f"- {prose}\n- {prose}\n"
        + "| Status | Claim |\n| --- | --- |\n"
        + f"| First | {prose} |\n| Second | {prose} |\n\n"
        + fence + "text\n" + prose + "\n" + prose + "\n" + fence + "\n"
    )
    result, count = deduplicate_repeated_answer_prose(source)
    assert count == 0
    assert result == source


def test_new_section_may_repeat_a_fact_in_a_new_context():
    sentence = (
        "Two independent sensors recorded a transition but neither report "
        "establishes the initiating automation for this action."
    )
    source = "## Summary\n" + sentence + "\n\n## Evidence\n" + sentence
    result, count = deduplicate_repeated_answer_prose(source)
    assert count == 0
    assert result == source


def test_short_status_and_no_repetition_remain_intact():
    for source in (
        "Success.\nSuccess.\n", "No evidence found.", "",
        "The light is off. Another sample is needed.",
    ):
        result, count = deduplicate_repeated_answer_prose(source)
        assert result == source
        assert count == 0


def test_api_serialization_applies_dedup_after_other_claim_guards():
    draft = (
        "**Findings**\n"
        + REPORTER + " " + BOUNDARY + "\n\n"
        + REPORTER + " " + BOUNDARY + "\n\n"
        + "**Timeline**\n"
        + "| State | Time |\n| --- | --- |\n| OFF | 20:53:25 |\n"
    )
    outcome = SimpleNamespace(
        message=draft, request_class="live-read", evidence=[],
        choices=[], confirmation_required=False, confirmation_count=0,
        metrics={"outcome": "unresolved", "counters": {"model_rounds": 2}},
    )
    result = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=20, version="0.18.448",
    )
    assert result["message"].count(REPORTER) == 1
    assert result["message"].count(BOUNDARY) == 1
    assert "| OFF | 20:53:25 |" in result["message"]
    assert result["evidence_validation"]["repeated_long_prose_removed"] == 2
    assert outcome.message == draft
    assert result["outcome_presentation"]["value"] == "unresolved"


def test_api_serialization_does_not_invent_new_actor_or_discard_short_answer():
    outcome = SimpleNamespace(
        message="Cause unverified. OFF reported at 20:53:25 GMT.",
        request_class="live-read", evidence=[], choices=[],
        metrics={"outcome": "unresolved"},
    )
    result = build_agent_response(outcome, model="model", elapsed_ms=1, version="test")
    assert result["message"] == outcome.message
    assert "repeated_long_prose_removed" not in result["evidence_validation"]

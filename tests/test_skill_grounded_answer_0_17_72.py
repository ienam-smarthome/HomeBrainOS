"""Live v0.17.71 regression: no unsupported external-origin verdict may escape.

Tests exercise actual FinalAnswerCoordinator boundary, not only the text guard.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from causal_fail_closed_summary import render_failed_causal_synthesis
from final_answer_coordinator import FinalAnswerCoordinator
from skill_grounded_answer import render_grounded_causal_answer
from test_homebrain_skills_framework_0_17_69 import QUESTION, _case


def test_source_grounded_causal_answer_contains_all_focal_evidence():
    text = render_grounded_causal_answer(_case(), QUESTION)
    assert text is not None
    assert "SenseCap D1 Settings" in text
    assert "13.358" in text
    assert "19:54:57.946" in text
    assert "19:55:00.049" in text
    assert "not a confirmed cause" in text
    assert "Reporter: Matter Hue Bridge Pro" in text
    assert "does not disprove its prior command" not in text  # no listeners in sparse fixture
    assert "initiated outside of Hubitat" not in text
    assert "not which upstream app" in text


def test_actual_coordinator_must_not_consult_model_for_grounded_case():
    async def bad_model(messages, functions):
        raise AssertionError("model should not invent an external cause")
    coordinator = FinalAnswerCoordinator(bad_model, lambda: _case())
    response = asyncio.run(
        coordinator.answer([{"role": "user", "content": QUESTION}])
    )
    assert response.startswith("### Investigation")
    assert "SenseCap D1 Settings" in response
    assert "19:54:57.946" in response
    assert "initiated outside of Hubitat" not in response


def test_grounded_selection_needs_verified_prior_command():
    records = _case()
    no_command = [r for r in records if r.get("tool") != "hub_read_devices"]
    assert render_grounded_causal_answer(no_command, QUESTION) is None
    off_question = "Why did Livingroom Light 1 turn OFF at 22:45 on 14 October 2026? Read-only."
    assert render_grounded_causal_answer(records, off_question) is None


def test_grounded_answer_is_reusable_not_hue_hardcoded():
    evidence = _case()
    events = evidence[0]["details"]["correlationEvents"]
    for event in events:
        event["producedBy"]["label"] = "Generic Matter Bridge"
    text = render_grounded_causal_answer(evidence, QUESTION)
    assert text is not None
    assert "Generic Matter Bridge" in text
    assert "Matter Hue Bridge Pro" not in text


def test_previous_fail_closed_path_still_available_for_model_failures():
    answer = render_failed_causal_synthesis(_case(), QUESTION)
    assert "SenseCap D1 Settings" in answer
    assert "19:54:57.946" in answer

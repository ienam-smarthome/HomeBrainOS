from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import (  # noqa: E402
    controller_transition_alignments,
    subject_has_observed_intervals,
)
from causal_timeline import render_causal_timeline  # noqa: E402
from final_answer_coordinator import (  # noqa: E402
    FinalAnswerCoordinator,
    _current_turn_messages,
)
from request_metrics import RequestMetrics  # noqa: E402


def _empty_subject_receipt() -> dict:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "summary": (
            "temporal history: intervals=0, total=0s (0s), "
            "coverage=partial, reliability=unverified-event-stream"
        ),
        "details": {
            "label": "Bedroom 3 Light",
            "room": "Bedroom 3",
            "attribute": "switch",
            "timeWindow": {
                "kind": "last_night",
                "label": "last night",
                "start": "2026-09-17T18:00:00+01:00",
                "end": "2026-09-18T08:00:00+01:00",
            },
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "intervalCount": 0,
                "totalActiveDuration": "0s",
                "totalActiveSeconds": 0,
                "coverage": "partial",
                "durationReliability": "unverified-event-stream",
                "sourceIntegrityVerified": False,
                "observedIntervals": [],
            },
            "observedEvents": [
                {
                    "name": "switch",
                    "value": "on",
                    "description": "Bedroom 3 Light switch is on",
                    "date": "2026-09-18T23:16:07.001+01:00",
                }
            ],
        },
    }


def _old_controller_receipt() -> dict:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "details": {
            "label": "Bedroom 3 dimmer - 1",
            "attribute": "pushed",
            "observedEvents": [
                {
                    "name": "pushed",
                    "value": "1",
                    "description": (
                        "Bedroom 3 dimmer - 1 button 1 was pushed [physical]"
                    ),
                    "date": "2026-09-18T01:32:51.876+01:00",
                },
                {
                    "name": "pushed",
                    "value": "1",
                    "description": (
                        "Bedroom 3 dimmer - 1 button 1 was pushed [physical]"
                    ),
                    "date": "2026-09-18T00:02:53.840+01:00",
                },
            ],
        },
    }


def test_subject_without_observed_intervals_cannot_seed_causal_alignment() -> None:
    subject = {
        "label": "Bedroom 3 Light",
        "temporalAnalysis": {"observedIntervals": []},
    }
    controller = {
        "events": [
            {
                "name": "pushed",
                "value": "1",
                "date": "2026-09-18T00:02:53.840+01:00",
            }
        ]
    }

    assert subject_has_observed_intervals(subject) is False
    assert controller_transition_alignments(subject, controller) == []


def test_subject_interval_sufficiency_requires_a_bounded_start_and_end() -> None:
    assert subject_has_observed_intervals({
        "temporalAnalysis": {
            "observedIntervals": [
                {
                    "start": "2026-09-18T00:02:53.713+01:00",
                    "end": "2026-09-18T01:30:07.971+01:00",
                }
            ]
        }
    }) is True

    assert subject_has_observed_intervals({
        "temporalAnalysis": {
            "observedIntervals": [{"start": "2026-09-18T00:02:53+01:00"}]
        }
    }) is False


def test_current_turn_fence_removes_prior_user_and_assistant_conclusions() -> None:
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Why was the light on last night?"},
        {
            "role": "assistant",
            "content": (
                "Old conclusion: button 1 caused both overnight intervals."
            ),
        },
        {"role": "user", "content": "Why was Bedroom 3 Light on during the night?"},
        {
            "role": "tool",
            "tool_name": "homebrain_device_history",
            "content": '{"temporalAnalysis":{"observedIntervals":[]}}',
        },
        {
            "role": "user",
            "content": "HOST CAUSAL SUBJECT EVIDENCE STOP\nFinalize current evidence.",
        },
    ]

    current = _current_turn_messages(messages)
    joined = "\n".join(str(item.get("content") or "") for item in current)

    assert current[0]["role"] == "system"
    assert "Why was Bedroom 3 Light on during the night?" in joined
    assert "HOST CAUSAL SUBJECT EVIDENCE STOP" in joined
    assert "Old conclusion" not in joined
    assert "Why was the light on last night?" not in joined


def test_empty_subject_timeline_stays_empty_even_with_old_controller_events() -> None:
    evidence = [_empty_subject_receipt(), _old_controller_receipt()]

    assert render_causal_timeline(evidence) is None


def test_final_causal_synthesis_cannot_see_prior_assistant_answer() -> None:
    calls: list[list[dict]] = []

    async def chat(messages, tools):
        assert tools == []
        calls.append(messages)
        joined = "\n".join(str(item.get("content") or "") for item in messages)
        assert "Old conclusion: physical button 1 caused both intervals" not in joined
        assert "intervals=0" in joined or "0 intervals" in joined
        return {
            "content": (
                "No bounded on interval was established for Bedroom 3 Light "
                "during last night from the current recorded rows. The event "
                "stream is unverified, so that does not prove it stayed off."
            )
        }

    evidence = [_empty_subject_receipt(), _old_controller_receipt()]
    coordinator = FinalAnswerCoordinator(
        chat,
        evidence_supplier=lambda: evidence,
    )
    answer = asyncio.run(coordinator.answer([
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Why was the light on last night?"},
        {
            "role": "assistant",
            "content": "Old conclusion: physical button 1 caused both intervals",
        },
        {"role": "user", "content": "Why was Bedroom 3 Light on during the night?"},
        {
            "role": "tool",
            "tool_name": "homebrain_device_history",
            "content": '{"temporalAnalysis":{"observedIntervals":[]}}',
        },
        {
            "role": "user",
            "content": (
                "HOST CAUSAL SUBJECT EVIDENCE STOP\n"
                "Use CURRENT-TURN evidence only."
            ),
        },
    ]))

    assert len(calls) == 1
    assert "No bounded on interval was established" in answer
    assert "button 1 caused" not in answer


def test_empty_subject_stop_metric_is_supported() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_subject_empty_stop")
        assert metrics.snapshot()["counters"]["causal_subject_empty_stop"] == 1
    finally:
        metrics.reset(token)

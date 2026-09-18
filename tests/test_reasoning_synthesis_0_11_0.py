from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from homebrain_agent import UnifiedMCPAgent as ProductionAgent  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent as BaseAgent  # noqa: E402
from history_temporal_analysis import (  # noqa: E402
    guard_history_duration_claim,
    history_temporal_evidence_details,
)
from reasoning_policy import (  # noqa: E402
    reasoning_budget_status,
    reset_reasoning_budget,
    set_reasoning_profile,
)
from synthesis_context import build_tool_evidence_packet  # noqa: E402


def _subject_receipt() -> dict:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "summary": "temporal history",
        "details": {
            "label": "Bedroom 3 Light",
            "attribute": "switch",
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "totalActiveDuration": "1h 44m",
                "totalActiveSeconds": 6237,
                "intervalCount": 5,
                "longestActiveDuration": "1h 27m",
                "durationReliability": "unverified-event-stream",
                "sourceIntegrityVerified": False,
                "windowLabel": "last night",
                "observedIntervals": [
                    {
                        "start": "2026-09-18T00:02:53+01:00",
                        "end": "2026-09-18T01:30:07+01:00",
                        "duration": "1h 27m",
                    }
                ],
            },
        },
    }


def test_event_style_history_keeps_bounded_rows_for_synthesis() -> None:
    details = history_temporal_evidence_details({
        "label": "Bedroom 3 dimmer - 1",
        "attribute": "pushed",
        "hoursBack": 27,
        "count": 2,
        "sourceEventCount": 7,
        "analysisEventCount": 2,
        "historySourceIntegrity": "unverified",
        "historySourceIntegrityVerified": False,
        "events": [
            {
                "name": "pushed",
                "value": "1",
                "description": "button 1 pushed [physical]",
                "date": "2026-09-18T01:32:51.800+01:00",
                "isStateChange": True,
            },
            {
                "name": "pushed",
                "value": "1",
                "description": "button 1 pushed [physical]",
                "date": "2026-09-18T00:02:53.800+01:00",
                "isStateChange": True,
            },
        ],
    })

    assert details is not None
    assert details["attribute"] == "pushed"
    assert len(details["observedEvents"]) == 2
    assert details["observedEvents"][0]["description"].endswith("[physical]")


def test_evidence_brief_preserves_controller_events_beside_subject_timeline() -> None:
    controller = {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "summary": "event history",
        "details": {
            "label": "Bedroom 3 dimmer - 1",
            "attribute": "pushed",
            "observedEvents": [
                {
                    "name": "pushed",
                    "value": "1",
                    "description": "button 1 pushed [physical]",
                    "date": "2026-09-18T00:02:53.800+01:00",
                }
            ],
        },
    }

    brief = build_current_turn_evidence_ledger([_subject_receipt(), controller])

    assert brief is not None
    assert "CURRENT-TURN EVIDENCE BRIEF" in brief
    assert "Bedroom 3 Light (switch)" in brief
    assert "Bedroom 3 dimmer - 1 (pushed)" in brief
    assert "00:02:53.800" in brief
    assert "[physical]" in brief


def test_duration_guard_never_erases_other_supported_analysis() -> None:
    message = (
        "The light was on for exactly 1h 44m last night.\n"
        "A button-1 event on the Bedroom 3 dimmer occurred at the same recorded "
        "time as the 00:02:53 light-on transition.\n"
        "That timing supports a controller-trigger hypothesis but does not identify "
        "who operated it."
    )

    corrected, changed = guard_history_duration_claim(message, [_subject_receipt()])

    assert changed is True
    assert "Pairing the recorded state rows gives an on-time estimate" in corrected
    assert "button-1 event" in corrected
    assert "controller-trigger hypothesis" in corrected


def test_investigative_budget_is_larger_without_changing_standard_budget() -> None:
    reset_reasoning_budget()
    set_reasoning_profile("standard")
    standard = reasoning_budget_status()
    assert standard["maxToolRounds"] == 3
    assert standard["maxReadCalls"] == 8

    set_reasoning_profile("investigative")
    investigative = reasoning_budget_status()
    assert investigative["profile"] == "investigative"
    assert investigative["maxToolRounds"] == 5
    assert investigative["maxReadCalls"] == 12


def test_tool_packet_keeps_recent_concrete_results_and_skips_discovery() -> None:
    packet = build_tool_evidence_packet([
        {
            "role": "tool",
            "tool_name": "hub_search_tools",
            "content": '{"result":"discovery noise"}',
        },
        {
            "role": "tool",
            "tool_name": "homebrain_device_history",
            "content": (
                '{"result":{"label":"Bedroom 3 dimmer - 1","attribute":"pushed",'
                '"events":[{"date":"2026-09-18T00:02:53+01:00","value":"1"}]}}'
            ),
        },
        {
            "role": "tool",
            "tool_name": "hub_read_diagnostics",
            "content": '{"result":{"logs":[{"message":"Lighting: Auto OFF"}]}}',
        },
    ])

    assert packet is not None
    assert "discovery noise" not in packet
    assert "Bedroom 3 dimmer - 1" in packet
    assert "Lighting: Auto OFF" in packet



def test_production_agent_inherits_the_shared_final_answer_path() -> None:
    assert ProductionAgent._final_answer is BaseAgent._final_answer


async def _coordinator_messages() -> tuple[str, list[list[dict]]]:
    calls: list[list[dict]] = []

    async def chat(messages, tools):
        assert tools == []
        calls.append(messages)
        return {
            "content": (
                "The strongest evidence points to the Bedroom 3 dimmer as a "
                "controller trigger. The recorded duration is an estimate."
            )
        }

    evidence = [
        _subject_receipt(),
        {
            "tool": "homebrain_device_history",
            "success": True,
            "evidence_kind": "deterministic_device_event_history",
            "summary": "event history",
            "details": {
                "label": "Bedroom 3 dimmer - 1",
                "attribute": "pushed",
                "observedEvents": [{
                    "name": "pushed",
                    "value": "1",
                    "description": "button 1 pushed [physical]",
                    "date": "2026-09-18T00:02:53.800+01:00",
                }],
            },
        },
    ]
    coordinator = FinalAnswerCoordinator(chat, evidence_supplier=lambda: evidence)
    answer = await coordinator.answer([
        {"role": "user", "content": "Why was Bedroom 3 Light on during the night?"},
        {
            "role": "tool",
            "tool_name": "homebrain_device_history",
            "content": (
                '{"result":{"label":"Bedroom 3 dimmer - 1","attribute":"pushed",'
                '"events":[{"date":"2026-09-18T00:02:53.800+01:00",'
                '"description":"button 1 pushed [physical]"}]}}'
            ),
        },
    ])
    return answer, calls


def test_shared_final_coordinator_uses_causal_brief_and_tool_packet() -> None:
    import asyncio

    answer, calls = asyncio.run(_coordinator_messages())

    assert "strongest evidence" in answer
    assert len(calls) == 1
    final_messages = calls[0]
    joined = "\n".join(str(item.get("content") or "") for item in final_messages)
    assert "HOST CURRENT-TURN EVIDENCE BRIEF" in joined
    assert "HOST CURRENT-TURN TOOL EVIDENCE EXCERPTS" in joined
    assert "This is a causal investigation" in joined
    assert "button 1 pushed [physical]" in joined

from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402

"""Reasoning-first regression coverage for historical/diagnostic READs.

The default path should let the model synthesize authoritative tool results
rather than ending the request at a canned presenter.  0.10.447 extends that
principle to successful device-history reads: deterministic code performs the
timestamp arithmetic, while the model gets a second round to answer the user's
actual question from those grounded derived facts.
"""


class ReasoningModeMCP:
    """Fake MCP exposing one switch device with event history, plus the
    hub's own location-scoped event stream -- both reachable via the
    hub_list_devices / hub_list_device_events operation-dispatch shape the
    real gateway uses. No list_tools() entries are needed for the local
    (homebrain_*) tools under test -- those are always declared regardless
    of what the remote MCP server itself advertises.
    """

    def __init__(
        self,
        *,
        switch_events: list[dict[str, object]] | None = None,
        location_events: list[dict[str, object]] | None = None,
    ) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.switch_events = switch_events if switch_events is not None else [
            {
                "name": "switch",
                "value": "off",
                "date": "2026-08-11T07:09:07.070+0100",
                "isStateChange": True,
            },
            {
                "name": "switch",
                "value": "on",
                "date": "2026-08-11T07:08:32.619+0100",
                "isStateChange": True,
            },
        ]
        self.location_events = location_events if location_events is not None else [
            {
                "name": "mode",
                "value": "Away",
                "date": "2026-08-10T09:00:00.000+0100",
                "isStateChange": True,
            },
        ]

    async def list_tools(self) -> list:
        return []

    async def get_cached_devices(self) -> list[dict[str, object]]:
        return [{
            "id": "7029",
            "label": "Shower Light",
            "room": "Bathroom",
            "capabilities": ["Switch"],
        }]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> MCPToolResult:
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if operation == "hub_list_devices":
            return MCPToolResult(
                name, arguments, {}, "ok",
                {"devices": [{
                    "id": "7029",
                    "label": "Shower Light",
                    "room": "Bathroom",
                    "capabilities": ["Switch"],
                }]},
            )
        if operation == "hub_list_device_events":
            args = arguments.get("args") or {}
            if isinstance(args, dict) and (args.get("deviceId") or args.get("appId")):
                return MCPToolResult(
                    name, arguments, {}, "ok",
                    {"source": "device", "events": self.switch_events},
                )
            return MCPToolResult(
                name, arguments, {}, "ok",
                {"source": "location", "events": self.location_events},
            )
        raise AssertionError(f"unexpected operation: {operation}")


def _device_history_call(name: str = "shower light") -> dict:
    return {
        "function": {
            "name": "homebrain_device_history",
            "arguments": {"name": name, "attribute": "switch", "hours_back": 12},
        }
    }


def _location_events_call() -> dict:
    return {
        "function": {
            "name": "homebrain_location_events",
            "arguments": {"hours_back": 24},
        }
    }


@pytest.mark.asyncio
async def test_default_construction_reasons_through_hub_health_instead_of_a_template() -> None:
    """Regression test: default reasoning mode must actually invoke the model."""

    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_location_events_call()]}},
        {"message": {"role": "assistant", "content": "The hub looks healthy."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "check the hub health status", session_id="reasoning-mode-hub-health"
    )

    assert len(ai.requests) >= 1
    assert "healthy" in outcome.message.casefold()


@pytest.mark.asyncio
async def test_location_events_question_is_now_reachable_via_a_declared_tool() -> None:
    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_location_events_call()]}},
        {"message": {"role": "assistant", "content": "We last entered Away mode yesterday at 9am."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "when did we last enter Away mode?", session_id="reasoning-mode-location-events"
    )

    location_calls = [
        arguments for name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_device_events"
        and not (isinstance(arguments.get("args"), dict) and arguments["args"].get("deviceId"))
    ]
    assert location_calls, "the model must have been able to fetch location events at all"
    assert "away" in outcome.message.casefold()


@pytest.mark.asyncio
async def test_causal_why_question_is_not_cut_off_by_the_device_history_template() -> None:
    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_device_history_call()]}},
        {
            "message": {
                "role": "assistant",
                "content": (
                    "Shower Light turned off at 7:09 am, 35 seconds after "
                    "turning on at 7:08 am -- consistent with a motion-timeout "
                    "automation rather than a fault."
                ),
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": (
                    "The recorded interval ran from 7:08 am to 7:09 am. Its short "
                    "duration is consistent with a motion-timeout automation, but "
                    "the event history alone does not prove which automation caused it."
                ),
            }
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "why did the shower light turn off this morning?",
        session_id="reasoning-mode-causal-why",
    )

    assert len(ai.requests) >= 3
    assert ai.requests[-1][1]["json"].get("tools") in (None, [])
    assert outcome.metrics["counters"].get("investigative_finalization", 0) == 1
    assert "do not by themselves identify" not in outcome.message
    assert "motion-timeout" in outcome.message


@pytest.mark.asyncio
async def test_non_causal_history_gets_grounded_synthesis_round() -> None:
    """0.10.447: successful history is evidence, not the final answer.

    The tool computes exact interval arithmetic, then the model gets a second
    round to answer the actual question.  This replaces the old unconditional
    event-dump early return that made "how long was X on?" impossible.
    """

    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_device_history_call()]}},
        {
            "message": {
                "role": "assistant",
                "content": "Shower Light was on for about 35 seconds.",
            }
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "how long was the shower light on?",
        session_id="reasoning-mode-non-causal",
    )

    assert len(ai.requests) >= 2
    assert "35 seconds" in outcome.message
    second_round_messages = ai.requests[1][1]["json"]["messages"]
    tool_messages = [
        str(message.get("content") or "")
        for message in second_round_messages
        if message.get("role") == "tool"
    ]
    assert any("temporalAnalysis" in content for content in tool_messages)
    assert any("totalActiveSeconds" in content for content in tool_messages)
    hint_messages = [
        str(message.get("content") or "")
        for message in second_round_messages
        if message.get("role") == "user"
    ]
    assert any(
        "HOST HISTORY-SYNTHESIS HINT" in content for content in hint_messages
    )


@pytest.mark.asyncio
async def test_causal_history_uses_generic_evidence_contract_not_sensor_hunt() -> None:
    """0.10.454: causal reads share the generic bounded reasoning contract.

    The legacy hint explicitly told the model to hunt related room sensors and
    caused 19-call/76-second live investigations. The orchestrator may still
    append that compatibility message internally, but transport policy must
    remove it before the provider sees the turn and retain the current-turn
    evidence boundary plus the generic tool-result review contract.
    """

    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_device_history_call()]}},
        {"message": {"role": "assistant", "content": "The event history alone does not prove the cause."}},
        {"message": {"role": "assistant", "content": "The event history alone does not prove the cause."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    await agent.process_user_request_result(
        "why did the shower light turn off this morning?",
        session_id="reasoning-mode-causal-generic",
    )

    assert len(ai.requests) >= 3
    assert ai.requests[-1][1]["json"].get("tools") in (None, [])
    second_round_messages = ai.requests[1][1]["json"]["messages"]
    rendered = "\n".join(
        str(message.get("content") or "") for message in second_round_messages
    )
    assert "HOST CAUSAL-INVESTIGATION HINT" not in rendered
    assert "CURRENT-TURN EVIDENCE BOUNDARY" in rendered
    tool_messages = [
        str(message.get("content") or "")
        for message in second_round_messages
        if message.get("role") == "tool"
    ]
    assert any("HOST EVIDENCE-REVIEW CONTRACT" in content for content in tool_messages)


def test_hub_info_tool_description_advertises_zigbee_and_zwave_radio_status() -> None:
    from tool_registry import hub_info_tool

    description = hub_info_tool().description.casefold()
    assert "zigbee" in description
    assert "z-wave" in description or "zwave" in description

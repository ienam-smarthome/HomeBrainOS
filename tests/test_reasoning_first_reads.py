from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402

"""0.10.410 regression coverage: historical/causal/diagnostic READ questions
(last-contact, count/list-yesterday, motion aggregation, location events,
mode-last-entered, hub health, firmware status) used to be intercepted by a
hand-coded deterministic parser + canned answer template before the model
ever saw the prompt -- an ever-growing list of bespoke parsers for every new
phrasing. `deterministic_reads_enabled` now defaults to False: those
questions fall through to the general native-function-calling loop, which
calls the exact same underlying tools and reasons over the result itself.
Existing tests in test_homebrain_agent.py pin the exact prior behaviour with
deterministic_reads_enabled=True (the rollback lever); this file pins the
new default behaviour instead.
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
    """Regression test: with deterministic_reads_enabled left at its new
    default (False, not passed at all), "check the hub health status" must
    no longer be intercepted by the old hand-coded dispatch branch --
    it should reach the general model loop and actually invoke the model,
    unlike every existing deterministic-mode test in test_homebrain_agent.py
    which asserts `ai.requests == []`.
    """

    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_location_events_call()]}},
        {"message": {"role": "assistant", "content": "The hub looks healthy."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "check the hub health status", session_id="reasoning-mode-hub-health"
    )

    assert len(ai.requests) >= 1, (
        "the model must actually be invoked once deterministic reads are "
        "disabled by default -- the old fast path never called it at all"
    )
    assert "healthy" in outcome.message.casefold()


@pytest.mark.asyncio
async def test_location_events_question_is_now_reachable_via_a_declared_tool() -> None:
    """Regression test: location/mode-event questions previously worked
    *only* through the deterministic dispatch branch, which called the MCP
    client directly -- there was no homebrain_location_events tool declared
    to the model at all, so disabling that dispatch branch would have made
    these questions entirely unanswerable. homebrain_location_events is now
    declared by default (tool_catalog_assembly.py), so the model can call it
    itself in reasoning mode.
    """

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
    """Regression test for the Shower Light live-testing finding: a
    genuinely causal "why did X happen" question used to be cut off the
    instant homebrain_device_history returned a successful result --
    mcp_agent_orchestrator.py's early-return fired unconditionally for any
    successful call to this tool, handing back a fixed "does not by
    themselves identify what caused them" disclaimer and ending the loop
    right there, even though the model is fully capable of investigating
    further (or at minimum synthesising a real answer from the fetched
    events) when actually allowed to keep reasoning. The bypass only
    applies when the prompt itself is asking "why".
    """

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
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "why did the shower light turn off this morning?",
        session_id="reasoning-mode-causal-why",
    )

    assert len(ai.requests) >= 2, (
        "a causal 'why' question must get a second model round to actually "
        "reason over the fetched history instead of being cut off after "
        "the first round's tool call"
    )
    assert "do not by themselves identify" not in outcome.message
    assert "motion-timeout" in outcome.message


@pytest.mark.asyncio
async def test_non_causal_history_question_keeps_the_deterministic_template() -> None:
    """Regression guard for the opposite direction: a plain "what happened"
    question (no "why") must still get the exact prior templated,
    hallucination-safe summary -- the bypass above must not widen to cover
    every device-history call, only genuinely causal ones.
    """

    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_device_history_call()]}},
        # No second response scripted -- if the early return fails to fire,
        # this test will error on a StopIteration from FakeAI instead of a
        # clean assertion failure, which is itself a useful signal.
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "what happened to the shower light this morning?",
        session_id="reasoning-mode-non-causal",
    )

    assert len(ai.requests) == 1, (
        "a plain factual history question must still stop after the first "
        "round via the deterministic template, not consume a second model "
        "round"
    )
    assert "do not by themselves identify" in outcome.message


@pytest.mark.asyncio
async def test_causal_bypass_nudges_the_model_to_check_a_correlated_sensor() -> None:
    """Regression test (0.10.411): a live run of the causal "why" bypass
    just re-narrated the same switch-only event list instead of checking a
    plausible related sensor (e.g. motion) in the same room, even though
    the bypass gave it a second round to do so -- a second round alone does
    not make the model investigate. The orchestrator must now inject an
    explicit host hint after the device-history tool result telling the
    model to consider a related sensor before answering.
    """

    mcp = ReasoningModeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [_device_history_call()]}},
        {"message": {"role": "assistant", "content": "Likely a motion-timeout automation."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    await agent.process_user_request_result(
        "why did the shower light turn off this morning?",
        session_id="reasoning-mode-causal-hint",
    )

    assert len(ai.requests) >= 2
    second_round_messages = ai.requests[1][1]["json"]["messages"]
    hint_messages = [
        message.get("content", "")
        for message in second_round_messages
        if message.get("role") == "user"
    ]
    assert any(
        "HOST CAUSAL-INVESTIGATION HINT" in content for content in hint_messages
    ), "the model must be explicitly nudged to check a correlated sensor"


def test_hub_info_tool_description_advertises_zigbee_and_zwave_radio_status() -> None:
    """Regression test (0.10.411): a live run of "check the hub health
    status" in reasoning mode came back with memory/uptime/temperature but
    no Zigbee/Z-Wave radio status at all -- the data was always in
    homebrain_hub_info_snapshot's result, but its tool description never
    told the model this was the tool to call for radio status, so the
    model reached for hub_read_diagnostics instead (which does not carry
    it) and never asked for it. The description is the only signal the
    model has before deciding which tool to call, so it must mention
    Zigbee/Z-Wave radio status explicitly.
    """

    from tool_registry import hub_info_tool

    description = hub_info_tool().description.casefold()
    assert "zigbee" in description
    assert "z-wave" in description or "zwave" in description

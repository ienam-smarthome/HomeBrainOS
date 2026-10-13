"""0.17.46 live regressions: current config gateway and exact BST event intent.

All remote responses are fakes; no live Hubitat or device mutation occurs.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from focal_event_provenance import (
    explicit_british_clock_source, explicit_requested_instant, select_focal_off,
)
from motion_lockout_investigation import (
    is_motion_lockout_investigation, prefetch_motion_lockout,
)
from targeted_lockout_config import (
    current_lockout_config_app_id, read_current_lockout_config,
)
from mcp_agent_orchestrator import UnifiedMCPAgent
from mcp_client import MCPTool


CONFIG_QUESTION = (
    "Read app 4019's persisted motion-off lockout duration, trigger mode "
    "and configured button. Compare these against my intended three-minute "
    "duration, keeping current settings separate from historical execution. Read-only."
)
EXACT_QUESTION = (
    "Independently reconstruct Livingroom Light 1's OFF at approximately "
    "23:49:27 BST on 12 October 2026. Correlate device 746's physical button "
    "press, app 1251's OFF command, device 7805's state, subsequent eligible "
    "motion and app 4019's lockout decision. Use correct UTC log windows. Read-only."
)


def test_current_settings_is_not_undeclared_tool_model_selection():
    assert current_lockout_config_app_id(CONFIG_QUESTION) == "4019"
    assert current_lockout_config_app_id(EXACT_QUESTION) is None
    assert current_lockout_config_app_id(
        "Did app 4019 motion lockout engage after yesterday's manual OFF?"
    ) is None


@pytest.mark.asyncio
async def test_current_config_fetches_known_read_gateway_without_provider():
    calls = []

    class FakeExecutor:
        async def execute(self, name, args, **kwargs):
            calls.append((name, args))
            return SimpleNamespace(success=True, result=SimpleNamespace(data={
                "settings": {
                    "motionOffLockoutMinutes": "300",
                    "motionOffLockoutTrigger": "toggleButtonOnly",
                    "password": "not-for-output",
                },
            }))

    class Catalog:
        def available_tool(self, name):
            assert name == "hub_read_apps_code"
            return object()

    result = await read_current_lockout_config(
        SimpleNamespace(executor=FakeExecutor()), CONFIG_QUESTION,
        catalog=Catalog(),
    )
    assert len(calls) == 1
    assert calls[0] == ("hub_read_apps_code", {
        "tool": "hub_get_app_config",
        "args": {"appId": "4019", "includeSettings": True},
    })
    assert "300 minutes" in result
    assert "toggleButtonOnly" in result
    assert "3 minutes" in result
    assert "do not match" in result
    assert "not independently established" in result
    assert "not-for-output" not in result


@pytest.mark.asyncio
async def test_permission_denial_and_missing_settings_do_not_invent_values():
    class Denied:
        def available_tool(self, name):
            return None

    assert "unavailable" in await read_current_lockout_config(
        SimpleNamespace(), CONFIG_QUESTION, catalog=Denied(),
    )

    class Executor:
        async def execute(self, *args, **kwargs):
            return SimpleNamespace(
                success=False, result=SimpleNamespace(data={}),
            )

    class Available:
        def available_tool(self, name):
            return object()

    result = await read_current_lockout_config(
        SimpleNamespace(executor=Executor()), CONFIG_QUESTION,
        catalog=Available(),
    )
    assert "remain unverified" in result


@pytest.mark.asyncio
async def test_real_orchestrator_shortcuts_provider_for_named_app_config(monkeypatch):
    class MCP:
        async def list_tools(self):
            return [MCPTool(
                "hub_read_apps_code", "Read installed app settings",
                {"type": "object"},
            )]

    agent = UnifiedMCPAgent(MCP(), "key", "gemma4:31b", ai_client=object())

    async def fake_execute(name, args, **kwargs):
        assert name == "hub_read_apps_code"
        return SimpleNamespace(success=True, result=SimpleNamespace(data={
            "settings": {"motionOffLockoutMinutes": "300"},
        }))
    monkeypatch.setattr(agent.executor, "execute", fake_execute)

    async def no_model(*args, **kwargs):
        raise AssertionError("No model selection should be required")
    monkeypatch.setattr(agent, "_system_prompt", no_model)

    text = await agent.process_user_request(CONFIG_QUESTION)
    assert "300 minutes" in text
    assert "do not match" in text


def test_explicit_bst_anchor_is_exact_and_not_latest_state():
    assert is_motion_lockout_investigation(EXACT_QUESTION)
    source = explicit_british_clock_source(EXACT_QUESTION)
    assert source == "2026-10-12T23:49:27+01:00"
    target = explicit_requested_instant(EXACT_QUESTION, source)
    assert target.isoformat() == "2026-10-12T22:49:27+00:00"
    latest_only = {"observedEvents": [
        {"name": "switch", "value": "off",
         "date": "2026-10-13T22:52:21.258+0100"},
    ]}
    selection = select_focal_off(
        latest_only, EXACT_QUESTION, source_local=source,
    )
    assert selection["selectedOff"] is None
    assert selection["explicitTargetUtc"] == "2026-10-12T22:49:27+00:00"
    assert selection["latestObservedOff"].startswith("2026-10-13")
    assert explicit_british_clock_source(
        "Investigate OFF at 23:49:27 GMT on 12 October 2026"
    ) is None


@pytest.mark.asyncio
async def test_historical_prefetch_queries_requested_utc_even_when_state_history_missing():
    light = {"id": "7805", "label": "Livingroom Light 1",
             "room": "Living Room", "attributes": {"switch": "off"}}
    button = {"id": "746", "label": "🔢 Living Room Button",
              "room": "Button Controllers",
              "attributes": {"pushed": "1"}, "capabilities": ["PushableButton"]}
    records, calls = [], []

    class MCP:
        async def get_device_identities(self):
            return [light, button]

    class Catalog:
        def declared_tool(self, name):
            return object()

    class Executor:
        async def execute(self, name, args, **kwargs):
            calls.append((name, args))
            if name == "homebrain_device_history":
                if args["attribute"] == "pushed":
                    data = {"observedEvents": [
                        {"name": "pushed", "value": "1", "type": "physical",
                         "date": "2026-10-12T23:49:27.303+0100",
                         "producedBy": {"id": "746", "type": "device"}},
                    ]}
                else:
                    data = {
                        "temporalAnalysis": {"observedIntervals": [
                            {"start": "2026-10-13T22:49:00+0100",
                             "end": "2026-10-13T22:52:21.258+0100"},
                        ]},
                        "commandEvents": [{
                            "name": "command-off",
                            "date": "2026-10-12T23:49:27.336+0100",
                            "producedBy": {"id": "1251",
                                           "type": "app", "label": "button 1 pushed"},
                        }],
                    }
            elif args.get("tool") == "hub_get_app_config":
                data = {"settings": {"motionOffLockoutMinutes": "300"}}
            elif args.get("tool") == "hub_get_logs":
                data = {"logs": []}
            else:
                raise AssertionError((name, args))
            return SimpleNamespace(success=True, result=SimpleNamespace(data=data))

    class Evidence:
        def record(self, name, args, **kwargs):
            records.append((name, kwargs.get("details")))

    host = SimpleNamespace(
        mcp=MCP(), executor=Executor(), historical_journal=None,
        evidence=Evidence(),
    )
    messages = []
    assert await prefetch_motion_lockout(
        host, EXACT_QUESTION, catalog=Catalog(), messages=messages,
    )
    details = next(d for name, d in records
                   if name == "homebrain_motion_lockout_investigation")
    assert details["requestedEventUtc"] == "2026-10-12T22:49:27+00:00"
    assert details["requestedEventStateObserved"] is False
    assert details["focalSelection"]["selectedOff"] is None
    assert details["status"] == "explicit-event-not-observed"
    assert details["manualOffVerified"] is False
    assert not details["lockoutExecutionVerified"]
    assert len([x for x in calls if x[0] == "homebrain_device_history"]) == 2
    assert next(x for x in details["sources"]
                if x["source"] == "targeted-native-controller-history"
               )["verifiedPhysicalPresses"] == 1
    args = next(a["args"] for _, a in calls
                if a.get("tool") == "hub_get_logs")
    assert args["appId"] == "4019"
    assert args["since"] == "2026-10-12T22:49:07+00:00"
    assert args["until"] == "2026-10-12T22:52:42+00:00"
    assert "2026-10-13" not in args["since"]

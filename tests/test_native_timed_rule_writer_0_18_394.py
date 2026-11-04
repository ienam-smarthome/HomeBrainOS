"""Offline native MCP 5.1.6 dated Switch creation/confirmation contracts."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from native_switch_schedule import create_dated_switch, dated_switch_proposal_error
from rule_authoring_service import RuleAuthoringService
from rule_writer_contract import NATIVE_DOCUMENT
from tool_registry import rule_machine_proposal_error
from confirmation_policy import _rule_confirmation_prompt, ConfirmationPolicy
from confirmed_action_coordinator import ConfirmedActionCoordinator
from mcp_client import MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect

NAME = "HB one-shot | Block Media Google TV Streamer (One-time 2026-11-10 15:35)"


def candidate():
    return create_dated_switch(
        name=NAME, parent_id=169, device_id="6923", command="off",
        hub_local_at=datetime(2026, 11, 10, 15, 35, tzinfo=ZoneInfo("Europe/London")),
    )


def gateway_call():
    return {"tool": "hub_set_rule", "args": candidate()["args"]}


def receipt(*, partial=False, broken=False, jobs=True, different_rule=False):
    return {
        "success": True, "created": True, "rule_id": 4399,
        "broken": broken, "partial": partial,
        "stopped": False, "paused": False,
        "eventSubscriptions": [],
        "scheduledJobs": [{"method": "runRule"}] if jobs else [],
        "document": {
            "rule_id": 4400 if different_rule else 4399,
            "triggers": {"1": "at 15:35 on 2026-11-10"},
            "actions": [{"id": "1", "value": {"method": "getOnOffSwitch"}}],
        },
    }


def execution(data):
    args = gateway_call()
    return ToolExecution(
        name="hub_manage_rule_machine", arguments=args,
        effect=ToolEffect.SENSITIVE_WRITE, success=True, elapsed_ms=1,
        content="{}", result=MCPToolResult("hub_manage_rule_machine", args, {}, "", data),
    )


def test_native_create_is_validated_at_gateway_and_has_explicit_confirmation():
    call = gateway_call()
    assert dated_switch_proposal_error(call["args"]) is None
    assert rule_machine_proposal_error("hub_manage_rule_machine", call) is None
    rendered = _rule_confirmation_prompt([("hub_manage_rule_machine", call)])
    assert "2026-11-10 15:35" in rendered
    assert "6923" in rendered
    assert "OFF (block Internet)" in rendered
    approved = ConfirmationPolicy.approved_arguments(
        "hub_manage_rule_machine", call,
    )
    assert approved["args"]["confirm"] is True
    assert "confirm" not in call["args"]
    assert dated_switch_proposal_error(approved["args"]) is not None
    assert dated_switch_proposal_error(approved["args"], approved=True) is None


@pytest.mark.parametrize("patch", [
    {"operation": "update"},
    {"args": {"parent_id": 169, "name": NAME, "changes": []}},
    {"newUnattestedField": True},
])
def test_native_gate_rejects_unverified_creates(patch):
    args = candidate()["args"]
    args.update(patch)
    assert rule_machine_proposal_error(
        "hub_manage_rule_machine", {"tool": "hub_set_rule", "args": args}
    ) is not None


def test_native_receipt_must_prove_persisted_document_and_schedule():
    args = ConfirmationPolicy.approved_arguments(
        "hub_manage_rule_machine", gateway_call(),
    )
    ok = execution(receipt())
    assert ConfirmedActionCoordinator.verified_rule_execution(ok, args)
    report = ConfirmedActionCoordinator.confirmed_rule_report(
        [("hub_manage_rule_machine", args, ok)], queued_count=1,
    )
    assert "native rule ID **4399**" in report
    assert "scheduled job(s)" in report
    assert "Physical execution is not verified" in report
    for kwargs in [
        {"partial": True}, {"broken": True}, {"jobs": False},
        {"different_rule": True},
    ]:
        assert not ConfirmedActionCoordinator.verified_rule_execution(
            execution(receipt(**kwargs)), args,
        )


def test_native_version_attestation_is_server_identity_not_model_guess():
    s = SimpleNamespace(server_info={
        "name": "hubitat-mcp-rule-server", "version": "5.1.6"
    })
    assert RuleAuthoringService._native_date_supported(s)
    s.server_info["version"] = "5.1.5"
    assert not RuleAuthoringService._native_date_supported(s)
    s.server_info["version"] = "5.1.7"
    assert RuleAuthoringService._native_date_supported(s)
    s.server_info["name"] = "unrelated-server"
    assert not RuleAuthoringService._native_date_supported(s)


@pytest.mark.asyncio
async def test_parent_identified_from_two_typed_read_only_sources():
    class MCP:
        calls = []

        async def call_tool(self, gateway, args):
            self.calls.append((gateway, args))
            if args["tool"] == "hub_list_apps":
                data = {
                    "apps": [{"id": 169, "name": "Rule Machine", "type": "Rule Machine",
                              "appTypeId": 18, "parentId": None, "user": False}],
                    "count": 1,
                }
            else:
                data = {
                    "success": True, "id": 169, "name": "Rule Machine",
                    "type": "Rule Machine", "namespace": "hubitat",
                    "user": False, "appTypeId": 18, "parentId": None,
                }
            return MCPToolResult(gateway, args, {}, "", data)
    mcp = MCP()
    service = RuleAuthoringService(mcp, lambda *args, **kwargs: None)
    assert await service._native_parent_id() == 169
    assert len(mcp.calls) == 2
    assert all(gateway == "hub_read_apps_code" for gateway, _ in mcp.calls)


@pytest.mark.asyncio
async def test_confirmation_replay_rejects_old_version_or_duplicate():
    class MCP:
        server_info = {"name": "hubitat-mcp-rule-server", "version": "5.1.6"}
    mcp = MCP()
    service = RuleAuthoringService(mcp, lambda *args, **kwargs: None)

    async def contract():
        return NATIVE_DOCUMENT
    async def parent():
        return 169
    async def names():
        return set()
    service._rule_writer_contract = contract
    service._native_parent_id = parent
    service._existing_names = names
    assert await service.duplicate_create_group_error([gateway_call()]) is None
    mcp.server_info["version"] = "5.1.5"
    assert "5.1.6" in await service.duplicate_create_group_error([gateway_call()])
    mcp.server_info["version"] = "5.1.6"
    async def duplicate():
        return {NAME.casefold()}
    service._existing_names = duplicate
    assert "already exist" in await service.duplicate_create_group_error([gateway_call()])


@pytest.mark.asyncio
async def test_end_to_end_positive_relative_and_clock_schedule_compiler():
    """No native write occurs; only an approved future proposal is compiled."""
    # Avoid test-module import coupling: the same bounded fake server is
    # implemented locally and exposes only device/rule source reads.
    class Source:
        server_info = {"name": "hubitat-mcp-rule-server", "version": "5.1.6"}
        def __init__(self):
            self.calls = []
        async def get_cached_devices(self):
            return [{"id": "6923", "label": "Block Google-TV-Streamer",
                     "room": "Internet", "commands": ["on", "off"],
                     "capabilities": ["Switch"]}]
        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_devices":
                data = {"devices": await self.get_cached_devices()}
            elif name == "hub_read_rules":
                data = {"rules": [], "count": 0}
            else:
                raise AssertionError(f"unexpected source read: {name}")
            return MCPToolResult(name, arguments, {}, "", data)
    source = Source()
    fixed = datetime(2026, 11, 10, 8, 0, tzinfo=ZoneInfo("Europe/London"))
    service = RuleAuthoringService(source, lambda *a, **kw: None, now=lambda: fixed)
    async def contract():
        return NATIVE_DOCUMENT
    async def parent():
        return 169
    async def guide_key():
        return None
    async def hubtime(clock):
        return fixed, "Europe/London", "source-verified-test-clock"
    service._rule_writer_contract = contract
    service._native_parent_id = parent
    service._native_guide_key = guide_key
    service._hub_timezone.now_in_hub_timezone = hubtime
    for prompt in ("block the tv after 15 minutes", "block the tv at 8:15am"):
        decision = await service.propose(
            prompt, available_gateways={"hub_manage_rule_machine"},
        )
        assert decision.handled and decision.message is None
        assert len(decision.actions) == 1
        action = decision.actions[0]
        assert rule_machine_proposal_error("hub_manage_rule_machine", action) is None
        changes = action["args"]["args"]["changes"]
        assert changes[0]["value"]["fields"][-1]["value"] == "2026-11-10"
        assert changes[1]["value"]["fields"][0]["value"] == ["6923"]
        assert changes[1]["value"]["fields"][1]["value"] is False
        assert all(tool != "hub_manage_rule_machine" for tool, _ in source.calls)

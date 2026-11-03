"""Regression: incompatible upstream native Rule Machine API must not get writes.

All probes are synthetic/read-only. A server's return of
'Unknown hub_set_rule property' is not a safe invitation to retry a
different, guessed action schema.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from mcp_client import MCPToolResult
from rule_writer_contract import (
    LEGACY, NATIVE_DOCUMENT, UNKNOWN,
    installed_rule_writer_contract, legacy_rule_writer_incompatibility,
)
from rule_authoring_service import RuleAuthoringService, RULE_MACHINE_GATEWAY

NEW_GUIDE = """
## Set Rule Reference
Call hub_set_rule without operation for help, or choose a write operation
without confirm to inspect its schema. Writes require confirm=true and a
recent backup.
hub_set_rule(operation:"create",args:{parent_id,name,changes:[...]},confirm:true)
creates a native Rule-5.1 child under native Rule Machine.
Each change is {part,value}. Unknown fields cannot be assumed to compile.
"""
OLD_GUIDE = """
## set_rule_reference
hub_set_rule name, addTrigger {capability,time,atTime}
and addAction {capability,deviceIds,command}; edit using appId.
"""


class Server:
    def __init__(self, guide=NEW_GUIDE, error=False):
        self.guide = guide
        self.error = error
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_get_tool_guide":
            if self.error:
                raise RuntimeError("Guide unavailable")
            return MCPToolResult(name, arguments, {}, "", {"content": self.guide})
        if name == "hub_read_rules":
            return MCPToolResult(name, arguments, {}, "", {"rules": []})
        # No scheduler, device or rule write is permissible with a new guide.
        raise AssertionError(f"unexpected call: {name}")


def _recorder(*_args, **_kwargs):
    pass


def _service(server):
    return RuleAuthoringService(
        server, _recorder,
        now=lambda: datetime(2026, 11, 2, 15, 20, tzinfo=timezone.utc)
    )


def test_current_server_document_guide_is_distinguished_from_old_shortcuts():
    assert installed_rule_writer_contract({"content": NEW_GUIDE}) == NATIVE_DOCUMENT
    assert installed_rule_writer_contract({"content": OLD_GUIDE}) == LEGACY
    assert installed_rule_writer_contract({"content": "Rule creation reference"}) == UNKNOWN
    assert "NEW native" in legacy_rule_writer_incompatibility(NATIVE_DOCUMENT)
    assert legacy_rule_writer_incompatibility(LEGACY) is None


@pytest.mark.asyncio
async def test_native_document_server_is_rejected_before_confirmation_or_write():
    server = Server()
    result = await _service(server).propose(
        "Turn off Desk Lamp at 3:35pm",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    assert result.handled and not result.actions
    assert result.message is not None
    assert "No rule write was queued or executed" in result.message
    assert "parent_id" in result.message
    assert "native" in result.message.casefold()
    assert "native_oneshot_date_field_unverified" in result.message
    assert server.calls == [("hub_get_tool_guide", {"section": "set_rule_reference"})]


@pytest.mark.asyncio
async def test_unknown_guide_fails_closed_without_confirm_or_write():
    server = Server(error=True)
    result = await _service(server).propose(
        "Turn on Desk Lamp at 7am",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    assert result.handled and not result.actions
    assert "could not verify" in result.message
    assert len(server.calls) == 1


@pytest.mark.asyncio
async def test_confirmed_legacy_create_is_revalidated_against_new_server_guide():
    server = Server()
    service = _service(server)
    old_proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Block Desk Lamp (One-time 2026-11-02 15:35)",
            "addTrigger": {"capability": "Certain Time (and optional date)",
                           "time": "A specific time",
                           "atTime": "2026-11-02T15:35:00"},
            "addAction": {"capability": "runCommand",
                          "deviceIds": ["9876"], "command": "off"},
        },
    }
    result = await service.duplicate_create_group_error([old_proposal])
    assert "safely stopped before confirmation" in result
    assert server.calls == [("hub_get_tool_guide", {"section": "set_rule_reference"})]


@pytest.mark.asyncio
async def test_legacy_confirmed_rule_preflight_still_checks_duplicates():
    server = Server(guide=OLD_GUIDE)
    service = _service(server)
    old_proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Block Desk Lamp (Daily)",
            "addTrigger": {"capability": "Certain Time (and optional date)",
                           "atTime": "15:35"},
            "addAction": {"capability": "runCommand", "deviceIds": ["9876"],
                          "command": "off"},
        },
    }
    result = await service.duplicate_create_group_error([old_proposal])
    assert result is None
    assert [name for name, _ in server.calls] == [
        "hub_get_tool_guide", "hub_read_rules"
    ]


def test_probe_resists_unrelated_or_error_outputs():
    assert installed_rule_writer_contract({"foo": NEW_GUIDE}) == UNKNOWN
    assert installed_rule_writer_contract({"content": 42}) == UNKNOWN
    class Errored:
        is_error = True
        data = {"content": OLD_GUIDE}
    assert installed_rule_writer_contract(Errored()) == UNKNOWN


@pytest.mark.asyncio
async def test_recurring_native_writer_refusal_does_not_claim_missing_one_shot_date():
    server = Server()
    result = await _service(server).propose(
        "Turn off Desk Lamp every day at 7am",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    assert result.handled and not result.actions
    assert "NEW native" in result.message
    assert "native_oneshot_date_field_unverified" not in result.message
    assert server.calls == [("hub_get_tool_guide", {"section": "set_rule_reference"})]

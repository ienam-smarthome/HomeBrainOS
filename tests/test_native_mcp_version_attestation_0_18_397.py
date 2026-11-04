"""Real #575 version gate: read-only installed MCP identity fallback.

A tool guide says which native document schema is installed, not whether its
date-field validator has been upgraded. These tests never invoke rule writes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPToolResult
from rule_authoring_service import RuleAuthoringService
from rule_writer_contract import NATIVE_DOCUMENT


class FakeMCP:
    def __init__(self, initialize_version="5.1.5", hub_version="5.1.5",
                 refresh_version=None, *, init_name="hubitat-mcp-rule-server",
                 fail_hub_info=False, allow_refresh=True):
        self.server_info = {"name": init_name, "version": initialize_version}
        self.hub_version = hub_version
        self.refresh_version = refresh_version
        self.calls = []
        self.fail_hub_info = fail_hub_info
        self.allow_refresh = allow_refresh

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        assert gateway == "hub_get_info"
        assert arguments == {}
        data = (
            {"mcpServerVersion": self.hub_version}
            if not self.fail_hub_info else {"error": "info unavailable"}
        )
        return MCPToolResult(gateway, arguments, {}, "", data,
                             is_error=self.fail_hub_info)

    async def initialize(self, force=False):
        self.calls.append(("initialize", {"force": force}))
        assert force is True
        if not self.allow_refresh:
            raise ConnectionError("synthetic connection failed")
        if self.refresh_version is not None:
            self.server_info = {
                "name": "hubitat-mcp-rule-server",
                "version": self.refresh_version,
            }


def service(mcp):
    evidence = []
    obj = RuleAuthoringService(
        mcp, lambda tool, args, **kwargs: evidence.append((tool, args, kwargs)),
    )
    return obj, evidence


@pytest.mark.asyncio
async def test_current_supported_initialize_stays_fast_with_zero_extra_reads():
    mcp = FakeMCP(initialize_version="5.1.6")
    subject, evidence = service(mcp)
    supported, source = await subject._native_date_version_check()
    assert supported is True
    assert source == "MCP initialize serverInfo"
    assert not mcp.calls
    assert evidence == []


@pytest.mark.asyncio
async def test_real_old_server_is_reported_not_masked_as_generic_unknown():
    mcp = FakeMCP(initialize_version="5.1.5", hub_version="5.1.5")
    subject, evidence = service(mcp)
    supported, reason = await subject._native_date_version_check()
    assert not supported
    assert "5.1.5" in reason
    assert "5.1.6 or later" in reason
    assert "Hubitat Package Manager" in reason
    assert "No rule was created" in reason
    assert mcp.calls == [("hub_get_info", {})]
    assert evidence[0][2]["mutates"] is False
    assert evidence[0][2]["effect"] == "read"
    assert evidence[0][2]["details"] == {
        "initializeVersion": "5.1.5",
        "hubInfoMcpServerVersion": "5.1.5",
    }


@pytest.mark.asyncio
async def test_stale_initialize_is_refreshed_only_when_current_hub_is_newer():
    mcp = FakeMCP(
        initialize_version="5.1.5", hub_version="5.1.6",
        refresh_version="5.1.6",
    )
    subject, evidence = service(mcp)
    supported, source = await subject._native_date_version_check()
    assert supported
    assert "refreshed" in source
    assert mcp.calls == [
        ("hub_get_info", {}),
        ("initialize", {"force": True}),
    ]
    assert evidence[0][2]["details"]["hubInfoMcpServerVersion"] == "5.1.6"


@pytest.mark.parametrize("refresh_version,allow_refresh", [
    ("5.1.5", True),
    (None, True),
    (None, False),
])
@pytest.mark.asyncio
async def test_mismatched_or_failed_refresh_refuses_write(refresh_version, allow_refresh):
    mcp = FakeMCP(
        initialize_version="5.1.5", hub_version="5.1.6",
        refresh_version=refresh_version, allow_refresh=allow_refresh,
    )
    subject, _ = service(mcp)
    supported, reason = await subject._native_date_version_check()
    assert not supported
    assert "could not be reconciled" in reason


@pytest.mark.parametrize("hub_version,invalid_name,fail", [
    ("", False, False),
    ("v5.1.6", False, False),
    ("not-a-version", False, False),
    ("5.1.6", True, True),
])
@pytest.mark.asyncio
async def test_no_trustworthy_installed_version_fails_closed(hub_version, invalid_name, fail):
    mcp = FakeMCP(
        initialize_version="5.1.5" if not invalid_name else "2.5.3.114",
        hub_version=hub_version,
        init_name="Hubitat Hub" if invalid_name else "hubitat-mcp-rule-server",
        fail_hub_info=fail,
    )
    subject, _ = service(mcp)
    supported, reason = await subject._native_date_version_check()
    assert not supported
    assert "No rule was created" in reason


@pytest.mark.asyncio
async def test_native_proposal_with_5_1_5_stops_before_device_and_parent_reads():
    mcp = FakeMCP()
    subject, _ = service(mcp)
    async def native_contract():
        return NATIVE_DOCUMENT
    subject._rule_writer_contract = native_contract
    proposal = await subject.propose(
        "Block TV after 30 mins",
        available_gateways={"hub_manage_rule_machine"},
    )
    assert proposal.handled
    assert proposal.actions == ()
    assert "5.1.5" in proposal.message
    assert "5.1.6" in proposal.message
    assert mcp.calls == [("hub_get_info", {})]


@pytest.mark.asyncio
async def test_newly_upgraded_native_proposal_reaches_next_safety_boundary():
    mcp = FakeMCP(
        initialize_version="5.1.5", hub_version="5.1.6",
        refresh_version="5.1.6",
    )
    subject, _ = service(mcp)
    async def native_contract():
        return NATIVE_DOCUMENT
    # A deliberate sentinel: proves the request cleared only the version
    # boundary, not that a real target, parent or write was authorised.
    async def hub_timezone(_clock):
        raise RuntimeError("test reached next source preflight")
    subject._rule_writer_contract = native_contract
    subject._hub_timezone.now_in_hub_timezone = hub_timezone
    with pytest.raises(RuntimeError, match="reached next source preflight"):
        await subject.propose(
            "Block TV after 30 mins",
            available_gateways={"hub_manage_rule_machine"},
        )
    assert mcp.calls == [
        ("hub_get_info", {}),
        ("initialize", {"force": True}),
    ]


@pytest.mark.asyncio
async def test_duplicate_replay_old_version_refused_before_any_native_write():
    mcp = FakeMCP(initialize_version="5.1.5", hub_version="5.1.5")
    subject, _ = service(mcp)
    async def native_contract():
        return NATIVE_DOCUMENT
    subject._rule_writer_contract = native_contract
    native_action = {
        "tool": "hub_set_rule",
        "args": {
            "operation": "create",
            "args": {"name": "HB one-shot | X (One-time 2026-11-04 15:35)"}
        }
    }
    error = await subject.duplicate_create_group_error([native_action])
    assert "5.1.5" in error
    assert "No rule was created" in error
    assert mcp.calls == [("hub_get_info", {})]

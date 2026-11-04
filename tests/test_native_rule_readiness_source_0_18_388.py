"""Read-only native Rule Machine preflight must not become rule inventory.

Synthetic sources only, no real MCP endpoint, model calls or writes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from native_rule_inventory_source import is_native_rule_inventory_question  # noqa: E402
from native_rule_readiness_source import (  # noqa: E402
    is_native_rule_readiness_question, read_native_rule_readiness,
    native_rule_readiness_coverage,
)

QUESTION = (
    "Read-only preflight for a future disposable native Rule Machine timed-switch test.\n"
    "Report the installed MCP Rule Server version only if its own read-only\n"
    "status/info source exposes a version. Otherwise mark it unverified.\n"
    "Report the newest Hubitat local backup timestamp using read-only backup\n"
    "inventory, or say why backup freshness cannot be verified.\n"
    "Check whether the read-only MCP tool guides for set_rule_reference and\n"
    "builtin_app_tools_rules are available; report which sections are readable,\n"
    "without copying acknowledgement tokens or private configuration.\n"
    "Do not create a backup, virtual device or rule. Do not run, change,\n"
    "pause or delete anything and do not access router controls."
)

class NeverAskModel:
    async def chat(self, *args, **kwargs):
        raise AssertionError("Read-only preflight must not invoke model rounds")


class FakeMCP:
    def __init__(self, *, server=True, partial=False, bad_timestamp=False,
                 missing_guide=None, missing_gateway=None):
        self.calls = []
        self.server_info = (
            {"name": "hubitat-mcp-rule-server", "version": "5.1.5"}
            if server else {"name": "Hubitat hub", "version": "2.5.3.103"}
        )
        self.partial = partial
        self.bad_timestamp = bad_timestamp
        self.missing_guide = missing_guide
        self.missing_gateway = missing_gateway

    async def list_tools(self):
        tools = [
            MCPTool("hub_read_apps_code", "read-only Hubitat admin", {"type": "object"}),
            MCPTool("hub_get_tool_guide", "read-only tool guide", {"type": "object"}),
            MCPTool("hub_read_rules", "Rules", {"type": "object"}),
            MCPTool("hub_manage_rule_machine", "Rule writes", {"type": "object"}),
        ]
        return [tool for tool in tools if tool.name != self.missing_gateway]

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        assert gateway in {"hub_read_apps_code", "hub_get_tool_guide"}
        if gateway == "hub_read_apps_code":
            assert arguments == {
                "tool": "hub_list_backups", "args": {"scope": "hub_local"}
            }
            data = {
                "scope": "hub_local",
                "hubLocalBackups": [
                    {"name": "PRIVATE-HUB-NAME-1.lzf",
                     "createTimeOrig": "2026-11-02T03:00:00+0000"},
                    {"name": "PRIVATE-HUB-NAME-2.lzf",
                     "createTimeOrig": (
                         "unknown" if self.bad_timestamp
                         else "2026-11-03T03:01:00+0000"
                     )},
                ],
                **({"partial": True, "hubBackupErrors": ["unreadable"]}
                   if self.partial else {}),
            }
        else:
            section = arguments["section"]
            assert section in {"set_rule_reference", "builtin_app_tools_rules"}
            data = (
                {"success": False, "error": "guide unavailable"}
                if self.missing_guide == section else {
                    "success": True,
                    "content": (
                        "I-HAVE-READ-THE-GUIDE-" + section
                        + "-a12f109e\nPRIVATE-SECRET-KEY-DO-NOT-PUBLISH\n"
                    ),
                }
            )
        return MCPToolResult(gateway, arguments, {}, "", data)


def test_classifier_prefers_explicit_multi_source_read_only_preflight():
    assert is_native_rule_readiness_question(QUESTION)
    assert not is_native_rule_inventory_question(QUESTION)
    assert not is_native_rule_readiness_question(
        "List my existing one-time Rule Machine rules; do not create backups "
        "or read tool guides."
    )
    assert not is_native_rule_readiness_question(
        "Read-only Rule Machine inventory: list native parents and their IDs."
    )
    assert not is_native_rule_readiness_question(
        "Create and run a new timed Rule Machine rule after checking backups."
    )


@pytest.mark.asyncio
async def test_complete_preflight_direct_read_only_no_secret_leakage_or_model_rounds():
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b",
                            ai_client=NeverAskModel())
    outcome = await agent.process_user_request_result(
        QUESTION, session_id="native-preflight-direct"
    )
    assert outcome.request_class == "live-read"
    assert not outcome.confirmation_required
    assert outcome.confirmation_count == 0
    assert [name for name, _args in mcp.calls] == [
        "hub_read_apps_code", "hub_get_tool_guide", "hub_get_tool_guide",
    ]
    assert "5.1.5" in outcome.message
    assert "2026-11-03T03:01:00+00:00" in outcome.message
    assert "set_rule_reference: readable" in outcome.message
    assert "builtin_app_tools_rules: readable" in outcome.message
    assert "PRIVATE" not in outcome.message
    assert "I-HAVE-READ-THE-GUIDE-" not in outcome.message
    assert "Rule Machine inventory" not in outcome.message
    assert "does not authorize" in outcome.message
    assert outcome.investigation_coverage is not None
    assert outcome.investigation_coverage["domain"] == "native_rule_readiness"
    assert outcome.investigation_coverage["evidenceComplete"] is True
    assert outcome.investigation_coverage["readinessForMutation"] is False
    assert all(row["effect"] == "read" and row["mutates"] is False
               for row in outcome.evidence)
    receipt = outcome.evidence[-1]
    assert receipt["evidence_kind"] == "typed_native_rule_readiness"
    assert receipt["details"]["preflightEvidenceComplete"] is True
    assert "PRIVATE" not in str(outcome.evidence)
    assert "I-HAVE-READ-THE-GUIDE-" not in str(outcome.evidence)
    assert "PRIVATE" not in str(outcome.investigation_coverage)


@pytest.mark.parametrize("kwargs,expected", [
    ({"server": False}, "MCP Rule Server version (server-supplied): unverified"),
    ({"partial": True}, "backup inventory was partial or conflicted"),
    ({"bad_timestamp": True}, "backup timestamps were not parseable"),
    ({"missing_guide": "set_rule_reference"}, "set_rule_reference: unverified/unavailable"),
    ({"missing_guide": "builtin_app_tools_rules"},
     "builtin_app_tools_rules: unverified/unavailable"),
    ({"missing_gateway": "hub_get_tool_guide"},
     "builtin_app_tools_rules: unverified/unavailable"),
    ({"missing_gateway": "hub_read_apps_code"},
     "hub-local backup inventory unavailable"),
])
@pytest.mark.asyncio
async def test_preflight_source_failures_never_become_success_or_authorization(kwargs, expected):
    mcp = FakeMCP(**kwargs)
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        tools = {tool.name for tool in await mcp.list_tools()}
        answer, projection = await read_native_rule_readiness(
            mcp, recorder, available_names=tools
        )
        assert expected in answer
        assert projection["preflightEvidenceComplete"] is False
        assert projection["readinessForMutation"] is False
        assert "PRIVATE" not in answer
        assert "I-HAVE-READ-THE-GUIDE-" not in str(recorder.receipts())
        scope = native_rule_readiness_coverage(QUESTION, recorder.receipts())
        assert scope["evidenceComplete"] is False
        assert scope["questionResolved"] is False
        assert scope["readinessForMutation"] is False
        assert all(row["effect"] == "read" and row["mutates"] is False
                   for row in recorder.receipts())
        assert all(gateway not in {"hub_manage_rule_machine", "hub_create_backup"}
                   for gateway, _args in mcp.calls)
    finally:
        recorder.reset(token)


@pytest.mark.asyncio
async def test_no_mcp_gateway_available_does_not_guess_any_preflight_fact():
    mcp = FakeMCP(server=False)
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        message, projection = await read_native_rule_readiness(
            mcp, recorder, available_names=frozenset()
        )
        assert mcp.calls == []
        assert projection["latestHubLocalBackupUtc"] is None
        assert projection["mcpServerVersion"] is None
        assert not any(projection["toolGuideAvailability"].values())
        assert "unverified" in message
        assert "does not authorize" in message
    finally:
        recorder.reset(token)

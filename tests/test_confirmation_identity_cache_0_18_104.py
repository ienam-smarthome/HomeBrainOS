"""0.18.104: warm structural identity staging avoids 28s full inventory refresh.

No live hub requests: fake-MCP tests ensure the expensive fresh detailed
manifest is still required before an approved protected or bulk mutation.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from homebrain_agent import UnifiedMCPAgent
from test_control_fast_path_guards_0_18_103 import (
    DEVICES, FakeMCP, ScriptedAI, switch_writes,
)
from request_outcome_policy import classify_completed_request


class CountingManifestMCP(FakeMCP):
    def __init__(self):
        super().__init__()
        self.refresh_args: list[bool] = []
        self.peek_calls = 0

    def peek_device_identities(self):
        self.peek_calls += 1
        return self.devices

    async def get_device_identities(self):
        # Production MCPClient exposes this cheap TTL-checked structural
        # world reader. The old mock omitted it, so semantic grounding
        # unexpectedly fell back to the detailed manifest before staging.
        return self.peek_device_identities()

    async def get_cached_devices(self, refresh=False):
        self.refresh_args.append(bool(refresh))
        return self.devices


@pytest.mark.asyncio
async def test_staging_uses_warm_ttl_checked_identity_not_forced_refresh():
    mcp = CountingManifestMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    outcome = await agent.process_user_request_result(
        "turn off everything in Appliances", session_id="warm-staging",
    )
    assert outcome.confirmation_required
    assert "Fridge" in outcome.message and "Freezer" in outcome.message
    assert not any(mcp.refresh_args)
    assert mcp.peek_calls >= 1
    assert not switch_writes(mcp)
    assert outcome.metrics["outcome"] == "needs_input"
    assert outcome.metrics["counters"]["confirmation_queued"] == 1


@pytest.mark.asyncio
async def test_confirm_still_forces_detailed_manifest_refresh_before_execution():
    mcp = CountingManifestMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    staged = await agent.process_user_request_result(
        "turn off the Freezer", session_id="approve-refresh",
    )
    assert staged.confirmation_required is True
    assert not any(mcp.refresh_args)
    outcome = await agent.process_user_request_result(
        "confirm", session_id="approve-refresh",
    )
    assert mcp.refresh_args[-1] is True
    assert len(switch_writes(mcp)) == 1
    # FakeMCP acknowledges the command without changing its switch state.
    # Dispatcher safety is verified; the expected read-back failure is real.
    assert outcome.metrics["outcome"] == "failed"
    assert outcome.confirmation_required is False


@pytest.mark.asyncio
async def test_structural_snapshot_missing_commands_uses_switch_capability_for_preview():
    class CompactMCP(CountingManifestMCP):
        def peek_device_identities(self):
            self.peek_calls += 1
            return [{k: v for k, v in d.items() if k != "commands"}
                    for d in self.devices]

    mcp = CompactMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    staged = await agent.process_user_request_result(
        "turn off the Freezer", session_id="missing-command-metadata",
    )
    assert staged.confirmation_required
    assert mcp.refresh_args == []
    assert staged.metrics["counters"]["control_confirmation_preview_cache"] == 1
    assert not switch_writes(mcp)


@pytest.mark.asyncio
async def test_confirmation_fails_closed_if_fresh_snapshot_has_changed_id():
    mcp = CountingManifestMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    staged = await agent.process_user_request_result(
        "turn off Freezer", session_id="id-change",
    )
    assert staged.confirmation_required
    mcp.devices[0]["id"] = "12345"
    result = await agent.process_user_request_result("confirm", session_id="id-change")
    assert "changed" in result.message.lower()
    assert not switch_writes(mcp)
    assert mcp.refresh_args[-1] is True


@pytest.mark.asyncio
async def test_structural_switch_cache_stages_room_approval_without_manifest_read():
    class CompactSwitchMCP(CountingManifestMCP):
        def peek_device_identities(self):
            self.peek_calls += 1
            return [
                {k: v for k, v in d.items() if k != "commands"}
                for d in self.devices
            ]

    mcp = CompactSwitchMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    staged = await agent.process_user_request_result(
        "turn off everything in Appliances", session_id="compact-stage",
    )
    assert staged.confirmation_required is True
    assert "Freezer" in staged.message and "Fridge" in staged.message
    assert mcp.refresh_args == []  # no detailed calls, not even cached manifest
    assert staged.metrics["counters"]["control_confirmation_preview_cache"] == 1
    assert staged.metrics["counters"].get(
        "control_confirmation_manifest_fallback", 0
    ) == 0
    assert staged.metrics["outcome"] == "needs_input"
    assert switch_writes(mcp) == []


@pytest.mark.asyncio
async def test_compact_stage_still_requires_actual_advertised_command_on_confirm():
    class CommandDeniedAfterApproval(CountingManifestMCP):
        def peek_device_identities(self):
            return [
                {k: v for k, v in d.items() if k != "commands"}
                for d in self.devices
            ]

        async def get_cached_devices(self, refresh=False):
            self.refresh_args.append(bool(refresh))
            return [
                {**d, "commands": ["refresh"]} if d["label"] == "Freezer" else d
                for d in self.devices
            ]

    mcp = CommandDeniedAfterApproval()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    staged = await agent.process_user_request_result(
        "turn off Freezer", session_id="cap-denied",
    )
    assert staged.confirmation_required
    response = await agent.process_user_request_result(
        "confirm", session_id="cap-denied",
    )
    assert mcp.refresh_args == [True]
    assert "changed" in response.message.lower()
    assert switch_writes(mcp) == []


@pytest.mark.asyncio
async def test_explicit_empty_commands_not_treated_as_missing_metadata():
    mcp = CountingManifestMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    candidate = [
        {**d, "commands": []} if d["label"] == "Freezer" else d
        for d in mcp.devices
    ]
    provisional = agent._exact_sensitive_targets(
        {"device_names": ["Freezer"], "command": "off"},
        candidate, preview_only=True,
    )
    assert provisional is None


@pytest.mark.asyncio
async def test_compact_identity_without_switch_capability_cannot_stage_approval():
    class NoCapabilities(CountingManifestMCP):
        def peek_device_identities(self):
            return [
                {k: v for k, v in d.items()
                 if k not in {"commands", "capabilities"}}
                for d in self.devices
            ]
        async def get_cached_devices(self, refresh=False):
            self.refresh_args.append(bool(refresh))
            return self.peek_device_identities()

    mcp = NoCapabilities()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ScriptedAI())
    outcome = await agent.process_user_request_result(
        "turn off Freezer", session_id="missing-evidence",
    )
    assert not outcome.confirmation_required
    assert "Nothing was sent" in outcome.message
    assert not switch_writes(mcp)


def test_confirmation_outcome_not_reported_as_success():
    assert classify_completed_request({"confirmation_queued": 1}) == "needs_input"
    assert classify_completed_request({
        "confirmation_queued": 1, "mutation_verification_failures": 1,
    }) == "failed"
    assert classify_completed_request({}) == "success"

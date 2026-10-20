"""v0.18.46: prohibitions in read-only investigations grant no write authority."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import (  # noqa: E402
    _explicit_mutation_request,
    UNVERIFIED_MUTATION_REFUSAL,
)
from tool_registry import device_resolver_tool  # noqa: E402


LIVE_READ_ONLY_PROMPT = (
    "Investigate TV device 4221 and Google TV device 6923. "
    "Verify their exact identities, capabilities, commands and current states. "
    "Determine whether TV power consumption can reliably distinguish active "
    "viewing from standby. Identify the authoritative Internet control for "
    "Google TV and its actual block/unblock commands. Recommend a persistent "
    "cumulative 60-minute usage controller that resets on manual unblocking. "
    "Do not create rules or change device states."
)


@pytest.mark.parametrize("prompt", [
    LIVE_READ_ONLY_PROMPT,
    "Investigate the TV power usage. Do not create rules or change settings.",
    "Review Google TV access and do not block Internet access.",
    "Explain how to turn off the TV. Do not turn it off.",
    "Verify the configuration. Do not change it or restart the hub.",
    "Compare two automations; never disable either app.",
    "Check Internet-room switches and do not create or change rules.",
])
def test_explicit_prohibitions_are_not_mutation_requests(prompt):
    assert _explicit_mutation_request(prompt) is False, prompt


@pytest.mark.parametrize("prompt", [
    "Investigate the TV, and block Google TV now.",
    "Review Google TV. Then block its Internet access.",
    "Investigate TV settings. Do not create rules; instead block the TV.",
    "Do not alter the socket, but block Internet access for Google TV.",
    "Check the TV and change its device setting.",
    "Investigate why TV changed state. Please block Internet now.",
    "Block Google TV now.",
])
def test_independent_positive_write_still_requires_mutation_authority(prompt):
    assert _explicit_mutation_request(prompt) is True, prompt


def test_internet_resolver_guidance_never_requires_fictional_command():
    description = device_resolver_tool().description
    assert "Internet room" in description
    assert "off=blocked, on=allowed" in description
    assert "do NOT assume" in description
    assert "blockInternet/allowInternet" in description
    assert "TV power plug" in description


@pytest.mark.asyncio
async def test_read_only_observation_survives_unverified_write_guard(monkeypatch):
    """Exercise production result classification and final-answer safeguard."""
    from homebrain_agent import UnifiedMCPAgent

    class FakeMCP:
        pass

    agent = UnifiedMCPAgent(FakeMCP(), "unused")
    async def read_only_process(self, prompt, conversation_history=None, *, session_id="default"):
        self.evidence.record(
            "hub_read_devices",
            {"tool": "hub_get_device", "args": {"deviceId": "4221"}},
            success=True,
            elapsed_ms=1,
            summary="TV ID verified",
            supports_live_claim=True,
        )
        return "TV 4221 was identified; active-viewing threshold remains unverified."

    monkeypatch.setattr(agent.__class__, "_process_user_request", read_only_process)
    outcome = await agent.process_user_request_result(LIVE_READ_ONLY_PROMPT)
    assert outcome.request_class == "live-read"
    assert outcome.message != UNVERIFIED_MUTATION_REFUSAL
    assert "threshold remains unverified" in outcome.message
    assert outcome.evidence
    assert all(not row.get("mutates") for row in outcome.evidence)

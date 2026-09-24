from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_subject_prefetch import causal_switch_subject_phrase  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402


def _device(
    device_id: str,
    label: str,
    room: str,
    capabilities: list[str],
) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "capabilities": list(capabilities),
        "attributes": {"switch": "off"} if "Switch" in capabilities else {},
        "commands": ["on", "off"] if "Switch" in capabilities else [],
    }


HALLWAY_1 = _device(
    "7829",
    "Hallway Light 1",
    "Hallway",
    ["Switch", "Light"],
)
HALLWAY_2 = _device(
    "7830",
    "Hallway Light 2",
    "Hallway",
    ["Switch", "Light"],
)
KITCHEN = _device(
    "7831",
    "Kitchen Light",
    "Kitchen",
    ["Switch", "Light"],
)
HALLWAY_METER = _device(
    "7832",
    "Hallway Meter",
    "Hallway",
    ["TemperatureMeasurement"],
)


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError(
            "causal room-group clarification must not call the provider"
        )

    async def aclose(self) -> None:
        return None


class _IdentityOnlyMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.identities = [
            dict(HALLWAY_1),
            dict(HALLWAY_2),
            dict(KITCHEN),
            dict(HALLWAY_METER),
        ]

    def peek_device_identities(self):
        return [dict(item) for item in self.identities]

    async def get_device_identities(self):
        return [dict(item) for item in self.identities]

    async def list_tools(self):
        return []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        raise AssertionError(
            ("zero-model group clarification must not call MCP", name, arguments)
        )


def test_causal_switch_subject_phrase_is_narrow_and_explicit() -> None:
    assert causal_switch_subject_phrase(
        "why did hallway lights turn on?"
    ) == "hallway lights"
    assert causal_switch_subject_phrase(
        "Why did Bedroom 1 lights turn themselves on?"
    ) is None
    assert causal_switch_subject_phrase(
        "why did hallway lights come on?"
    ) == "hallway lights"
    assert causal_switch_subject_phrase(
        "what happened to hallway lights?"
    ) is None


@pytest.mark.asyncio
async def test_initial_causal_room_group_clarifies_without_model_or_mcp() -> None:
    mcp = _IdentityOnlyMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "why did hallway lights turn on?",
        session_id="hallway-zero-model",
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert mcp.calls == []
    assert counters.get("model_rounds", 0) == 0
    assert counters.get("tool_calls", 0) == 0
    assert counters["causal_group_clarification"] == 1
    assert counters["device_resolution_ambiguous"] == 1
    assert counters["identity_cache_hit"] == 1

    assert outcome.request_class == "live-read"
    assert outcome.choices == ["Hallway Light 1", "Hallway Light 2"]
    assert outcome.message == (
        "I could not resolve **hallway lights** uniquely. Possible matches: "
        "Hallway Light 1 or Hallway Light 2."
    )

    assert agent._clarification_choices["hallway-zero-model"] == [
        "Hallway Light 1",
        "Hallway Light 2",
    ]
    assert agent._clarification_objectives["hallway-zero-model"] == (
        "why did hallway lights turn on?"
    )

    assert len(outcome.evidence) == 1
    receipt = outcome.evidence[0]
    assert receipt["tool"] == "homebrain_resolve_device"
    assert receipt["success"] is True
    assert receipt["supports_live_claim"] is False
    assert receipt["evidence_kind"] == "deterministic_targeted_device_resolution"
    assert receipt["arguments"] == {"name": "hallway lights"}
    assert receipt["details"]["alternatives"] == [
        "Hallway Light 1",
        "Hallway Light 2",
    ]
    assert receipt["details"]["attempts"] == [{
        "source": "authoritative_identity_room_kind",
        "count": 2,
    }]


@pytest.mark.asyncio
async def test_exact_causal_device_is_not_intercepted_as_group() -> None:
    mcp = _IdentityOnlyMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent._causal_group_clarification_outcome(
        "Why did Hallway Light 1 turn on?",
        session_key="exact-device",
    )

    assert outcome is None
    assert ai.requests == []
    assert mcp.calls == []

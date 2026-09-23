from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_agent_orchestrator import _device_inventory_arguments  # noqa: E402


class _ScopedInventoryMCP:
    def __init__(self, devices: list[dict]) -> None:
        self.devices = [dict(item) for item in devices]
        self.identity_reads = 0
        self.tool_calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return []

    async def get_device_identities(self):
        self.identity_reads += 1
        return [dict(item) for item in self.devices]

    async def call_tool(self, name: str, arguments: dict):
        self.tool_calls.append((name, arguments))
        raise AssertionError("scoped inventory must not call remote Hubitat list pagination")


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("provider must not be called for scoped inventory")

    async def aclose(self) -> None:
        return None


DEVICES = [
    {"id": "1", "label": "Bathroom Light", "room": "Bathroom"},
    {"id": "2", "label": "Bathroom Motion", "room": "Bathroom"},
    {"id": "3", "label": "Bedroom Meter", "room": "Bedroom 1"},
    {"id": "4", "label": "Bedroom 2 Light", "room": "Bedroom 2"},
    {"id": "5", "label": "Livingroom Light 1", "room": "Living Room"},
    {"id": "6", "label": "Hub Info (C8 Pro)"},
]


def _agent(devices: list[dict] | None = None):
    mcp = _ScopedInventoryMCP(devices or DEVICES)
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )
    return agent, mcp, ai


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        (
            "list Bathroom devices",
            "2 devices in **Bathroom**: Bathroom Light, Bathroom Motion.",
        ),
        (
            "list devices in Bedroom 1",
            "1 device in **Bedroom 1**: Bedroom Meter.",
        ),
        (
            "show living devices",
            "1 device in **Living Room**: Livingroom Light 1.",
        ),
        (
            "list unassigned devices",
            "1 device in **Unassigned**: Hub Info (C8 Pro).",
        ),
    ],
)
async def test_scoped_inventory_returns_only_requested_group_without_model(
    prompt: str,
    expected: str,
) -> None:
    agent, mcp, ai = _agent()

    outcome = await agent.process_user_request_result(prompt)

    assert outcome.message == expected
    assert ai.requests == []
    assert mcp.tool_calls == []
    assert mcp.identity_reads == 1
    assert outcome.metrics["counters"].get("model_rounds", 0) == 0
    assert outcome.metrics["counters"]["tool_calls"] == 1


@pytest.mark.asyncio
async def test_ambiguous_inventory_group_lists_choices_instead_of_guessing() -> None:
    agent, mcp, ai = _agent()

    outcome = await agent.process_user_request_result("list bedroom devices")

    assert outcome.message.startswith(
        "More than one device group matches **bedroom**: "
    )
    assert "Bedroom 1 (1)" in outcome.message
    assert "Bedroom 2 (1)" in outcome.message
    assert "list Bedroom 1 devices" in outcome.message
    assert ai.requests == []
    assert mcp.tool_calls == []
    assert mcp.identity_reads == 1
    assert outcome.metrics["counters"].get("model_rounds", 0) == 0


@pytest.mark.asyncio
async def test_unknown_inventory_group_shows_available_group_counts() -> None:
    agent, mcp, ai = _agent()

    outcome = await agent.process_user_request_result("list Garage devices")

    assert outcome.message.startswith("No device group matched **Garage**.")
    assert "Bathroom 2" in outcome.message
    assert "Bedroom 1 1" in outcome.message
    assert "Unassigned 1" in outcome.message
    assert ai.requests == []
    assert mcp.tool_calls == []
    assert mcp.identity_reads == 1


@pytest.mark.parametrize(
    "prompt",
    [
        "show active devices",
        "list offline devices",
        "show open devices",
        "list motion devices",
        "show light devices",
        "list low battery devices",
    ],
)
def test_live_state_or_device_kind_requests_are_not_stolen_by_inventory_fastpath(
    prompt: str,
) -> None:
    assert _device_inventory_arguments(prompt) is None


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("list devices", {}),
        ("show all devices", {}),
        ("device inventory", {}),
        ("list Bathroom devices", {"group": "Bathroom"}),
        ("list devices in Living Room", {"group": "Living Room"}),
    ],
)
def test_inventory_prompt_parser_returns_compact_or_scoped_arguments(
    prompt: str,
    expected: dict,
) -> None:
    assert _device_inventory_arguments(prompt) == expected

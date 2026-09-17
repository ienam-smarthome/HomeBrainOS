from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_claim_grounding import (  # noqa: E402
    DEVICE_CLAIM_REFUSAL,
    DEVICE_CLAIM_RETRY_INSTRUCTION,
)
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class SequencedAI:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = iter(responses)
        self.requests: list[dict[str, object]] = []

    async def post(self, _url: str, **kwargs: object) -> FakeResponse:
        self.requests.append(dict(kwargs))
        return FakeResponse(next(self._responses))

    async def aclose(self) -> None:
        return None


class TwoDeviceMCP:
    """Two known devices; the model reads Kitchen Light's live attribute
    but the answer below names Front Door instead -- the mismatch this
    module exists to catch."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.full_manifest_reads = 0

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool(
                "hub_get_device_attribute",
                "Read one device attribute",
                {"type": "object"},
                annotations={"readOnlyHint": True},
            ),
        ]

    def peek_cached_devices(self) -> list[dict[str, object]]:
        return [
            {"id": "42", "label": "Kitchen Light"},
            {"id": "77", "label": "Front Door"},
        ]

    async def get_cached_devices(self) -> list[dict[str, object]]:
        self.full_manifest_reads += 1
        raise AssertionError("final claim grounding must not refresh the full manifest")

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(
                name, arguments, {}, "",
                {"results": [{
                    "tool": "hub_get_device_attribute",
                    "gateway": "hub_get_device_attribute",
                }]},
            )
        if name == "hub_get_device_attribute":
            return MCPToolResult(
                name, arguments, {}, "",
                {"deviceId": "42", "attribute": "switch", "value": "on"},
            )
        raise AssertionError((name, arguments))


def _tool_call_message() -> dict[str, object]:
    return {
        "role": "assistant",
        "tool_calls": [{"function": {
            "name": "hub_get_device_attribute",
            "arguments": {"deviceId": "42", "attribute": "switch"},
        }}],
    }


@pytest.mark.asyncio
async def test_answer_naming_a_different_device_than_the_evidence_is_retried_once() -> None:
    mcp = TwoDeviceMCP()
    ai = SequencedAI([
        {"message": _tool_call_message()},
        {"message": {"role": "assistant", "content": "The Front Door is locked."}},
        {"message": {"role": "assistant", "content": "The Kitchen Light is on."}},
    ])
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai, require_sensitive_confirmation=False
    )

    outcome = await agent.process_user_request_result("Is the kitchen light on?")

    assert outcome.message == "The Kitchen Light is on."
    assert len(ai.requests) == 3
    assert mcp.full_manifest_reads == 0
    retry_content = ai.requests[2]["json"]["messages"][-1]["content"]
    assert retry_content == DEVICE_CLAIM_RETRY_INSTRUCTION.format(label="Front Door")


@pytest.mark.asyncio
async def test_repeated_wrong_device_claim_is_refused_after_one_retry() -> None:
    mcp = TwoDeviceMCP()
    ai = SequencedAI([
        {"message": _tool_call_message()},
        {"message": {"role": "assistant", "content": "The Front Door is locked."}},
        {"message": {"role": "assistant", "content": "The Front Door is locked."}},
    ])
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai, require_sensitive_confirmation=False
    )

    outcome = await agent.process_user_request_result("Is the kitchen light on?")

    assert outcome.message == DEVICE_CLAIM_REFUSAL.format(label="Front Door")
    assert len(ai.requests) == 3
    assert mcp.full_manifest_reads == 0


@pytest.mark.asyncio
async def test_answer_naming_the_evidenced_device_is_accepted_immediately() -> None:
    mcp = TwoDeviceMCP()
    ai = SequencedAI([
        {"message": _tool_call_message()},
        {"message": {"role": "assistant", "content": "The Kitchen Light is on."}},
    ])
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai, require_sensitive_confirmation=False
    )

    outcome = await agent.process_user_request_result("Is the kitchen light on?")

    assert outcome.message == "The Kitchen Light is on."
    assert len(ai.requests) == 2
    assert mcp.full_manifest_reads == 0


@pytest.mark.asyncio
async def test_answer_naming_no_device_at_all_is_unaffected() -> None:
    mcp = TwoDeviceMCP()
    ai = SequencedAI([
        {"message": _tool_call_message()},
        {"message": {"role": "assistant", "content": "It is currently on."}},
    ])
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai, require_sensitive_confirmation=False
    )

    outcome = await agent.process_user_request_result("Is the kitchen light on?")

    assert outcome.message == "It is currently on."
    assert len(ai.requests) == 2
    assert mcp.full_manifest_reads == 0


class HistoryIdentityMCP:
    """History result carries the only device label; no full cache exists."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.full_manifest_reads = 0

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("homebrain_device_history", "History", {"type": "object"}),
        ]

    def peek_cached_devices(self) -> list[dict[str, object]]:
        return []

    async def get_cached_devices(self) -> list[dict[str, object]]:
        self.full_manifest_reads += 1
        raise AssertionError("history synthesis must not load the full device manifest")

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(name, arguments, {}, "", {"results": []})
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_history_synthesis_uses_tool_result_identity_without_manifest_refresh() -> None:
    mcp = HistoryIdentityMCP()
    ai = SequencedAI([
        {"message": {
            "role": "assistant",
            "tool_calls": [{"function": {
                "name": "homebrain_device_history",
                "arguments": {"name": "big lamp", "attribute": "switch", "hours_back": 24},
            }}],
        }},
        {"message": {
            "role": "assistant",
            "content": "The Big lamp was on for 4 hours and 29 minutes.",
        }},
    ])
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai, require_sensitive_confirmation=False
    )

    async def history(_arguments: dict[str, object]) -> MCPToolResult:
        data = {
            "success": True,
            "deviceId": "7827",
            "label": "Big lamp",
            "attribute": "switch",
            "count": 2,
            "events": [],
            "temporalAnalysis": {
                "totalActiveDuration": "4h 29m",
                "intervalCount": 5,
                "coverage": "complete",
                "totalIsLowerBound": False,
            },
        }
        return MCPToolResult("homebrain_device_history", _arguments, {}, "", data)

    agent.executor.local_handlers["homebrain_device_history"] = history
    outcome = await agent.process_user_request_result(
        "How long was big lamp on last night?"
    )

    assert outcome.message == "The Big lamp was on for 4 hours and 29 minutes."
    assert len(ai.requests) == 2
    assert mcp.full_manifest_reads == 0

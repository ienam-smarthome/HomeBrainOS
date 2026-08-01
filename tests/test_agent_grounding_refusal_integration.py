from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from grounding_policy import EVIDENCE_REFUSAL, LOG_REFUSAL  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeResponse:
    def __init__(self, message: dict[str, object]) -> None:
        self._payload = {"message": message}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class SequencedAI:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self._messages = iter(messages)
        self.requests: list[dict[str, object]] = []

    async def post(self, _url: str, **kwargs: object) -> FakeResponse:
        self.requests.append(dict(kwargs))
        return FakeResponse(next(self._messages))

    async def aclose(self) -> None:
        return None


class DiscoveryOnlyMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                "hub_search_tools",
                "Search the Hubitat capability catalogue",
                {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
                annotations={"readOnlyHint": True},
            )
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
    ) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_search_tools"
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={"query": arguments.get("query"), "results": []},
        )

    async def get_cached_devices(self) -> list[dict[str, object]]:
        return []


@pytest.mark.asyncio
async def test_live_read_retries_model_once_then_returns_hard_evidence_refusal() -> None:
    mcp = DiscoveryOnlyMCP()
    ai = SequencedAI(
        [
            {"role": "assistant", "content": "Everything is operating normally."},
            {"role": "assistant", "content": "Everything is operating normally."},
        ]
    )
    agent = UnifiedMCPAgent(
        mcp,
        "test-key",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result("What is the current hub status?")

    assert outcome.message == EVIDENCE_REFUSAL
    assert outcome.request_class == "live-read"
    assert outcome.evidence == []
    assert len(ai.requests) == 2
    second_messages = ai.requests[1]["json"]["messages"]
    assert second_messages[-1]["role"] == "user"
    assert "authoritative live MCP evidence" in second_messages[-1]["content"]


@pytest.mark.asyncio
async def test_log_request_retries_once_then_refuses_despite_unrelated_claims() -> None:
    mcp = DiscoveryOnlyMCP()
    ai = SequencedAI(
        [
            {"role": "assistant", "content": "No issues were found in the logs."},
            {"role": "assistant", "content": "No issues were found in the logs."},
        ]
    )
    agent = UnifiedMCPAgent(
        mcp,
        "test-key",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result("Show recent hub logs")

    assert outcome.message == LOG_REFUSAL
    assert outcome.request_class == "live-read"
    assert outcome.evidence == []
    assert len(ai.requests) == 2
    second_messages = ai.requests[1]["json"]["messages"]
    assert second_messages[-1]["role"] == "user"
    assert "authoritative Hubitat log tool" in second_messages[-1]["content"]

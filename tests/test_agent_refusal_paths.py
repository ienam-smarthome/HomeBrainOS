from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool  # noqa: E402


class Response:
    def __init__(self, content: str) -> None:
        self._payload = {"message": {"role": "assistant", "content": content}}

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class AI:
    def __init__(self, *contents: str) -> None:
        self._contents = iter(contents)
        self.requests = []

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return Response(next(self._contents))

    async def aclose(self):
        return None


class ReadMCP:
    def __init__(self, tools: list[MCPTool]) -> None:
        self.tools = tools
        self.calls = []

    async def list_tools(self):
        return list(self.tools)

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        raise AssertionError("the model did not request a tool in this refusal test")


@pytest.mark.asyncio
async def test_evidence_retry_refuses_after_exactly_one_retry():
    ai = AI("The hub seems fine.", "It still seems fine.")
    mcp = ReadMCP([MCPTool("hub_get_info", "info", {"type": "object"})])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Check hub status")

    assert outcome.request_class == "live-read"
    assert outcome.evidence == []
    assert len(ai.requests) == 2
    assert mcp.calls == []
    assert outcome.message == (
        "I could not retrieve verified live Hubitat evidence, so I will "
        "not provide an inferred answer."
    )
    retry_prompt = ai.requests[1][1]["json"]["messages"][-1]["content"]
    assert "No successful live evidence receipt exists yet" in retry_prompt
    assert "Tool discovery alone is not evidence" in retry_prompt


@pytest.mark.asyncio
async def test_log_retry_refuses_after_exactly_one_retry():
    ai = AI("No errors found.", "The logs are clear.")
    mcp = ReadMCP([
        MCPTool("hub_read_diagnostics", "diagnostics", {"type": "object"}),
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Check the Hubitat logs for errors")

    assert outcome.request_class == "live-read"
    assert outcome.evidence == []
    assert len(ai.requests) == 2
    assert mcp.calls == []
    assert outcome.message == (
        "I could not retrieve the actual Hubitat logs, so I will not "
        "provide an inferred log summary."
    )
    retry_prompt = ai.requests[1][1]["json"]["messages"][-1]["content"]
    assert "Fetch the actual logs now" in retry_prompt
    assert "tool='hub_get_logs'" in retry_prompt

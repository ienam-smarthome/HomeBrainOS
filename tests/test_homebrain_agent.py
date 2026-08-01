from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent as BaseUnifiedMCPAgent  # noqa: E402


class FakeMCP:
    pass


class FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"message": {"role": "assistant", "content": self._content}}


class FakeAI:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[dict[str, object]] = []

    async def post(self, _url: str, **kwargs: object) -> FakeResponse:
        self.requests.append(dict(kwargs))
        return FakeResponse(self.content)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_production_agent_delegates_final_answer_to_coordinator() -> None:
    ai = FakeAI("Final grounded answer.")
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=ai)

    answer = await agent._final_answer([
        {"role": "user", "content": "Original request"},
        {"role": "tool", "tool_name": "read", "content": "evidence"},
    ])

    assert isinstance(agent, BaseUnifiedMCPAgent)
    assert isinstance(agent.final_answers, FinalAnswerCoordinator)
    assert answer == "Final grounded answer."
    payload = ai.requests[0]["json"]
    # ChatTransport serialises an empty declared-tool list as JSON null. This is
    # the established provider contract for a final round with no callable tools.
    assert payload["tools"] is None
    assert payload["messages"][-1]["role"] == "user"
    assert "using only the MCP results already provided" in payload["messages"][-1]["content"]


def test_runtime_app_imports_coordinated_agent() -> None:
    source = (APP_DIR / "app.py").read_text(encoding="utf-8")

    assert "from homebrain_agent import UnifiedMCPAgent" in source
    assert "from mcp_agent_orchestrator import UnifiedMCPAgent" not in source

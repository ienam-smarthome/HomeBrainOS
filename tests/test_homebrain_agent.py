from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import homebrain_agent  # noqa: E402
from evidence_recorder import EvidenceRecorder  # noqa: E402
from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from grounding_policy import GroundingPolicy  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from live_evidence_authority import LiveEvidenceAuthority  # noqa: E402
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


def test_production_context_selects_live_evidence_authority() -> None:
    recorder = EvidenceRecorder()
    token = homebrain_agent._CURRENT_EVIDENCE_RECORDER.set(recorder)
    try:
        adapter = homebrain_agent._ProductionGroundingAuthority(
            logs_requested=False,
            conversational=False,
        )
    finally:
        homebrain_agent._CURRENT_EVIDENCE_RECORDER.reset(token)

    assert isinstance(adapter._delegate, LiveEvidenceAuthority)
    assert adapter._delegate.recorder is recorder


def test_base_agent_context_retains_original_grounding_policy() -> None:
    adapter = homebrain_agent._ProductionGroundingAuthority(
        logs_requested=False,
        conversational=False,
    )

    assert isinstance(adapter._delegate, GroundingPolicy)


def test_authority_adapter_ignores_stale_external_evidence_flag() -> None:
    recorder = EvidenceRecorder()
    receipt_token = recorder.begin()
    context_token = homebrain_agent._CURRENT_EVIDENCE_RECORDER.set(recorder)
    try:
        recorder.record(
            "hub_read_devices",
            {"tool": "hub_list_devices"},
            success=True,
            elapsed_ms=1,
            summary="live devices",
        )
        adapter = homebrain_agent._ProductionGroundingAuthority(
            logs_requested=False,
            conversational=False,
        )
        decision = adapter.decide_no_tool_calls(has_live_evidence=False)
    finally:
        homebrain_agent._CURRENT_EVIDENCE_RECORDER.reset(context_token)
        recorder.reset(receipt_token)

    assert decision.action.value == "accept"


def test_runtime_app_imports_coordinated_agent() -> None:
    source = (APP_DIR / "app.py").read_text(encoding="utf-8")

    assert "from homebrain_agent import UnifiedMCPAgent" in source
    assert "from mcp_agent_orchestrator import UnifiedMCPAgent" not in source

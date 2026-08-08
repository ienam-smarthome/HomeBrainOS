from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import homebrain_agent  # noqa: E402
import mcp_agent_orchestrator as orchestrator  # noqa: E402
from evidence_recorder import EvidenceRecorder  # noqa: E402
from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from grounding_policy import (  # noqa: E402
    GroundingPolicy,
    reset_grounding_policy_factory,
    set_grounding_policy_factory,
)
from homebrain_agent import ObservedAgentOutcome, UnifiedMCPAgent  # noqa: E402
from live_evidence_authority import LiveEvidenceAuthority  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from mcp_agent_orchestrator import AgentOutcome  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent as BaseUnifiedMCPAgent  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


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
    assert isinstance(agent.request_metrics, RequestMetrics)
    assert answer == "Final grounded answer."
    payload = ai.requests[0]["json"]
    assert payload["tools"] is None
    assert payload["messages"][-1]["role"] == "user"
    assert "using only the MCP results already provided" in payload["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_chat_records_model_round_and_provider_timing() -> None:
    ai = FakeAI("Measured answer.")
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=ai)
    token = agent.request_metrics.begin()
    try:
        response = await agent._chat([{"role": "user", "content": "hello"}], [])
        metrics = agent.request_metrics.finish("success")
    finally:
        agent.request_metrics.reset(token)

    assert response["content"] == "Measured answer."
    assert metrics["counters"]["model_rounds"] == 1
    assert metrics["timings_ms"]["provider"] >= 0
    assert metrics["timings_ms"]["total"] >= 0


@pytest.mark.asyncio
async def test_process_result_returns_privacy_safe_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_base_result(*_args: object, **_kwargs: object) -> AgentOutcome:
        return AgentOutcome(
            message="Done",
            request_class="live-read",
            evidence=[{"tool": "hub_read_devices"}],
            choices=[],
            confirmation_required=True,
            confirmation_count=1,
        )

    monkeypatch.setattr(
        BaseUnifiedMCPAgent,
        "process_user_request_result",
        fake_base_result,
    )
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result("private device wording")

    assert isinstance(outcome, ObservedAgentOutcome)
    assert outcome.message == "Done"
    assert outcome.metrics["outcome"] == "success"
    assert outcome.metrics["counters"]["tool_calls"] == 1
    assert outcome.metrics["counters"]["confirmation_queued"] == 1
    assert "private device wording" not in repr(outcome.metrics)


@pytest.mark.asyncio
async def test_scheduled_control_request_skips_instant_fast_path_and_reaches_base_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for the dispatch-order bug: a prompt carrying an "at
    <time>" clause must not be executed immediately by the instant routine-
    control fast path. It has to reach base_process() so RuleAuthoringService
    gets a chance to turn it into a real (recurring or one-time) Rule
    Machine proposal instead of either running the command right now or
    handing DeviceControlService a mangled device name.
    """

    control_calls: list[dict[str, object]] = []

    async def fake_control_devices(_self: object, arguments: dict[str, object]):
        control_calls.append(arguments)
        raise AssertionError("instant control fast path must not run for a scheduled request")

    base_calls: list[str] = []

    async def fake_base_result(_self: object, prompt: str, *_args: object, **_kwargs: object) -> AgentOutcome:
        base_calls.append(prompt)
        return AgentOutcome(message="handed to base agent", request_class="write", evidence=[], choices=[])

    monkeypatch.setattr(UnifiedMCPAgent, "_control_devices", fake_control_devices)
    monkeypatch.setattr(
        BaseUnifiedMCPAgent,
        "process_user_request_result",
        fake_base_result,
    )
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result("turn on livingroom light 1 at 10:05am")

    assert control_calls == []
    assert base_calls == ["turn on livingroom light 1 at 10:05am"]
    assert outcome.message == "handed to base agent"


@pytest.mark.asyncio
async def test_immediate_control_request_still_uses_instant_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare control command with no time clause is unaffected by the
    dispatch-order fix and keeps using the instant path -- this pins that
    down so a future change to the AT_TIME gate can't silently slow down
    or reroute ordinary immediate commands.
    """

    control_calls: list[dict[str, object]] = []

    async def fake_control_devices(_self: object, arguments: dict[str, object]) -> MCPToolResult:
        control_calls.append(arguments)
        return MCPToolResult(
            "homebrain_control_devices", arguments, {}, "", {"success": True}
        )

    base_calls: list[str] = []

    async def fake_base_result(_self: object, prompt: str, *_args: object, **_kwargs: object) -> AgentOutcome:
        base_calls.append(prompt)
        return AgentOutcome(message="should not be reached", request_class="write", evidence=[], choices=[])

    monkeypatch.setattr(UnifiedMCPAgent, "_control_devices", fake_control_devices)
    monkeypatch.setattr(
        BaseUnifiedMCPAgent,
        "process_user_request_result",
        fake_base_result,
    )
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))

    await agent.process_user_request_result("turn on livingroom light 1")

    assert len(control_calls) == 1
    assert base_calls == []


def test_production_factory_selects_live_evidence_authority() -> None:
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))
    token = set_grounding_policy_factory(agent._create_grounding_policy)
    try:
        policy = GroundingPolicy(
            logs_requested=False,
            conversational=False,
        )
    finally:
        reset_grounding_policy_factory(token)

    assert isinstance(policy, LiveEvidenceAuthority)
    assert policy.recorder is agent.evidence


def test_base_agent_context_retains_original_grounding_policy() -> None:
    policy = GroundingPolicy(
        logs_requested=False,
        conversational=False,
    )

    assert type(policy) is GroundingPolicy
    assert orchestrator.GroundingPolicy is GroundingPolicy


def test_live_authority_ignores_stale_external_evidence_flag() -> None:
    recorder = EvidenceRecorder()
    receipt_token = recorder.begin()
    try:
        recorder.record(
            "hub_read_devices",
            {"tool": "hub_list_devices"},
            success=True,
            elapsed_ms=1,
            summary="live devices",
        )
        authority = LiveEvidenceAuthority(
            recorder,
            logs_requested=False,
            conversational=False,
        )
        decision = authority.decide_no_tool_calls(has_live_evidence=False)
    finally:
        recorder.reset(receipt_token)

    assert decision.action.value == "accept"


@pytest.mark.asyncio
async def test_grounding_factory_is_context_local_between_tasks() -> None:
    first = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))
    second = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))

    async def select(agent: UnifiedMCPAgent) -> object:
        token = set_grounding_policy_factory(agent._create_grounding_policy)
        try:
            await asyncio.sleep(0)
            return GroundingPolicy(
                logs_requested=False,
                conversational=False,
            )
        finally:
            reset_grounding_policy_factory(token)

    first_policy, second_policy = await asyncio.gather(
        select(first),
        select(second),
    )

    assert isinstance(first_policy, LiveEvidenceAuthority)
    assert isinstance(second_policy, LiveEvidenceAuthority)
    assert first_policy.recorder is first.evidence
    assert second_policy.recorder is second.evidence
    assert orchestrator.GroundingPolicy is GroundingPolicy


def test_runtime_app_imports_coordinated_agent() -> None:
    source = (APP_DIR / "app.py").read_text(encoding="utf-8")

    assert "from homebrain_agent import UnifiedMCPAgent" in source
    assert "from mcp_agent_orchestrator import UnifiedMCPAgent" not in source


class DeviceMCP:
    """Minimal MCP fake exposing the hub_list_devices read path used by
    DeviceQueryService, matching the QueryMCP/TargetedMCP fakes already
    used against device_query_service.py directly.
    """

    def __init__(self, devices: list[dict[str, object]]) -> None:
        self.devices = devices
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, arguments: dict[str, object]) -> MCPToolResult:
        self.calls.append((name, arguments))
        return MCPToolResult(name, arguments, {}, "ok", {"devices": self.devices})

    async def get_cached_devices(self) -> list[dict[str, object]]:
        return self.devices


@pytest.mark.asyncio
async def test_bare_attribute_query_never_reaches_model_tool_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for a real live failure: a bare "temperature" query
    used to fall through to the model's tool-selection loop, which could --
    and did -- answer from the outdoor weather device instead of an indoor
    reading, even after 0.10.370's prompt-only steering fix. The
    parse_bare_attribute fast path added afterward must resolve this
    deterministically and never hand the request to the model loop at all.
    Three indoor devices report temperature here, so this also proves the
    request reaches DeviceQueryService.resolve_device's existing
    bare-attribute disambiguation guard (0.10.369) rather than silently
    picking one.
    """

    async def fail_if_reached(_self: object, *_args: object, **_kwargs: object) -> AgentOutcome:
        raise AssertionError(
            "bare attribute query reached the model tool-selection loop"
        )

    monkeypatch.setattr(
        BaseUnifiedMCPAgent, "process_user_request_result", fail_if_reached
    )

    mcp = DeviceMCP([
        {
            "id": "1",
            "label": "Bedroom Meter",
            "room": "Bedroom",
            "capabilities": ["TemperatureMeasurement"],
            "attributes": {"temperature": 24.0},
        },
        {
            "id": "2",
            "label": "Hallway Meter",
            "room": "Hallway",
            "capabilities": ["TemperatureMeasurement"],
            "attributes": {"temperature": 28.5},
        },
        {
            "id": "3",
            "label": "Weather Open-Meteo",
            "room": "Climate",
            "capabilities": ["TemperatureMeasurement"],
            "attributes": {"temperature": 20.0},
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result("temperature")

    assert "Bedroom Meter" in outcome.message
    assert "Hallway Meter" in outcome.message
    assert "Weather Open-Meteo" in outcome.message
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]


@pytest.mark.asyncio
async def test_bare_attribute_query_resolves_single_exact_label_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A device literally labelled "Temperature" must still resolve to
    itself deterministically rather than triggering the multi-reporter
    disambiguation guard -- mirrors
    test_resolve_device_exact_label_match_bypasses_bare_attribute_guard in
    test_device_query_service.py, exercised through the fast path this
    time.
    """

    async def fail_if_reached(_self: object, *_args: object, **_kwargs: object) -> AgentOutcome:
        raise AssertionError(
            "bare attribute query reached the model tool-selection loop"
        )

    monkeypatch.setattr(
        BaseUnifiedMCPAgent, "process_user_request_result", fail_if_reached
    )

    mcp = DeviceMCP([
        {
            "id": "1",
            "label": "Temperature",
            "room": "Office",
            "capabilities": ["TemperatureMeasurement"],
            "attributes": {"temperature": 21.5},
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result("What's the temperature?")

    assert outcome.message == "Temperature temperature is 21.5°C."

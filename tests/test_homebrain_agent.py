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
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
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


@pytest.mark.asyncio
async def test_pronoun_follow_up_reuses_the_just_controlled_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for a live bug report: "turn on Livingroom Light 2"
    succeeded, and the immediate follow-up "turn it off" returned
    "Unresolved" instead of turning off the same device -- routine_control_
    arguments() parses "it" as a literal device_names entry, and nothing
    remembered which device the prior command actually landed on. This pins
    down the fix: a successful single-device control command now records
    its label in the same per-session slot the read-side "what's its
    temperature" follow-up already uses, and a pronoun-only control target
    is substituted from that slot before DeviceControlService ever sees it.
    """

    control_calls: list[dict[str, object]] = []

    async def fake_control_devices(_self: object, arguments: dict[str, object]) -> MCPToolResult:
        control_calls.append(arguments)
        return MCPToolResult(
            "homebrain_control_devices",
            arguments,
            {},
            "",
            {
                "success": True,
                "command": arguments.get("command"),
                "matched": 1,
                "executed": 1,
                "succeeded": [{"id": "42", "label": "Livingroom Light 2", "success": True}],
                "failed": [],
                "complete": True,
            },
        )

    monkeypatch.setattr(UnifiedMCPAgent, "_control_devices", fake_control_devices)
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))

    await agent.process_user_request_result(
        "turn on livingroom light 2", session_id="pronoun-follow-up"
    )
    await agent.process_user_request_result(
        "turn it off", session_id="pronoun-follow-up"
    )

    assert control_calls[0]["device_names"] == ["livingroom light 2"]
    assert control_calls[1]["device_names"] == ["Livingroom Light 2"]
    assert control_calls[1]["command"] == "off"


@pytest.mark.asyncio
async def test_pronoun_follow_up_is_scoped_per_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pronoun follow-up in a session that never controlled a device must
    not borrow another session's last-controlled device -- it should fail
    to resolve exactly as it did before this fix, not silently act on
    someone else's device.
    """

    control_calls: list[dict[str, object]] = []

    async def fake_control_devices(_self: object, arguments: dict[str, object]) -> MCPToolResult:
        control_calls.append(arguments)
        return MCPToolResult(
            "homebrain_control_devices",
            arguments,
            {},
            "",
            {
                "success": True,
                "command": arguments.get("command"),
                "matched": 1,
                "executed": 1,
                "succeeded": [{"id": "42", "label": "Livingroom Light 2", "success": True}],
                "failed": [],
                "complete": True,
            },
        )

    monkeypatch.setattr(UnifiedMCPAgent, "_control_devices", fake_control_devices)
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))

    await agent.process_user_request_result(
        "turn on livingroom light 2", session_id="session-a"
    )
    await agent.process_user_request_result("turn it off", session_id="session-b")

    assert control_calls[1]["device_names"] == ["it"]


@pytest.mark.asyncio
async def test_multi_device_control_does_not_seed_a_pronoun_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A command that controlled more than one device has no single "it" to
    remember -- guessing which one the user meant next would be worse than
    making the follow-up ask again, so this must leave any prior single-
    device context untouched rather than clobbering it with ambiguity.
    """

    async def fake_control_devices(_self: object, arguments: dict[str, object]) -> MCPToolResult:
        return MCPToolResult(
            "homebrain_control_devices",
            arguments,
            {},
            "",
            {
                "success": True,
                "command": arguments.get("command"),
                "matched": 2,
                "executed": 2,
                "succeeded": [
                    {"id": "1", "label": "Hallway Light", "success": True},
                    {"id": "2", "label": "Kitchen Light", "success": True},
                ],
                "failed": [],
                "complete": True,
            },
        )

    monkeypatch.setattr(UnifiedMCPAgent, "_control_devices", fake_control_devices)
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI("unused"))

    await agent.process_user_request_result(
        "turn on hallway light and kitchen light", session_id="multi-device"
    )

    assert agent._selected_devices.get("multi-device") is None


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


class FirmwareMCP:
    """Fake MCP exposing the Hub Info device the firmware scope reads, plus
    the hub_update_firmware tool the confirmed resume path executes.
    Mirrors the shape used by test_hub_info_service.py and
    test_confirmation_enforcement.py's own firmware fakes.
    """

    def __init__(
        self,
        *,
        installed: str = "2.5.1.145",
        available: str = "2.5.1.147",
        firmware_result: dict[str, object] | None = None,
    ) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.installed = installed
        self.available = available
        self.firmware_result = firmware_result if firmware_result is not None else {"success": True}

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool(
                "hub_update_firmware",
                "Install available hub firmware",
                {"type": "object", "properties": {"confirm": {"type": "boolean"}}},
            ),
        ]

    async def get_cached_devices(self) -> list[dict[str, object]]:
        return [{"id": "1089", "label": "Hub Info (C8 Pro)"}]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_manage_devices":
            return MCPToolResult(name, arguments, {}, "ok", {"success": True})
        if name == "hub_update_firmware":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                self.firmware_result,
                is_error=self.firmware_result.get("success") is False,
            )
        if name == "hub_search_tools":
            return MCPToolResult(name, arguments, {}, "", {"matches": []})
        return MCPToolResult(
            name,
            arguments,
            {},
            "",
            {
                "devices": [{
                    "id": "1089",
                    "label": "Hub Info (C8 Pro)",
                    "attributes": {
                        "firmwareVersionString": self.installed,
                        "hubUpdateStatus": (
                            "current" if self.installed == self.available
                            else "available"
                        ),
                        "hubUpdateVersion": self.available,
                    },
                }]
            },
        )


@pytest.mark.asyncio
async def test_firmware_install_intent_queues_confirmation_and_resumes_to_a_real_call() -> None:
    """Regression test for a real live failure: even the explicit request
    "Install the available Hubitat firmware update" only ever called the
    read-only firmware snapshot and narrated a summary -- the system prompt
    trusted the model to chain a second tool call to hub_update_firmware
    after seeing update_available=true, and it never did, so the
    confirmation gate (which only engages once that tool call is actually
    attempted) never fired. The WebUI's "Update hub firmware" button just
    resubmits the same text, so this looped forever.

    parse_firmware_install_intent must route this deterministically to a
    queued confirmation without ever calling the model for the propose
    step (proven by ai.requests staying empty), and "confirm" afterward
    must resume through the *existing* ConfirmedActionCoordinator machinery
    to a real hub_update_firmware call -- proving the synthetic
    assistant_message/actions this fast path builds are structurally
    compatible with the model-driven confirmation path, not just superficially
    similar.

    Follow-up regression: the confirm step itself must also answer
    deterministically now (confirmed_firmware_report), not fall through to
    model narration -- ai.requests must stay empty across *both* steps.
    """

    mcp = FirmwareMCP(installed="2.5.1.145", available="2.5.1.147")
    ai = FakeAI("unused -- deterministic report must not need this")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    propose = await agent.process_user_request_result(
        "Install the available Hubitat firmware update", session_id="firmware-test"
    )

    assert propose.confirmation_required is True
    assert propose.confirmation_count == 1
    assert "confirm" in propose.message.casefold()
    assert "restart" in propose.message.casefold()
    assert ai.requests == []
    assert ("hub_update_firmware", {}) not in mcp.calls

    confirm = await agent.process_user_request_result(
        "confirm", session_id="firmware-test"
    )

    assert confirm.message.startswith("Firmware update initiated.")
    assert mcp.calls[-1] == ("hub_update_firmware", {"confirm": True})
    assert ai.requests == []


@pytest.mark.asyncio
async def test_firmware_confirm_deterministically_reports_a_hub_side_failure() -> None:
    """If the hub reports success=False or a warning on the actual install
    call, that must reach the user verbatim and deterministically -- not
    depend on the model correctly carrying it into a narrated summary,
    which live testing found unreliable for exactly this kind of decision.
    """

    mcp = FirmwareMCP(
        installed="2.5.1.145",
        available="2.5.1.147",
        firmware_result={
            "success": False,
            "message": "Update rejected: a backup is required first.",
        },
    )
    ai = FakeAI("unused -- deterministic report must not need this")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    await agent.process_user_request_result(
        "Install the available Hubitat firmware update", session_id="firmware-fail-test"
    )
    confirm = await agent.process_user_request_result(
        "confirm", session_id="firmware-fail-test"
    )

    assert "did not succeed" in confirm.message
    assert "backup is required first" in confirm.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_firmware_confirm_surfaces_a_hub_warning_alongside_success() -> None:
    """A `warning` field on an otherwise successful install result must be
    surfaced too, not silently dropped.
    """

    mcp = FirmwareMCP(
        installed="2.5.1.145",
        available="2.5.1.147",
        firmware_result={
            "success": True,
            "warning": "A previous backup could not be verified.",
        },
    )
    ai = FakeAI("unused -- deterministic report must not need this")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    await agent.process_user_request_result(
        "Install the available Hubitat firmware update", session_id="firmware-warn-test"
    )
    confirm = await agent.process_user_request_result(
        "confirm", session_id="firmware-warn-test"
    )

    assert confirm.message.startswith("Firmware update initiated.")
    assert "A previous backup could not be verified." in confirm.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_unrelated_fast_path_turn_cancels_a_stale_pending_confirmation() -> None:
    """Live-debugging regression: every deterministic fast path returns
    straight from operation() without ever reaching the base
    orchestrator's ConfirmationStore.consume() -- so a fast path firing on
    an unrelated turn (e.g. a device-control command) used to leave an
    earlier, still-pending confirmation completely untouched instead of
    cancelling it. That meant a LATER, unrelated affirmative reply like
    "yes" could silently resume a stale action the user had long since
    moved on from and may not even remember asking for.

    _resolve_pending_confirmation must give the pending confirmation first
    refusal on every turn: an unrelated fast-path prompt must consume (and
    thereby cancel) it as a side effect, and a later bare "yes" must find
    nothing pending rather than resuming the stale firmware install.
    """

    mcp = FirmwareMCP(installed="2.5.1.145", available="2.5.1.147")
    ai = FakeAI("unused -- must never be reached")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    propose = await agent.process_user_request_result(
        "Install the available Hubitat firmware update", session_id="stale-confirm-test"
    )
    assert propose.confirmation_required is True
    assert agent.confirmations.pending.get("stale-confirm-test") is not None

    # An unrelated fast-path turn in between -- doesn't matter that this
    # particular device can't be resolved against FirmwareMCP's fixture;
    # what matters is that *some* fast path fires on this turn.
    unrelated = await agent.process_user_request_result(
        "turn off the nonexistent lamp", session_id="stale-confirm-test"
    )
    assert unrelated.confirmation_required is False
    assert agent.confirmations.pending.get("stale-confirm-test") is None

    late_yes = await agent.process_user_request_result(
        "yes", session_id="stale-confirm-test"
    )

    assert "No Hubitat action is pending confirmation" in late_yes.message
    assert ("hub_update_firmware", {"confirm": True}) not in mcp.calls
    assert ai.requests == []


@pytest.mark.asyncio
async def test_new_confirmation_does_not_silently_clobber_an_older_pending_one() -> None:
    """Companion regression to the stale-confirmation bug: a fast path
    that queues its OWN confirmation (e.g. _firmware_install_outcome) used
    to be able to silently overwrite a still-pending confirmation from an
    earlier, different request with no notice to the user, because it
    never ran the new consume-or-cancel gate first. Now that gate always
    runs before any fast path, so by the time a second queue() happens,
    the first pending entry has already been explicitly resolved
    (cancelled, in this case, since the intervening prompt wasn't a
    confirm word) rather than being clobbered out from under the user
    without any acknowledgement.
    """

    mcp = FirmwareMCP(installed="2.5.1.145", available="2.5.1.147")
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    first_propose = await agent.process_user_request_result(
        "Install the available Hubitat firmware update", session_id="clobber-test"
    )
    assert first_propose.confirmation_required is True
    first_pending = agent.confirmations.pending.get("clobber-test")
    assert first_pending is not None

    second_propose = await agent.process_user_request_result(
        "Install the available Hubitat firmware update", session_id="clobber-test"
    )

    assert second_propose.confirmation_required is True
    second_pending = agent.confirmations.pending.get("clobber-test")
    assert second_pending is not None
    # The second propose's pending entry replaced the first through the
    # normal queue() path (same request, re-asked) -- confirming it now
    # resumes exactly one firmware install, not two stacked ones.
    confirm = await agent.process_user_request_result("confirm", session_id="clobber-test")
    assert confirm.message.startswith("Firmware update initiated.")
    assert mcp.calls.count(("hub_update_firmware", {"confirm": True})) == 1


@pytest.mark.asyncio
async def test_confirm_word_collision_with_device_clarification_still_reprompts() -> None:
    """"do it" is a recognised CONFIRM_WORD, but it also contains the
    standalone word "it", which the unresolved-choice follow-up detector
    treats as a pronoun reference. When there is a live device
    clarification pending but NO sensitive action is actually queued for
    confirmation, "do it" must still fall through to the ordinary
    choice-follow-up re-prompt instead of being intercepted by the new
    pending-confirmation gate and answered with a confusing "No Hubitat
    action is pending confirmation" message that ignores the clarification
    the user was actually replying to.
    """

    mcp = FirmwareMCP(installed="2.5.1.145", available="2.5.1.147")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))
    agent._clarification_choices["clarify-test"] = ["Bedroom 1 Meter", "Bedroom 1 TRV"]

    outcome = await agent.process_user_request_result("do it", session_id="clarify-test")

    assert "No Hubitat action is pending confirmation" not in outcome.message
    assert "Which device do you mean" in outcome.message


@pytest.mark.asyncio
async def test_firmware_install_intent_reports_up_to_date_without_queuing() -> None:
    """When no update is actually available, the same explicit install
    request must answer deterministically from the snapshot instead of
    queuing a confirmation for nothing.
    """

    mcp = FirmwareMCP(installed="2.5.1.147", available="2.5.1.147")
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Install the available Hubitat firmware update", session_id="firmware-test-2"
    )

    assert outcome.confirmation_required is False
    assert "already the latest version" in outcome.message
    assert ai.requests == []
    assert ("hub_update_firmware", {}) not in mcp.calls


@pytest.mark.asyncio
async def test_read_only_firmware_check_does_not_trigger_install_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"check firmware" must keep going through the ordinary model loop --
    it must never be mistaken for an install directive just because it
    mentions firmware.
    """

    async def fake_base_result(_self: object, prompt: str, *_args: object, **_kwargs: object) -> AgentOutcome:
        return AgentOutcome(
            message="handed to base agent", request_class="live-read", evidence=[], choices=[]
        )

    monkeypatch.setattr(
        BaseUnifiedMCPAgent, "process_user_request_result", fake_base_result
    )
    agent = UnifiedMCPAgent(FirmwareMCP(), "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result("check firmware")

    assert outcome.message == "handed to base agent"
    assert outcome.confirmation_required is False


@pytest.mark.asyncio
async def test_firmware_status_query_reports_in_progress_without_the_model() -> None:
    """"How's the update going?" while installed still trails available must
    answer deterministically -- no model round, no confirmation queued --
    and must not overclaim a download percentage Hubitat doesn't expose.
    """

    mcp = FirmwareMCP(installed="2.5.1.145", available="2.5.1.147")
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "How's the firmware update going?", session_id="firmware-status-test"
    )

    assert outcome.message.startswith("Still in progress")
    assert "2.5.1.145" in outcome.message
    assert "2.5.1.147" in outcome.message
    assert "%" not in outcome.message
    assert outcome.confirmation_required is False
    assert ai.requests == []
    assert ("hub_update_firmware", {}) not in mcp.calls


@pytest.mark.asyncio
async def test_firmware_status_query_reports_up_to_date_when_versions_converge() -> None:
    """Once installed_firmware catches up with available_firmware,
    hub_info_service reports update_available=False -- the same status
    question must then report "up to date" instead of "still in progress"
    (the snapshot data can't distinguish "just finished" from "was never
    pending", so this covers both).
    """

    mcp = FirmwareMCP(installed="2.5.1.147", available="2.5.1.147")
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "update status", session_id="firmware-status-test-2"
    )

    assert outcome.message == (
        "Firmware is up to date -- the hub is running 2.5.1.147. "
        "No update is pending."
    )
    assert ai.requests == []


@pytest.mark.asyncio
async def test_firmware_status_query_does_not_match_install_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A status question must never be mistaken for an install directive
    and trigger a confirmation queue -- it is read-only.
    """

    agent = UnifiedMCPAgent(
        FirmwareMCP(installed="2.5.1.145", available="2.5.1.147"),
        "key",
        ai_client=FakeAI("unused"),
    )

    outcome = await agent.process_user_request_result(
        "Is the firmware update done?", session_id="firmware-status-test-3"
    )

    assert outcome.confirmation_required is False
    assert outcome.confirmation_count == 0


class HubHealthMCP:
    """Fake MCP exposing the same Hub Info device shape as FirmwareMCP
    above, but with the resource-telemetry attributes (unit-tagged, the
    same list-of-dicts shape used by test_hub_info_service.py) that the
    hub health fast path reads instead of the firmware fields.
    """

    def __init__(
        self,
        *,
        db_size: float = 126.0,
        db_unit: str = "MB",
        free_memory: float = 977.4,
        free_memory_unit: str = "MB",
        temperature: object = 47.6,
        temperature_unit: str = "°C",
        uptime: str = "0d 21h 24m",
        # Deliberately typed as `object`, defaulting to the real Hub Info
        # driver's live shape: hubAlerts is reported as the STRING "[]"
        # when empty, not an actual empty list -- see
        # test_hub_health_query_recognises_a_real_alert_reported_as_a_string.
        hub_alerts: object = "[]",
        cpu_percent: float = 22.25,
        # Deliberately typed as `object`, defaulting to the real Hub Info
        # driver's live shape: Hubitat attribute values are transmitted as
        # strings ("true"/"false"), not JSON/Python booleans -- see
        # test_hub_health_query_reports_cpu_percent_and_human_radio_health's
        # docstring for the live regression this default reproduces.
        zigbee_healthy: object = "true",
        zwave_healthy: object = "false",
    ) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.db_size = db_size
        self.db_unit = db_unit
        self.free_memory = free_memory
        self.free_memory_unit = free_memory_unit
        # Deliberately typed as `object`, not `float`: the real Hub Info
        # driver's temperatureC attribute has been observed live reporting
        # its currentValue as a display string with the unit already baked
        # in (e.g. "46.9 °C"), not a bare number -- see
        # test_hub_health_query_does_not_duplicate_a_unit_already_baked_into_the_raw_value.
        self.temperature = temperature
        self.temperature_unit = temperature_unit
        self.uptime = uptime
        self.hub_alerts = hub_alerts
        self.cpu_percent = cpu_percent
        self.zigbee_healthy = zigbee_healthy
        self.zwave_healthy = zwave_healthy

    async def list_tools(self) -> list[MCPTool]:
        return [MCPTool("hub_search_tools", "Search tools", {"type": "object"})]

    async def get_cached_devices(self) -> list[dict[str, object]]:
        return [{"id": "1089", "label": "Hub Info (C8 Pro)"}]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_manage_devices":
            return MCPToolResult(name, arguments, {}, "ok", {"success": True})
        if name == "hub_search_tools":
            return MCPToolResult(name, arguments, {}, "", {"matches": []})
        attributes: list[dict[str, object]] = [
            {
                "name": "freeMemory",
                "currentValue": self.free_memory,
                "unit": self.free_memory_unit,
            },
            {
                "name": "temperatureC",
                "currentValue": self.temperature,
                "unit": self.temperature_unit,
            },
            {
                "name": "dbSize",
                "currentValue": self.db_size,
                "unit": self.db_unit,
            },
            {"name": "formattedUptime", "currentValue": self.uptime},
            {"name": "hubAlerts", "currentValue": self.hub_alerts},
            {"name": "cpuPct", "currentValue": self.cpu_percent},
        ]
        if self.zigbee_healthy is not None:
            attributes.append({"name": "zbHealthy", "currentValue": self.zigbee_healthy})
        if self.zwave_healthy is not None:
            attributes.append({"name": "zwHealthy", "currentValue": self.zwave_healthy})
        return MCPToolResult(
            name,
            arguments,
            {},
            "",
            {
                "devices": [{
                    "id": "1089",
                    "label": "Hub Info (C8 Pro)",
                    "attributes": attributes,
                }]
            },
        )


@pytest.mark.asyncio
async def test_hub_health_query_reports_the_hubs_own_units_without_the_model() -> None:
    """Regression test for a live bug: "check the hub health status" used
    to reach the local model unfiltered, which mislabelled a correctly-
    reported 126 MB database size as "126 KB" in its own free-text prose,
    and fabricated an unrelated "Cloud Backup: Successful" line with no
    corresponding field in the tool result at all. This must now answer
    deterministically from homebrain_hub_info_snapshot's already
    unit-tagged fields, reporting the hub's actual reported unit (MB) and
    never inventing a field the snapshot didn't return.
    """

    mcp = HubHealthMCP(db_size=126.0, db_unit="MB")
    ai = FakeAI("unused -- deterministic report must not need this")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Check the hub health status", session_id="hub-health-test"
    )

    assert "126.0 MB" in outcome.message
    assert "KB" not in outcome.message
    assert "healthy with no active alerts" in outcome.message
    assert "Cloud Backup" not in outcome.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_hub_health_query_surfaces_real_active_alerts() -> None:
    """When the hub itself reports active alerts, they must be surfaced,
    not silently suppressed by a generic "healthy" headline.
    """

    mcp = HubHealthMCP(hub_alerts=["zigbeeRadioOffline"])
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "hub health", session_id="hub-health-test-2"
    )

    assert "1 active alert" in outcome.message
    assert "zigbeeRadioOffline" in outcome.message
    assert "healthy with no active alerts" not in outcome.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_hub_health_query_recognises_a_real_alert_reported_as_a_string() -> None:
    """Regression test for a live bug never actually exercised against a
    real hub: hub_alerts was only ever recognised as a Python list, but
    device_query_service.py's own empty-alerts sentinel check (comparing
    against the literal string "[]") proves the real Hub Info driver
    reports hubAlerts as a STRING, not a list. A genuine active alert
    reported that way must still be surfaced, not silently swallowed as
    "no active alerts" -- both a JSON-array-shaped string and a plain
    text string must work.
    """

    json_shaped = HubHealthMCP(hub_alerts='["zigbeeRadioOffline"]')
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(json_shaped, "key", ai_client=ai)
    outcome = await agent.process_user_request_result(
        "hub health", session_id="hub-health-test-json-alert"
    )
    assert "1 active alert" in outcome.message
    assert "zigbeeRadioOffline" in outcome.message
    assert "healthy with no active alerts" not in outcome.message

    plain_text = HubHealthMCP(hub_alerts="Zigbee radio offline")
    ai2 = FakeAI("unused")
    agent2 = UnifiedMCPAgent(plain_text, "key", ai_client=ai2)
    outcome2 = await agent2.process_user_request_result(
        "hub health", session_id="hub-health-test-text-alert"
    )
    assert "1 active alert" in outcome2.message
    assert "Zigbee radio offline" in outcome2.message
    assert "healthy with no active alerts" not in outcome2.message
    assert ai.requests == []
    assert ai2.requests == []


@pytest.mark.asyncio
async def test_hub_health_query_treats_the_string_empty_sentinel_as_healthy() -> None:
    """The real hub's "no alerts" state is the string "[]", not an empty
    Python list or None -- this must still read as healthy, not as "did
    not report an alert status" (reserved for a genuinely missing field).
    """

    mcp = HubHealthMCP(hub_alerts="[]")
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "hub health", session_id="hub-health-test-empty-string-alert"
    )

    assert "healthy with no active alerts" in outcome.message
    assert "did not report" not in outcome.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_hub_health_query_does_not_duplicate_a_unit_already_baked_into_the_raw_value() -> None:
    """Regression test for a live bug in the 0.10.387 fast path itself:
    "Internal Temperature: 46.9 °C °C". The real Hub Info driver reported
    temperatureC's currentValue as the display string "46.9 °C" (unit
    already included), not a bare number -- appending the separately
    tracked temperature_unit again produced the duplicate. The formatter
    must strip an existing trailing unit before appending it once, however
    the underlying driver happens to report the value.
    """

    mcp = HubHealthMCP(temperature="46.9 °C", temperature_unit="°C")
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Check the hub health status", session_id="hub-health-test-3"
    )

    assert "46.9 °C" in outcome.message
    assert "°C °C" not in outcome.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_hub_health_query_reports_cpu_percent_and_human_radio_health() -> None:
    """CPU load must read as an actual percentage (not a bare number with
    no unit at all), and the zigbee/zwave health flags must render as
    readable words instead of literal "true"/"false".

    Regression test for a live bug that survived the first version of this
    fast path: the real Hub Info driver reports zbHealthy/zwHealthy as the
    literal strings "true"/"false" (Hubitat attribute values are
    transmitted as strings), not a Python/JSON bool -- an
    isinstance(raw, bool) check alone never catches that, so
    HubHealthMCP's default fixture now reproduces the real string shape
    rather than an actual bool.
    """

    mcp = HubHealthMCP(zigbee_healthy="true", zwave_healthy="false")
    ai = FakeAI("unused")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Check the hub health status", session_id="hub-health-test-4"
    )

    assert "22.25%" in outcome.message
    assert "true" not in outcome.message.casefold()
    assert "false" not in outcome.message.casefold()
    assert "Healthy" in outcome.message
    assert "Not healthy" in outcome.message
    assert ai.requests == []


# Real device shapes pulled live from the hub this bug was found against:
# two devices both plausibly named "tv" -- a plain power-switch labelled
# exactly "TV", and a separate network-integration device labelled "Block
# Google-TV-Streamer" that is the only one of the two that actually
# advertises blockInternet/allowInternet.
TV_SWITCH_DEVICE = {
    "id": "4221", "label": "TV", "name": "Innr SP 242 Power Metering SmartPlug",
    "roomName": "Multimedia",
    "commands": [
        "childLock", "initialize", "ledMode", "off", "on", "ping", "refresh",
        "resetEnergy", "setEnergy", "setEnergyPrice", "setPowerOnState", "setSwitchType",
    ],
}
TV_STREAMER_BLOCK_DEVICE = {
    "id": "6923", "label": "Block Google-TV-Streamer", "name": "Cudy Device-192.168.1.108",
    "roomName": "Multimedia",
    "commands": [
        "addTime", "allowInternet", "blockInternet", "off", "on", "refresh",
        "resetUsage", "setDeviceIP", "setDeviceMAC",
    ],
}


class InternetAccessMCP:
    """Fake MCP exposing exactly the two real device shapes above, plus
    hub_call_device_command handling for block/allowInternet.
    """

    def __init__(self, *, converged: bool = True) -> None:
        self.devices = [TV_SWITCH_DEVICE, TV_STREAMER_BLOCK_DEVICE]
        self.converged = converged
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def get_cached_devices(self) -> list[dict[str, object]]:
        return list(self.devices)

    async def call_tool(self, gateway: str, arguments: dict[str, object]) -> MCPToolResult:
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_call_device_command":
            wait_for = (arguments.get("args") or {}).get("waitFor")
            expected = wait_for.get("expectedValue") if isinstance(wait_for, dict) else None
            return MCPToolResult(
                gateway, arguments, {}, "ok",
                {"success": True, "waitFor": {"converged": self.converged, "value": expected}},
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))


@pytest.mark.asyncio
async def test_immediate_block_request_finds_the_capable_device_not_the_switch() -> None:
    """Regression test for a real live failure: "block the tv" was
    resolved and executed as "turn off TV" -- the plain power-switch
    device won ordinary name resolution (exact label match), and there was
    no deterministic immediate path for blockInternet at all, so the
    request reached the model, which interpreted "block" as "turn off".

    This must now resolve to the device that actually advertises
    blockInternet (id 6923, not the switch at 4221), dispatch the real
    command, and never touch the model at all.
    """

    mcp = InternetAccessMCP(converged=True)
    ai = FakeAI("unused -- must never be reached")
    agent = UnifiedMCPAgent(mcp, "key", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "block the tv", session_id="block-tv-test"
    )

    assert outcome.message == "Block Google-TV-Streamer internet access blocked."
    dispatch_calls = [
        args for _, args in mcp.calls if args.get("tool") == "hub_call_device_command"
    ]
    assert len(dispatch_calls) == 1
    assert dispatch_calls[0]["args"]["deviceId"] == "6923"
    assert dispatch_calls[0]["args"]["command"] == "blockInternet"
    assert dispatch_calls[0]["args"]["waitFor"]["expectedValue"] == "blocked"
    assert ai.requests == []


@pytest.mark.asyncio
async def test_immediate_allow_request_targets_the_same_capable_device() -> None:
    mcp = InternetAccessMCP(converged=True)
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result(
        "allow internet for the tv", session_id="allow-tv-test"
    )

    assert outcome.message == "Block Google-TV-Streamer internet access unblocked."
    dispatch_calls = [
        args for _, args in mcp.calls if args.get("tool") == "hub_call_device_command"
    ]
    assert dispatch_calls[0]["args"]["deviceId"] == "6923"
    assert dispatch_calls[0]["args"]["command"] == "allowInternet"
    assert dispatch_calls[0]["args"]["waitFor"]["expectedValue"] == "allowed"


@pytest.mark.asyncio
async def test_unconverged_block_reports_uncertainty_not_silent_success() -> None:
    mcp = InternetAccessMCP(converged=False)
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result(
        "block the tv", session_id="block-tv-unconverged-test"
    )

    assert "could not verify" in outcome.message
    assert "blocked." not in outcome.message


@pytest.mark.asyncio
async def test_scheduled_block_request_is_left_to_rule_authoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"block the tv at 10pm" carries an AT_TIME clause, so it must be left
    completely alone by the new immediate path and reach RuleAuthoringService
    via base_process -- exactly as it did before this fix, unchanged.
    """

    async def fake_base_result(_self: object, prompt: str, *_args: object, **_kwargs: object) -> AgentOutcome:
        return AgentOutcome(
            message="handed to base agent", request_class="write", evidence=[], choices=[]
        )

    monkeypatch.setattr(
        BaseUnifiedMCPAgent, "process_user_request_result", fake_base_result
    )
    mcp = InternetAccessMCP()
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result(
        "block the tv at 10pm", session_id="block-tv-scheduled-test"
    )

    assert outcome.message == "handed to base agent"
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_no_capable_device_reports_a_clear_error_not_a_wrong_device() -> None:
    class NoBlockCapableMCP(InternetAccessMCP):
        def __init__(self) -> None:
            super().__init__()
            self.devices = [TV_SWITCH_DEVICE]

    mcp = NoBlockCapableMCP()
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result(
        "block the tv", session_id="block-tv-no-capable-test"
    )

    assert "could not find a device that supports blocking internet access" in outcome.message
    assert mcp.calls == []

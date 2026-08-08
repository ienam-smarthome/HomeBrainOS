from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from confirmation_policy import ConfirmationPolicy  # noqa: E402
from confirmation_store import PendingConfirmation  # noqa: E402
from confirmed_action_coordinator import ConfirmedActionCoordinator  # noqa: E402
from rule_authoring_service import NEW_RULE_ID_TOKEN  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from tool_discovery_catalog import ToolDiscoveryCatalog  # noqa: E402
from tool_executor import ToolExecution  # noqa: E402
from tool_registry import ToolEffect  # noqa: E402


def _rule_arguments(name: str) -> dict:
    return {
        "tool": "hub_set_rule",
        "args": {
            "name": name,
            "addAction": {
                "capability": "runCommand",
                "command": "blockInternet",
                "deviceIds": ["6916"],
                "capabilityFilter": "Switch",
            },
        },
    }


def _execution(
    name: str,
    arguments: dict,
    data: dict,
    *,
    success: bool,
) -> ToolExecution:
    result = MCPToolResult(name, arguments, {}, "", data)
    return ToolExecution(
        name=name,
        arguments=arguments,
        effect=ToolEffect.SENSITIVE_WRITE,
        success=success,
        elapsed_ms=1,
        content="{}",
        result=result,
    )


class FakeExecutor:
    def __init__(self, results: list[ToolExecution]) -> None:
        self.results = list(results)
        self.calls = []

    async def execute(self, name, arguments, **kwargs):
        self.calls.append((name, arguments, kwargs))
        return self.results.pop(0)


def _pending(actions):
    return PendingConfirmation(
        expires_at=999,
        actions=actions,
        messages=[{"role": "user", "content": "create rules"}],
        assistant_message={"role": "assistant", "content": "Please confirm"},
    )


def _catalog(*names: str) -> ToolDiscoveryCatalog:
    return ToolDiscoveryCatalog([
        MCPTool(name, name, {"type": "object"}) for name in names
    ])


def _clock(*values):
    sequence = iter(values)
    return lambda: next(sequence)


@pytest.mark.asyncio
async def test_verified_rule_group_executes_sequentially_and_reports_ids():
    gateway = "hub_manage_rule_machine"
    first = _rule_arguments("Block Tab S9 FE (Start)")
    second = _rule_arguments("Block Tab S9 FE (End)")
    executor = FakeExecutor([
        _execution(
            gateway,
            first,
            {"success": True, "appId": 4165, "health": {"ok": True}},
            success=True,
        ),
        _execution(
            gateway,
            second,
            {"success": True, "appId": 4166, "health": {"ok": True}},
            success=True,
        ),
    ])
    mutations = []

    async def unexpected_chat(messages, tools):
        raise AssertionError("verified Rule Machine groups must not use AI reporting")

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        unexpected_chat,
        lambda: mutations.append(True),
    )

    report = await coordinator.resume(
        _pending([(gateway, first), (gateway, second)]),
        _catalog(gateway),
    )

    assert "Confirmed Rule Machine actions completed" in report
    assert "appId: 4165" in report
    assert "appId: 4166" in report
    assert len(executor.calls) == 2
    assert len(mutations) == 2
    assert all(call[1]["args"]["confirm"] is True for call in executor.calls)


@pytest.mark.asyncio
async def test_unverified_rule_stops_group_and_reports_skipped_actions():
    gateway = "hub_manage_rule_machine"
    first = _rule_arguments("Broken rule")
    second = _rule_arguments("Must not run")
    executor = FakeExecutor([
        _execution(
            gateway,
            first,
            {"success": False, "error": "Rule validation failed"},
            success=False,
        ),
    ])

    async def unexpected_chat(messages, tools):
        raise AssertionError("failed Rule Machine groups must not use AI reporting")

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        unexpected_chat,
        lambda: None,
    )

    report = await coordinator.resume(
        _pending([(gateway, first), (gateway, second)]),
        _catalog(gateway),
    )

    assert "not fully completed" in report
    assert "Rule validation failed" in report
    assert "1 remaining confirmed action was not attempted" in report
    assert len(executor.calls) == 1


@pytest.mark.asyncio
async def test_incomplete_rule_payload_is_cancelled_before_execution():
    gateway = "hub_manage_rule_machine"
    executor = FakeExecutor([])

    async def unexpected_chat(messages, tools):
        raise AssertionError("invalid queued payload must not reach the model")

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        unexpected_chat,
        lambda: None,
    )

    report = await coordinator.resume(
        _pending([(gateway, {"tool": "hub_set_rule", "args": {}})]),
        _catalog(gateway),
    )

    assert "payload is incomplete" in report
    assert executor.calls == []


@pytest.mark.asyncio
async def test_non_rule_confirmation_uses_bounded_post_execution_synthesis():
    gateway = "hub_manage_apps"
    arguments = {"tool": "hub_set_app_disabled", "args": {"appId": 12}}
    executor = FakeExecutor([
        _execution(
            gateway,
            arguments,
            {"success": True},
            success=True,
        ),
    ])
    seen = {}

    async def chat(messages, tools):
        seen["messages"] = messages
        seen["tools"] = tools
        return {"content": "Confirmed app change completed."}

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        chat,
        lambda: None,
    )

    report = await coordinator.resume(
        _pending([(gateway, arguments)]),
        _catalog(gateway),
    )

    assert report == "Confirmed app change completed."
    assert seen["messages"][-1]["role"] == "tool"
    assert seen["messages"][-1]["tool_name"] == gateway


@pytest.mark.asyncio
async def test_failed_destructive_op_is_reported_deterministically_not_by_model():
    """`hub_manage_destructive_ops` (permanent device deletion, radio/
    network resets, hub reboot/shutdown) has no tool-specific deterministic
    report -- unlike Rule Machine and firmware, there are no live example
    payloads to build one safely against. But a genuinely failed
    destructive write must never reach the user narrated as a success by
    the model: confirmed_failure_report is the generic safety net for
    exactly this, and it must pre-empt the chat callback entirely so a
    model that (as this whole release cycle found repeatedly) can't be
    trusted with this kind of decision never gets the chance to soften or
    misreport a failure on an irreversible action.
    """

    gateway = "hub_manage_destructive_ops"
    arguments = {"tool": "hub_delete_device", "args": {"deviceId": "42", "confirm": True}}
    executor = FakeExecutor([
        _execution(
            gateway,
            arguments,
            {"success": False, "error": "Device is still referenced by 2 rules."},
            success=False,
        ),
    ])
    chat_called = False

    async def chat(messages, tools):
        nonlocal chat_called
        chat_called = True
        return {"content": "Device deleted successfully."}

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        chat,
        lambda: None,
    )

    report = await coordinator.resume(
        _pending([(gateway, arguments)]),
        _catalog(gateway),
    )

    assert "did not succeed" in report
    assert "still referenced by 2 rules" in report
    assert chat_called is False


def test_nested_rule_result_verification_requires_id_and_healthy_result():
    arguments = _rule_arguments("Nested")
    verified = _execution(
        "hub_manage_rule_machine",
        arguments,
        {
            "result": {
                "data": {
                    "success": True,
                    "ruleId": 42,
                    "partial": False,
                    "health": {"ok": True},
                }
            }
        },
        success=True,
    )
    partial = _execution(
        "hub_manage_rule_machine",
        arguments,
        {
            "success": True,
            "ruleId": 43,
            "partial": True,
            "health": {"ok": True},
        },
        success=True,
    )

    assert ConfirmedActionCoordinator.verified_rule_execution(verified) is True
    assert ConfirmedActionCoordinator.verified_rule_execution(partial) is False


@pytest.mark.asyncio
async def test_verified_rule_records_verification_duration_without_failure():
    gateway = "hub_manage_rule_machine"
    arguments = _rule_arguments("Healthy rule")
    executor = FakeExecutor([
        _execution(
            gateway,
            arguments,
            {"success": True, "appId": 77, "health": {"ok": True}},
            success=True,
        )
    ])

    async def unexpected_chat(messages, tools):
        raise AssertionError("verified Rule Machine actions must not use AI reporting")

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        unexpected_chat,
        lambda: None,
        clock=_clock(10.0, 10.012),
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        await coordinator.resume(_pending([(gateway, arguments)]), _catalog(gateway))
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["timings_ms"]["verification"] == 12
    assert "mutation_verification_failures" not in snapshot["counters"]


@pytest.mark.asyncio
async def test_unverified_rule_records_failure_and_verification_duration():
    gateway = "hub_manage_rule_machine"
    arguments = _rule_arguments("Unhealthy rule")
    executor = FakeExecutor([
        _execution(
            gateway,
            arguments,
            {"success": True, "appId": 78, "health": {"ok": False}},
            success=True,
        )
    ])

    async def unexpected_chat(messages, tools):
        raise AssertionError("failed Rule Machine actions must not use AI reporting")

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        unexpected_chat,
        lambda: None,
        clock=_clock(20.0, 20.007),
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        await coordinator.resume(_pending([(gateway, arguments)]), _catalog(gateway))
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["timings_ms"]["verification"] == 7
    assert snapshot["counters"]["mutation_verification_failures"] == 1



def _self_pause_arguments() -> dict:
    return {
        "tool": "hub_set_rule",
        "args": {
            "appId": NEW_RULE_ID_TOKEN,
            "addAction": {
                "capability": "pauseRule",
                "action": "pause",
                "ruleIds": [NEW_RULE_ID_TOKEN],
            },
        },
    }


@pytest.mark.asyncio
async def test_one_time_rule_pause_followup_resolves_placeholder_to_real_appid():
    """Regression coverage for the one-time-rule auto-pause feature:
    RuleAuthoringService queues a create action followed by a self-pause
    edit that references the not-yet-created rule via NEW_RULE_ID_TOKEN
    (see rule_authoring_service._self_pause_action). This proves the
    coordinator substitutes that placeholder with the real appId the hub
    assigns to the create action -- in both the edit target (`args.appId`)
    and the action's own `ruleIds` -- before executing the follow-up, and
    renders a distinct, non-misleading report line for it (not "Created
    **Rule Machine rule**", which would be wrong since nothing new was
    created by the second action).
    """

    gateway = "hub_manage_rule_machine"
    create = _rule_arguments("Turn on Bedroom 1 Lamp (One-time 2026-08-07)")
    pause = _self_pause_arguments()
    executor = FakeExecutor([
        _execution(
            gateway,
            create,
            {"success": True, "appId": 4171, "health": {"ok": True}},
            success=True,
        ),
        _execution(
            gateway,
            pause,
            {"success": True, "appId": 4171, "health": {"ok": True}},
            success=True,
        ),
    ])

    async def unexpected_chat(messages, tools):
        raise AssertionError("verified Rule Machine groups must not use AI reporting")

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        unexpected_chat,
        lambda: None,
    )

    report = await coordinator.resume(
        _pending([(gateway, create), (gateway, pause)]),
        _catalog(gateway),
    )

    # The placeholder must never reach the hub -- both occurrences in the
    # second call's actual arguments have to be the real appId.
    second_call_arguments = executor.calls[1][1]
    assert second_call_arguments["args"]["appId"] == "4171"
    assert second_call_arguments["args"]["addAction"]["ruleIds"] == ["4171"]
    assert NEW_RULE_ID_TOKEN not in str(second_call_arguments)

    assert "Created **Turn on Bedroom 1 Lamp (One-time 2026-08-07)** (appId: 4171)" in report
    assert (
        "**Turn on Bedroom 1 Lamp (One-time 2026-08-07)** was paused "
        "immediately after its one-time trigger so it cannot fire again."
    ) in report
    # The pause line must reuse the rule's real name, not the generic
    # "Rule Machine rule" fallback queued_rule_name() would otherwise
    # produce for an action with no `name` field of its own.
    assert "Created **Rule Machine rule**" not in report


@pytest.mark.asyncio
async def test_one_time_rule_pause_followup_failure_is_reported_distinctly():
    """If the create succeeds but the follow-up pause edit fails
    verification, the rule still exists (created successfully) -- the
    report must say so clearly rather than implying the whole write failed,
    while still warning that the safety pause did not take effect.
    """

    gateway = "hub_manage_rule_machine"
    create = _rule_arguments("Turn on Bedroom 1 Lamp (One-time 2026-08-07)")
    pause = _self_pause_arguments()
    executor = FakeExecutor([
        _execution(
            gateway,
            create,
            {"success": True, "appId": 4171, "health": {"ok": True}},
            success=True,
        ),
        _execution(
            gateway,
            pause,
            {"success": False, "error": "Rule 4171 not found"},
            success=False,
        ),
    ])

    async def unexpected_chat(messages, tools):
        raise AssertionError("failed Rule Machine actions must not use AI reporting")

    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True),
        executor,
        unexpected_chat,
        lambda: None,
    )

    report = await coordinator.resume(
        _pending([(gateway, create), (gateway, pause)]),
        _catalog(gateway),
    )

    assert "Created **Turn on Bedroom 1 Lamp (One-time 2026-08-07)** (appId: 4171)" in report
    assert (
        "**Turn on Bedroom 1 Lamp (One-time 2026-08-07)** was created but "
        "could not be confirmed paused afterward: Rule 4171 not found."
    ) in report

from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from grounding_policy import (  # noqa: E402
    EVIDENCE_REFUSAL,
    EVIDENCE_RETRY_INSTRUCTION,
    GroundingAction,
    GroundingPolicy,
    LOG_REFUSAL,
    LOG_RETRY_INSTRUCTION,
)


def test_live_read_retries_once_then_refuses_without_evidence():
    policy = GroundingPolicy(logs_requested=False, conversational=False)

    first = policy.decide_no_tool_calls(has_live_evidence=False)
    second = policy.decide_no_tool_calls(has_live_evidence=False)

    assert (first.action, first.message) == (
        GroundingAction.RETRY,
        EVIDENCE_RETRY_INSTRUCTION,
    )
    assert (second.action, second.message) == (
        GroundingAction.REFUSE,
        EVIDENCE_REFUSAL,
    )


def test_log_grounding_has_priority_even_when_other_live_evidence_exists():
    policy = GroundingPolicy(logs_requested=True, conversational=False)

    first = policy.decide_no_tool_calls(has_live_evidence=True)
    second = policy.decide_no_tool_calls(has_live_evidence=True)

    assert (first.action, first.message) == (
        GroundingAction.RETRY,
        LOG_RETRY_INSTRUCTION,
    )
    assert (second.action, second.message) == (
        GroundingAction.REFUSE,
        LOG_REFUSAL,
    )


def test_successful_exact_log_call_satisfies_log_requirement():
    policy = GroundingPolicy(logs_requested=True, conversational=False)
    policy.record_tool_outcome(
        "hub_read_diagnostics",
        {"tool": "hub_get_logs", "args": {"since": "30m"}},
        success=True,
    )

    decision = policy.decide_no_tool_calls(has_live_evidence=True)

    assert policy.logs_checked is True
    assert decision.action is GroundingAction.ACCEPT
    assert decision.message is None


def test_unrelated_or_failed_diagnostic_call_does_not_satisfy_log_requirement():
    policy = GroundingPolicy(logs_requested=True, conversational=False)
    policy.record_tool_outcome(
        "hub_read_diagnostics",
        {"tool": "hub_get_metrics", "args": {}},
        success=True,
    )
    policy.record_tool_outcome(
        "hub_read_diagnostics",
        {"tool": "hub_get_logs", "args": {}},
        success=False,
    )

    decision = policy.decide_no_tool_calls(has_live_evidence=True)

    assert policy.logs_checked is False
    assert decision.action is GroundingAction.RETRY


def test_conversational_answer_does_not_require_live_evidence():
    policy = GroundingPolicy(logs_requested=False, conversational=True)

    decision = policy.decide_no_tool_calls(has_live_evidence=False)

    assert decision.action is GroundingAction.ACCEPT


def test_successful_live_evidence_allows_non_conversational_answer():
    policy = GroundingPolicy(logs_requested=False, conversational=False)

    decision = policy.decide_no_tool_calls(has_live_evidence=True)

    assert decision.action is GroundingAction.ACCEPT


def test_request_instances_do_not_share_retry_state():
    first = GroundingPolicy(logs_requested=False, conversational=False)
    second = GroundingPolicy(logs_requested=False, conversational=False)

    assert first.decide_no_tool_calls(
        has_live_evidence=False
    ).action is GroundingAction.RETRY
    assert first.decide_no_tool_calls(
        has_live_evidence=False
    ).action is GroundingAction.REFUSE
    assert second.decide_no_tool_calls(
        has_live_evidence=False
    ).action is GroundingAction.RETRY

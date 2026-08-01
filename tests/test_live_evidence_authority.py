from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from grounding_policy import (  # noqa: E402
    EVIDENCE_REFUSAL,
    EVIDENCE_RETRY_INSTRUCTION,
    GroundingAction,
    LOG_REFUSAL,
    LOG_RETRY_INSTRUCTION,
)
from live_evidence_authority import LiveEvidenceAuthority  # noqa: E402


def _authority(*, logs_requested: bool = False, conversational: bool = False):
    recorder = EvidenceRecorder()
    token = recorder.begin()
    authority = LiveEvidenceAuthority(
        recorder,
        logs_requested=logs_requested,
        conversational=conversational,
    )
    return recorder, token, authority


def test_discovery_receipt_does_not_authorize_live_answer() -> None:
    recorder, token, authority = _authority()
    try:
        recorder.record(
            "hub_search_tools",
            {"query": "device state"},
            success=True,
            elapsed_ms=1,
            summary="one gateway found",
            supports_live_claim=False,
            evidence_kind="tool_discovery",
        )

        first = authority.decide_no_tool_calls()
        second = authority.decide_no_tool_calls()

        assert first.action is GroundingAction.RETRY
        assert first.message == EVIDENCE_RETRY_INSTRUCTION
        assert second.action is GroundingAction.REFUSE
        assert second.message == EVIDENCE_REFUSAL
    finally:
        recorder.reset(token)


def test_successful_live_receipt_authorizes_answer() -> None:
    recorder, token, authority = _authority()
    try:
        recorder.record(
            "hub_read_devices",
            {"tool": "hub_list_devices", "args": {}},
            success=True,
            elapsed_ms=2,
            summary="107 devices",
        )

        decision = authority.decide_no_tool_calls()

        assert authority.has_live_evidence is True
        assert decision.action is GroundingAction.ACCEPT
        assert decision.message is None
    finally:
        recorder.reset(token)


def test_log_request_requires_successful_authoritative_log_call() -> None:
    recorder, token, authority = _authority(logs_requested=True)
    try:
        authority.record_tool_outcome(
            "hub_read_diagnostics",
            {"tool": "hub_get_logs", "args": {"since": "30m"}},
            success=False,
        )
        first = authority.decide_no_tool_calls()
        second = authority.decide_no_tool_calls()

        assert authority.logs_checked is False
        assert first.action is GroundingAction.RETRY
        assert first.message == LOG_RETRY_INSTRUCTION
        assert second.action is GroundingAction.REFUSE
        assert second.message == LOG_REFUSAL
    finally:
        recorder.reset(token)


def test_successful_log_call_satisfies_log_requirement() -> None:
    recorder, token, authority = _authority(logs_requested=True)
    try:
        recorder.record(
            "hub_read_diagnostics",
            {"tool": "hub_get_logs", "args": {"since": "30m"}},
            success=True,
            elapsed_ms=4,
            summary="8 log rows",
        )
        authority.record_tool_outcome(
            "hub_read_diagnostics",
            {"tool": "hub_get_logs", "args": {"since": "30m"}},
            success=True,
        )

        decision = authority.decide_no_tool_calls()

        assert authority.logs_checked is True
        assert decision.action is GroundingAction.ACCEPT
    finally:
        recorder.reset(token)


def test_conversational_answer_does_not_require_live_receipt() -> None:
    recorder, token, authority = _authority(conversational=True)
    try:
        decision = authority.decide_no_tool_calls()

        assert authority.has_live_evidence is False
        assert decision.action is GroundingAction.ACCEPT
    finally:
        recorder.reset(token)

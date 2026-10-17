"""Read-only deep investigation requests must stop with receipt-only evidence."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from app import RequestCoordinator, _needs_investigation_deadline
from api_response_builder import build_agent_response
from evidence_recorder import EvidenceRecorder
from mcp_agent_orchestrator import AgentOutcome
from request_runtime import remember_verified_outcome


HISTORIC = (
    'Verify whether the automation "Power saving: Bedroom 3 Mesh off @night" '
    "(app 3950) actually issued an OFF command to Bedroom 3 Mesh (device 7103) "
    "on 12 October 2026 at approximately 01:30 BST. Read-only."
)


@pytest.mark.parametrize("question", [
    HISTORIC,
    "Inspect the actual Groovy source code for automation app 4019. Read-only.",
    "Investigate why Bedroom 3 Mesh went offline last Sunday.",
    "Reconstruct Bedroom 1 lighting events and compare possible causes.",
    "Audit the Hubitat scheduled jobs for unnecessary work, read-only.",
])
def test_read_only_investigations_have_request_deadlines(question):
    assert _needs_investigation_deadline(question)


@pytest.mark.parametrize("question", [
    "Turn off Bedroom 3 Mesh.",
    "Please disable app 3950 and delete the rule.",
    "Verify whether app 3950 issued OFF. Then disable app 3950.",
    "What is the current Bedroom 3 temperature?",
    "Review app 3950 current settings.",
    "Explain what an MQTT broker is.",
])
def test_routine_reads_conversation_and_writes_keep_existing_deadline_policy(question):
    assert not _needs_investigation_deadline(question)


@pytest.mark.asyncio
async def test_deadline_cancels_model_loop_and_returns_only_successful_read_receipts():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()
    cancelled = asyncio.Event()

    async def investigation():
        token = recorder.begin()
        try:
            recorder.record(
                "hub_read_devices",
                {"tool": "hub_get_device", "args": {"deviceId": "7103"}},
                success=True, elapsed_ms=3, summary="Device configuration received",
                effect="read",
            )
            recorder.record(
                "hub_read_devices",
                {"tool": "hub_get_logs", "args": {"deviceId": "7103"}},
                success=False, elapsed_ms=2, summary="history unavailable",
                effect="read",
            )
            # Simulated receipt only: no real Hubitat operation is executed.
            recorder.record(
                "hub_manage_devices",
                {"tool": "hub_device_off", "args": {"deviceId": "7103"}},
                success=True, elapsed_ms=4, summary="test-only mutation receipt",
                effect="write",
            )
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
        finally:
            recorder.reset(token)

    outcome = await coordinator.run(
        "historical-7103", investigation(), deadline_seconds=0.10,
    )
    assert cancelled.is_set()
    assert outcome.route == "investigation-timeout"
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0]["sub_tool"] == "hub_get_device"
    assert "hub_get_device" in outcome.message
    assert "hub_get_logs" not in outcome.message
    assert "hub_device_off" not in outcome.message
    assert outcome.confirmation_required is False
    result = build_agent_response(
        outcome, model="deepseek-v4", elapsed_ms=102, version="0.18.26"
    )
    assert result["success"] is False
    assert result["status_verification"] == "incomplete-timeout"
    assert result["metrics"]["outcome"] == "unresolved"
    assert len(result["evidence"]) == 1
    await coordinator.close()


@pytest.mark.asyncio
async def test_deadline_combines_prior_verified_checkpoint_and_later_read():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()
    baseline = AgentOutcome(
        message="An unverified model guess",
        request_class="live-read", choices=[], evidence=[{
            "tool": "hub_read_apps_code", "sub_tool": "hub_get_source",
            "success": True, "mutates": False, "effect": "read",
        }],
    )

    async def investigation():
        token = recorder.begin()
        try:
            remember_verified_outcome(baseline)
            recorder.record(
                "hub_read_devices", {"tool": "hub_get_device", "args": {"deviceId": "7103"}},
                success=True, elapsed_ms=1, summary="read", effect="read",
            )
            await asyncio.Event().wait()
        finally:
            recorder.reset(token)

    outcome = await coordinator.run(
        "historical-later-read", investigation(), deadline_seconds=0.1,
    )
    assert outcome.route == "investigation-timeout"
    assert len(outcome.evidence) == 2
    assert "unverified model guess" not in outcome.message
    assert "hub_get_source" in outcome.message
    assert "hub_get_device" in outcome.message
    await coordinator.close()


@pytest.mark.asyncio
async def test_deadline_with_only_failed_or_mutating_receipts_retains_504():
    from fastapi import HTTPException

    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()

    async def investigation():
        token = recorder.begin()
        try:
            recorder.record(
                "hub_read_devices", {"tool": "hub_get_device"},
                success=False, elapsed_ms=1, summary="failed", effect="read",
            )
            await asyncio.Event().wait()
        finally:
            recorder.reset(token)

    with pytest.raises(HTTPException) as exc:
        await coordinator.run("no-proof", investigation(), deadline_seconds=0.08)
    assert exc.value.status_code == 504
    await coordinator.close()

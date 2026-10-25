"""0.18.109: read-only investigation deadlines remain bounded and diagnosable.

Simulations only. No real Hubitat, Ollama or Home Assistant calls.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from app import RequestCoordinator, OPTIONS, _needs_investigation_deadline
from request_runtime import set_request_stage
from evidence_recorder import EvidenceRecorder


QUESTION = (
    "Why does Livingroom Light 1 sometimes stay ON when nobody is in the "
    "room? Investigate its controlling automation, sensors, inactivity timers "
    "and recorded activity using verified evidence. Read-only; do not change anything."
)


def test_deep_light_investigation_is_bounded_not_mutation():
    assert _needs_investigation_deadline(QUESTION)
    assert not _needs_investigation_deadline(
        "Turn off Livingroom Light 1."
    )


def test_release_defaults_give_source_investigation_more_room():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    app_source = (APP / "app.py").read_text(encoding="utf-8")
    assert 'version: "0.18.109"' in config
    assert "  investigation_deadline_seconds: 180" in config
    assert '"investigation_deadline_seconds": 180' in app_source
    assert 'OPTIONS.get("investigation_deadline_seconds") or 180' in app_source


def test_round_phase_instrumentation_keeps_model_led_tools():
    orchestrator = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "from request_runtime import set_request_stage" in orchestrator
    assert 'f"AI reasoning (round {round_index + 1}/{active_round_budget})"' in orchestrator
    assert 'f"Executing tool calls (round {round_index + 1}/{active_round_budget})"' in orchestrator
    assert "configuration_semantics_followup(" in orchestrator


@pytest.mark.asyncio
async def test_no_verified_reads_returns_diagnostic_504_and_cancels():
    coordinator = RequestCoordinator()
    cancelled = asyncio.Event()

    async def unresponsive_ai():
        set_request_stage("AI reasoning (round 1/9)")
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with pytest.raises(HTTPException) as error:
        await coordinator.run(
            "diag-109", unresponsive_ai(), request_id="diag-request-109",
            deadline_seconds=0.10,
        )
    assert cancelled.is_set()
    assert error.value.status_code == 504
    detail = str(error.value.detail)
    assert "AI reasoning (round 1/9)" in detail
    assert "0.1s deadline" in detail
    assert "No verified read-only results" in detail
    assert "investigation_deadline_seconds" in detail
    await coordinator.close()


@pytest.mark.asyncio
async def test_verified_read_still_returns_safe_evidence_only_timeout():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()

    async def partial_read():
        token = recorder.begin()
        try:
            set_request_stage("Executing tool calls (round 1/9)")
            recorder.record(
                "hub_read_apps_code",
                {"tool": "hub_get_app_config", "args": {"appId": "4019"}},
                success=True, elapsed_ms=1,
                summary="Received installed application settings",
                effect="read",
            )
            await asyncio.Event().wait()
        finally:
            recorder.reset(token)

    outcome = await coordinator.run(
        "partial-109", partial_read(), deadline_seconds=0.10
    )
    assert outcome.route == "investigation-timeout"
    assert outcome.confirmation_required is False
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0]["sub_tool"] == "hub_get_app_config"
    assert "hub_get_app_config" in outcome.message
    assert "never turns off" not in outcome.message
    await coordinator.close()

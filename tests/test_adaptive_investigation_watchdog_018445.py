"""v0.18.445 adaptive investigation timing: synthetic, no hub/model/writes."""
from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from app import RequestCoordinator, _answer_result
from evidence_recorder import EvidenceRecorder


def record(recorder, label, *, success=True, mutates=False, effect="read"):
    recorder.record(
        "hub_read_devices",
        {"tool": "hub_get_device", "args": {"labelFilter": label}},
        success=success, elapsed_ms=1, summary="Synthetic read",
        mutates=mutates, effect=effect,
    )


@pytest.mark.asyncio
async def test_distinct_verified_read_extends_idle_window_beyond_original_total_limit():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()

    async def investigation():
        token = recorder.begin()
        try:
            await asyncio.sleep(0.09)
            record(recorder, "Room A")
            await asyncio.sleep(0.13)
            return "completed after old fixed-total cutoff"
        finally:
            recorder.reset(token)

    result = await coordinator.run(
        "adaptive", investigation(), request_id="adaptive",
        idle_timeout_seconds=0.18, emergency_watchdog_seconds=2.0,
    )
    assert result == "completed after old fixed-total cutoff"
    await coordinator.close()


@pytest.mark.asyncio
async def test_identical_successful_repeats_do_not_reset_inactivity_window():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()
    stopped = asyncio.Event()

    async def investigation():
        token = recorder.begin()
        try:
            record(recorder, "Room A")
            await asyncio.sleep(0.11)
            record(recorder, "Room A")
            await asyncio.Event().wait()
        finally:
            stopped.set()
            recorder.reset(token)

    result = await coordinator.run(
        "repeat", investigation(), idle_timeout_seconds=0.15,
        emergency_watchdog_seconds=2.0,
    )
    assert stopped.is_set()
    assert result.route == "investigation-timeout"
    assert len(result.evidence) == 2  # Receipts remain; no extra time credit.
    assert "hub_get_device" in result.message
    await coordinator.close()


@pytest.mark.asyncio
async def test_failed_reads_and_write_receipts_never_count_as_source_progress():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()

    async def investigation():
        token = recorder.begin()
        try:
            record(recorder, "Room A")
            await asyncio.sleep(0.09)
            record(recorder, "Room B", success=False)
            record(recorder, "Room C", mutates=True, effect="write")
            await asyncio.Event().wait()
        finally:
            recorder.reset(token)

    result = await coordinator.run(
        "failure", investigation(), idle_timeout_seconds=0.15,
        emergency_watchdog_seconds=2.0,
    )
    assert result.route == "investigation-timeout"
    assert [x["success"] for x in result.evidence] == [True]
    assert result.confirmation_required is False
    await coordinator.close()


@pytest.mark.asyncio
async def test_stage_chatter_never_extends_stalled_read_window():
    from request_runtime import set_request_stage

    coordinator = RequestCoordinator()

    async def investigation():
        for n in range(8):
            set_request_stage(f"Thinking {n}")
            await asyncio.sleep(0.04)
        return "should be stopped"

    with pytest.raises(HTTPException) as exc:
        await coordinator.run(
            "chatter", investigation(), idle_timeout_seconds=0.10,
            emergency_watchdog_seconds=2,
        )
    assert exc.value.status_code == 504
    assert "new verified read scope" in str(exc.value.detail)
    await coordinator.close()


@pytest.mark.asyncio
async def test_hard_emergency_watchdog_stops_even_fresh_distinct_reads():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()
    cancelled = asyncio.Event()

    async def investigation():
        token = recorder.begin()
        try:
            for n in range(20):
                record(recorder, f"Room {n}")
                await asyncio.sleep(0.06)
        finally:
            cancelled.set()
            recorder.reset(token)

    result = await coordinator.run(
        "hard", investigation(), idle_timeout_seconds=0.25,
        emergency_watchdog_seconds=0.31,
    )
    assert cancelled.is_set()
    assert result.route == "investigation-timeout"
    assert "emergency watchdog" in result.message
    assert len(result.evidence) >= 3
    await coordinator.close()


@pytest.mark.asyncio
async def test_public_progress_only_shows_counts_not_source_names_or_tokens():
    coordinator = RequestCoordinator()
    recorder = EvidenceRecorder()
    entered = asyncio.Event()

    async def investigation():
        token = recorder.begin()
        try:
            record(recorder, "SecretSourceName")
            entered.set()
            await asyncio.sleep(0.08)
            return "done"
        finally:
            recorder.reset(token)

    task = asyncio.create_task(coordinator.run(
        "progress", investigation(), request_id="progress-1",
        idle_timeout_seconds=1, emergency_watchdog_seconds=2,
    ))
    await entered.wait()
    snapshot = coordinator.progress("progress", "progress-1")
    assert snapshot["verified_read_scopes"] == 1
    assert snapshot["seconds_since_source_progress"] >= 0
    assert "SecretSourceName" not in str(snapshot)
    assert await task == "done"
    await coordinator.close()


def test_normal_ask_route_has_no_fixed_deadline_parameter():
    code = inspect.getsource(_answer_result)
    assert "deadline_seconds=max(" not in code
    assert "idle_timeout_seconds=max(" in code
    assert "emergency_watchdog_seconds=max(" in code
    assert 'OPTIONS.get("investigation_deadline_seconds")' not in code

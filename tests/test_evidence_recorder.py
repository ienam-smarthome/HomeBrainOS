from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from tool_registry import ToolEffect  # noqa: E402


def test_record_is_request_scoped_and_reset_restores_inactive_context():
    recorder = EvidenceRecorder()

    recorder.record(
        "hub_read_devices",
        {},
        success=True,
        elapsed_ms=1,
        summary="ignored outside a request",
    )
    assert recorder.receipts() == []

    token = recorder.begin()
    recorder.record(
        "hub_read_devices",
        {},
        success=True,
        elapsed_ms=2,
        summary="live devices",
        effect=ToolEffect.READ,
    )
    assert len(recorder.receipts()) == 1

    recorder.reset(token)
    assert recorder.receipts() == []


@pytest.mark.asyncio
async def test_parallel_request_contexts_do_not_share_receipts():
    recorder = EvidenceRecorder()

    async def capture(tool: str) -> list[dict]:
        token = recorder.begin()
        try:
            await asyncio.sleep(0)
            recorder.record(
                tool,
                {},
                success=True,
                elapsed_ms=1,
                summary=tool,
                effect=ToolEffect.READ,
            )
            await asyncio.sleep(0)
            return recorder.receipts()
        finally:
            recorder.reset(token)

    first, second = await asyncio.gather(capture("first"), capture("second"))

    assert [item["tool"] for item in first] == ["first"]
    assert [item["tool"] for item in second] == ["second"]
    assert recorder.receipts() == []


def test_record_redacts_nested_secrets_and_bounds_large_values():
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        recorder.record(
            "hub_read_devices",
            {
                "authorization": "Bearer private",
                "args": {
                    "api_key": "private",
                    "password_hint": "private",
                    "deviceId": "42",
                    "description": "x" * 300,
                },
                "items": list(range(30)),
            },
            success=True,
            elapsed_ms=3,
            summary="devices",
            effect=ToolEffect.READ,
        )
        arguments = recorder.receipts()[0]["arguments"]
    finally:
        recorder.reset(token)

    assert arguments["authorization"] == "[redacted]"
    assert arguments["args"]["api_key"] == "[redacted]"
    assert arguments["args"]["password_hint"] == "[redacted]"
    assert arguments["args"]["deviceId"] == "42"
    assert arguments["args"]["description"].endswith("...")
    assert len(arguments["items"]) == 20


def test_receipt_snapshot_cannot_mutate_authoritative_context():
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        recorder.record(
            "hub_read_devices",
            {"args": {"deviceId": "42"}},
            success=True,
            elapsed_ms=4,
            summary="devices",
            evidence_kind="authoritative_state_snapshot",
            effect=ToolEffect.READ,
        )
        snapshot = recorder.receipts()
        snapshot[0]["arguments"]["args"]["deviceId"] = "changed"

        assert recorder.receipts()[0]["arguments"]["args"]["deviceId"] == "42"
    finally:
        recorder.reset(token)


def test_live_evidence_requires_success_and_explicit_claim_support():
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        recorder.record(
            "hub_search_tools",
            {"query": "devices"},
            success=True,
            elapsed_ms=1,
            summary="tool matches",
            supports_live_claim=False,
            effect=ToolEffect.READ,
        )
        recorder.record(
            "hub_read_devices",
            {},
            success=False,
            elapsed_ms=2,
            summary="failed",
            supports_live_claim=True,
            effect=ToolEffect.READ,
        )
        assert recorder.has_live_evidence() is False

        recorder.record(
            "hub_read_devices",
            {},
            success=True,
            elapsed_ms=3,
            summary="devices",
            supports_live_claim=True,
            effect=ToolEffect.READ,
        )
        assert recorder.has_live_evidence() is True
    finally:
        recorder.reset(token)


def test_record_infers_structured_effect_when_caller_omits_it():
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        recorder.record(
            "hub_manage_devices",
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "on"},
            },
            success=True,
            elapsed_ms=2,
            summary="command sent",
        )
        receipt = recorder.receipts()[0]
    finally:
        recorder.reset(token)

    assert receipt["effect"] == ToolEffect.ROUTINE_WRITE.value
    assert receipt["mutates"] is True
    assert receipt["timestamp"].endswith("+00:00")

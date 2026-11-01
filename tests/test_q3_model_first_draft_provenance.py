"""First-provider-draft provenance: privacy, scope, and fail-closed publication."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from model_first_draft_provenance import (
    PrivateModelDraft, begin_private_model_draft, reset_private_model_draft,
    record_first_no_tools_draft, record_coordinator_result, record_final_answer,
    private_snapshot, public_boundary_shape,
)
from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import build_observed_agent_outcome
from api_response_builder import build_agent_response
from shared_investigation_completion import apply_shared_investigation_completion


def capture():
    token = begin_private_model_draft()
    try:
        record_first_no_tools_draft("MODEL SECRET-device 9911 at 01:19")
        record_first_no_tools_draft("SECOND SHOULD NOT REPLACE FIRST")
        record_coordinator_result("CORRECTED SECRET-device 9911")
        record_final_answer("GUARDED SECRET-device 9911")
        return private_snapshot()
    finally:
        reset_private_model_draft(token)


def test_actual_first_draft_distinguishes_three_successive_message_boundaries():
    candidate = capture()
    assert candidate.raw_first == "MODEL SECRET-device 9911 at 01:19"
    assert candidate.coordinator_result == "CORRECTED SECRET-device 9911"
    assert candidate.final_answer == "GUARDED SECRET-device 9911"
    shape = public_boundary_shape(
        candidate,
        incoming="SERIALIZER GUARDED SECRET-device 9911",
        published="trusted safe answer",
    )
    assert shape["firstNoToolsDraftCaptured"] is True
    assert shape["coordinatorResultCaptured"] is True
    assert shape["draftUnchangedAtCoordinator"] is False
    assert shape["coordinatorUnchangedAtAuthorBoundary"] is False
    assert shape["authorAnswerUnchangedAtSharedBoundary"] is False
    assert shape["publishedIsFirstModelDraft"] is False
    assert shape["rawDraftSourceClaimsAttested"] is False
    assert shape["modelProseAuthorizedForPublication"] is False
    assert shape["containsAnswerText"] is False
    for needle in ("SECRET-device", "9911", "01:19", "CORRECTED"):
        assert needle not in json.dumps(shape)
        assert needle not in repr(candidate)


def test_no_final_no_tools_provider_completion_is_not_claimed():
    token = begin_private_model_draft()
    try:
        record_coordinator_result("model-free heuristic")
        record_final_answer("model-free heuristic")
        assert private_snapshot() is None
    finally:
        reset_private_model_draft(token)
    flags = public_boundary_shape(None, incoming="cached", published="cached")
    assert flags["firstNoToolsDraftCaptured"] is False
    assert flags["publishedIsFirstModelDraft"] is False
    assert flags["draftUnchangedAtCoordinator"] is None


def test_request_context_reset_prevents_earlier_draft_attribution():
    old = capture()
    assert old is not None
    assert private_snapshot() is None
    token = begin_private_model_draft()
    try:
        record_first_no_tools_draft("new")
        assert private_snapshot().raw_first == "new"
    finally:
        reset_private_model_draft(token)


def test_parallel_requests_do_not_share_raw_drafts():
    async def worker(content):
        token = begin_private_model_draft()
        try:
            record_first_no_tools_draft(content)
            await asyncio.sleep(0)
            record_coordinator_result(content)
            record_final_answer(content)
            return private_snapshot()
        finally:
            reset_private_model_draft(token)
    a, b = asyncio.run(asyncio.gather(worker("a"), worker("b"))) if False else asyncio.run(_pair(worker))
    assert a.raw_first == "a" and b.raw_first == "b"
    assert private_snapshot() is None


async def _pair(worker):
    return await asyncio.gather(worker("a"), worker("b"))


def test_private_provenance_survives_observed_wrapper_but_never_api_serializes():
    original = AgentOutcome(
        message="untrusted model suggestion",
        request_class="live-read", evidence=[], choices=[],
        private_model_draft=capture(),
    )
    assert "SECRET-device" not in repr(original)
    observed = build_observed_agent_outcome(
        original, {"outcome": "unresolved", "counters": {}, "timings_ms": {}},
    )
    assert observed.private_model_draft.raw_first == original.private_model_draft.raw_first
    api = build_agent_response(observed, model="fixture", elapsed_ms=42,
                               version="0.18.338")
    assert "private_model_draft" not in json.dumps(api)
    assert "SECRET-device" not in json.dumps(api)


def test_telemetry_publication_exposes_only_draft_boundary_flags():
    # A typed source (including a single ID-confirmed event) exists; the
    # downstream answer must remain deterministic until claim attestation.
    evidence = [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False, "effect": "read",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": "Anonymised Relay"}},
            "summary": "1 targeted device candidates",
            "details": {"reportedDeviceState": {
                "deviceId": "9911", "label": "Anonymised Relay",
                "source": "targeted-hubitat-device-state",
                "observedAt": "2026-11-01T20:00:00+00:00",
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected"
                },
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "mutates": False, "effect": "read",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": "9911", "hoursBack": 24}},
            "details": {"observedEvents": [{
                "name": "deviceHealth", "value": "stale",
                "date": "2026-11-01T19:59:00+00:00",
                "producedBy": {"id": "9911", "type": "device"}
            }]},
        },
    ]
    base = AgentOutcome(
        message="model says physical plug is definitely ON",
        request_class="live-read", evidence=evidence, choices=[],
        private_model_draft=PrivateModelDraft(
            raw_first="model says physical plug is definitely ON",
            coordinator_result="model says physical plug is definitely ON",
            final_answer="model says physical plug is definitely ON",
            no_tools_final_stage=True,
        ),
    )
    wrapped = build_observed_agent_outcome(
        base, {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    result = apply_shared_investigation_completion(
        wrapped, "Why is Anonymised Relay offline?"
    )
    api = build_agent_response(result, model="fixture", elapsed_ms=42,
                               version="0.18.338")
    assert "physical plug is definitely ON" not in api["message"]
    shape = api["investigation_coverage"]["modelFirstDraftBoundary"]
    assert shape["firstNoToolsDraftCaptured"] is True
    assert shape["draftUnchangedAtCoordinator"] is True
    assert shape["authorAnswerUnchangedAtSharedBoundary"] is True
    assert shape["publishedIsFirstModelDraft"] is False
    assert shape["modelProseAuthorizedForPublication"] is False
    for value in ("definitely ON", "SECRET-device"):
        assert value not in json.dumps(shape)
    assert api["investigation_coverage"]["rootCauseVerified"] is False


def test_non_telemetry_or_write_route_has_no_draft_publication_side_effect():
    from shared_investigation_completion import apply_shared_investigation_completion
    original = AgentOutcome(
        message="not changed", request_class="write", evidence=[], choices=[],
        private_model_draft=capture(),
    )
    assert apply_shared_investigation_completion(original, "Turn on this light") is original

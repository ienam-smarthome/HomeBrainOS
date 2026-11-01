"""Dependency-free privacy and concurrency contract for first-model drafts."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))
from model_first_draft_provenance import (
    begin_private_model_draft, reset_private_model_draft,
    record_first_no_tools_draft, record_coordinator_result,
    record_final_answer, private_snapshot, public_boundary_shape,
)


def test_first_no_tools_provider_reply_is_distinct_from_revised_public_answer():
    token = begin_private_model_draft()
    try:
        record_first_no_tools_draft("SECRET-home 7103")
        record_first_no_tools_draft("different draft")
        record_coordinator_result("validator adjusted it")
        record_final_answer("publisher-bound answer")
        trace = private_snapshot()
        assert trace.raw_first == "SECRET-home 7103"
        flags = public_boundary_shape(
            trace, incoming="publisher-bound answer", published="trusted summary",
        )
        assert flags["firstNoToolsDraftCaptured"] is True
        assert flags["draftUnchangedAtCoordinator"] is False
        assert flags["coordinatorUnchangedAtAuthorBoundary"] is False
        assert flags["authorAnswerUnchangedAtSharedBoundary"] is True
        assert flags["publishedIsFirstModelDraft"] is False
        assert flags["rawDraftSourceClaimsAttested"] is False
        assert flags["modelProseAuthorizedForPublication"] is False
        assert flags["containsAnswerText"] is False
        assert "SECRET-home" not in repr(trace)
        assert "SECRET-home" not in json.dumps(flags)
        assert "7103" not in json.dumps(flags)
    finally:
        reset_private_model_draft(token)
    assert private_snapshot() is None


def test_no_model_draft_is_not_misattributed_to_heuristic_result():
    token = begin_private_model_draft()
    try:
        record_coordinator_result("fallback")
        record_final_answer("fallback")
        assert private_snapshot() is None
        flags = public_boundary_shape(None, incoming="fallback", published="fallback")
        assert flags["firstNoToolsDraftCaptured"] is False
        assert flags["draftUnchangedAtCoordinator"] is None
        assert flags["publishedIsFirstModelDraft"] is False
    finally:
        reset_private_model_draft(token)


def test_async_requests_have_independent_private_captures():
    async def go(name):
        token = begin_private_model_draft()
        try:
            record_first_no_tools_draft(name)
            await asyncio.sleep(0)
            record_coordinator_result(name)
            record_final_answer(name)
            return private_snapshot()
        finally:
            reset_private_model_draft(token)
    async def gather():
        return await asyncio.gather(go("first"), go("second"))
    first, second = asyncio.run(gather())
    assert first.raw_first == "first"
    assert second.raw_first == "second"
    assert private_snapshot() is None

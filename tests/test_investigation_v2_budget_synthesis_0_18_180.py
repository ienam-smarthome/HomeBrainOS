"""A source-backed read-budget exit must not perform extra AI synthesis."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.evaluate import evaluate_v2_with_model
from test_investigation_v2_incident_first_summary_0_18_179 import fixture


class ReadOnlyMCP:
    async def list_tools(self):
        return []


class NeverExecute:
    def __init__(self, mcp):
        self.mcp = mcp
    async def execute(self, *args, **kwargs):
        raise AssertionError("No Hubitat read/write tool call expected")


@pytest.mark.asyncio
async def test_source_budget_exit_bypasses_all_additional_model_calls():
    receipts, _ = fixture()
    mcp = ReadOnlyMCP()
    model_calls = []
    async def model(*args, **kwargs):
        model_calls.append(True)
        raise AssertionError("No planning, atomic or narrative model call expected")
    outcome = await evaluate_v2_with_model(
        explicitly_authorised=True,
        question="Investigate why Livingroom Light 2 turned OFF most recently.",
        chat=model, mcp=mcp, executor=NeverExecute(mcp),
        verified_entity_ids=("7828",), initial_receipts=receipts,
        bootstrap_source_identity=True,
        max_total_reads=0, max_rounds=1,
        enable_atomic_claim_validation=True,
        enable_evidence_narrative=True,
    )
    assert outcome.investigation.stopped_because == "source_backed_read_budget_reached"
    assert model_calls == []
    assert outcome.atomic_claim_review is None
    assert outcome.narrative_audit is None
    assert "56.387 seconds" in outcome.report
    assert "243 ms" in outcome.report
    assert "source_backed_read_budget_reached" in outcome.answer.validation_issues

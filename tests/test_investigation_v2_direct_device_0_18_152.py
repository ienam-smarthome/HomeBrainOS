"""V2 .152: source identity drives a direct investigation, not AI word routing.

Synthetic case files and fake executor only. No network, Hubitat writes or
model API calls are allowed in these regressions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from mcp_client import MCPToolResult
from investigation_v2.evidence import build_case_file
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.read_loop import Hypothesis, InvestigationResult
from investigation_v2.evaluate import evaluate_v2_with_model
import investigation_v2.evaluate as evaluation


@pytest.mark.asyncio
async def test_no_new_evidence_skips_atomic_and_displays_every_issued_command(monkeypatch):
    arguments = {"tool": "hub_list_device_events",
                 "args": {"deviceId": "7103", "limit": 50}}
    receipt = project_read_receipt(
        "hub_read_devices", arguments,
        MCPToolResult(
            "hub_read_devices", arguments, raw={},
            text="UNTRUSTED SECRET", is_error=False,
            data={"deviceId": "7103", "events": [{
                "deviceId": "7103",
                "name": "command-on",
                "type": "command",
                "date": "2026-10-24T20:51:12+00:00",
                "producedBy": {"id": "3103"},
            }]},
        ), source_request_id="rodret",
    )
    case = build_case_file("Investigate Bedroom 3 Mesh", [receipt])
    assert len(case.records) == 1
    h = Hypothesis(
        hypothesis_id="h1",
        explanation="The plug is physically online because MQTT is connected",
        supporting_record_ids=(case.records[0].record_id,),
        conflicting_record_ids=(),
        missing_discriminator="Physical reachability",
        assessment="supported_candidate",
    )
    simulated = InvestigationResult(
        case=case, hypotheses=[h], rounds=1, executed_reads=2,
        stopped_because="no_new_usable_evidence",
    )

    class MCP:
        async def list_tools(self):
            return []
    mcp = MCP()

    class Executor:
        def __init__(self, m):
            self.mcp = m
    executor = Executor(mcp)

    async def fake_run(**kwargs):
        assert kwargs["verified_entity_ids"] == ("7103",)
        return simulated

    async def must_not_call_model(*args, **kwargs):
        raise AssertionError("No model planning, claim repair or narrative call")

    monkeypatch.setattr(evaluation, "run_read_only_investigation", fake_run)
    outcome = await evaluate_v2_with_model(
        explicitly_authorised=True, question="Investigate Bedroom 3 Mesh",
        chat=must_not_call_model, mcp=mcp, executor=executor,
        verified_entity_ids=("7103",), enable_atomic_claim_validation=True,
        enable_evidence_narrative=True,
    )
    assert "command-on" in outcome.answer.text
    assert "The plug is physically online" not in outcome.answer.text
    assert "model_hypotheses_unverified" in outcome.answer.validation_issues
    assert outcome.atomic_claim_review is None
    assert outcome.narrative_audit is None
    assert outcome.answer.root_cause_verified is False
    assert "UNTRUSTED SECRET" not in json.dumps(outcome.to_dict())


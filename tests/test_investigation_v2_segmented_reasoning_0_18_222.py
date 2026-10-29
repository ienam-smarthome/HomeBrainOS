"""Reasoning V2: independently gate facts and narrative segments.

These are regression checks for a GENERAL response contract, not named-device
production rules. No external model, MCP endpoint or Hubitat write is used.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_claim_verifier import (
    validate_claims, publish_verified_claims,
)
from investigation_v2.native_verified_prose import verify_model_explanation


CATALOG = [
    {
        "id": "claim-1",
        "kind": "device_observation",
        "statement": "Device 9001 source-reported healthStatus=offline at this read.",
        "evidence_reads": [2],
        "root_cause_verified": False,
        "metric": "healthStatus",
        "scope": "9001",
    },
    {
        "id": "claim-2",
        "kind": "warning",
        "statement": "A bounded hub log returned two WARN entries for device 9001.",
        "evidence_reads": [1],
        "root_cause_verified": False,
        "scope": "9001",
    },
]
CASE = {
    "source_id": "9001",
    "name": "Sample outlet",
    "warning_rows_in_returned_sample": 2,
    "warning_levels": ["WARN"],
    "status": {"healthStatus": "offline"},
    "evidence_reads": [1, 2],
}
GOOD = {
    "source_id": "9001",
    "explanation": (
        "Sample outlet has 2 WARN rows and healthStatus=offline "
        "in the reported readings; this is worth checking."
    ),
    "next_check": "Review the device logs and inspect recent activity.",
}


def test_optional_narrative_does_not_erase_verified_claims():
    proposed = {"claims": [{"fact_id": "claim-1"}, {"fact_id": "claim-2"}],
                "findings": [GOOD]}
    result = validate_claims(proposed, CATALOG)
    assert result["status"] == "validated"
    assert len(result["accepted"]) == 2
    published = publish_verified_claims(proposed, CATALOG)
    assert published["fallback"] is False
    assert "healthStatus=offline" in published["text"]
    assert "two WARN entries" in published["text"]
    assert "this is worth checking" not in published["text"]
    assert published["model_prose_published"] is False


@pytest.mark.parametrize("findings", [
    None,
    "malformed",
    [{"source_id": "9001", "explanation": "power was cut"}],
    [{"source_id": "9999", "explanation": "unverified"}],
])
def test_narrative_contract_failure_cannot_invalidate_independent_facts(findings):
    facts = validate_claims(
        {"claims": [{"fact_id": "claim-2"}], "findings": findings}, CATALOG)
    assert facts["status"] == "validated"
    assert len(facts["accepted"]) == 1


def test_injected_top_level_claim_authority_remains_rejected():
    response = validate_claims(
        {"claims": [{"fact_id": "claim-1"}], "root_cause": "power cut"},
        CATALOG,
    )
    assert not response["accepted"]
    assert "unrecognised_top_level_fields" in response["rejected"]


def test_missing_claims_is_not_authorised_by_valid_narrative():
    result = validate_claims({"findings": [GOOD]}, CATALOG)
    assert result["accepted"] == []
    assert result["status"] == "unverified"


def test_invalid_segment_does_not_erase_independent_valid_segment():
    unsupported = {
        **GOOD,
        "explanation": "Sample outlet definitely failed because power was cut.",
    }
    result = verify_model_explanation(
        {"findings": [unsupported, GOOD]}, [CASE])
    assert result["accepted"] is True
    assert result["reason"] == "partially_verified"
    assert result["verified_subject_ids"] == ["9001"]
    assert result["rejected_segments"] == [
        {"index": 0, "reason": "unsupported_language"}]
    assert "Sample outlet has 2 WARN rows" in result["text"]
    assert "power was cut" not in result["text"]
    assert "withheld" in result["text"]


def test_invalid_second_segment_does_not_erase_first():
    invented = {**GOOD, "source_id": "9999"}
    result = verify_model_explanation({"findings": [GOOD, invented]}, [CASE])
    assert result["accepted"] is True
    assert result["verified_subject_ids"] == ["9001"]
    assert result["rejected_segments"] == [
        {"index": 1, "reason": "unverified_subject"}]


def test_no_unverified_narrative_leaks_when_all_segments_bad():
    bad = {**GOOD, "next_check": "Restart the hub and turn off protection."}
    result = verify_model_explanation({"findings": [bad]}, [CASE])
    assert result["accepted"] is False
    assert "text" not in result
    assert result["rejected_segments"][0]["reason"] == "unsupported_language"


def test_missing_evidence_receipts_cannot_authorise_a_narrative():
    case = {**CASE, "evidence_reads": ["not-a-read"]}
    result = verify_model_explanation({"findings": [GOOD]}, [case])
    assert result["accepted"] is False
    assert result["reason"] == "unverified_read_references"


def test_over_budget_findings_are_rejected_before_partial_processing():
    result = verify_model_explanation({"findings": [GOOD] * 4}, [CASE])
    assert result["accepted"] is False
    assert result["reason"] == "invalid_findings"


@pytest.mark.asyncio
async def test_native_model_combined_response_keeps_claims_and_valid_narrative():
    """The model makes two actual guarded fake READs and returns one JSON answer."""
    import json
    from investigation_v2.native_read_agent import run_native_read_agent
    from test_investigation_v2_single_pass_model_explanations_0_18_216 import (
        _tools, _results, _draft,
    )
    from test_investigation_v2_native_read_agent_0_18_181 import call
    from test_investigation_v2_verified_focus_0_18_204 import _call

    mcp = _tools()
    executor = __import__(
        "test_investigation_v2_native_read_agent_0_18_181"
    ).FakeExecutor(mcp, _results())
    count = 0

    async def model(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return {"tool_calls": [call(
                "hub_get_logs", mode="past", level="warn", limit=100)]}
        if count == 2:
            return {"tool_calls": [_call(
                "hub_read_devices", "hub_get_device", deviceId="9001")]}
        return {"content": json.dumps({
            "claims": [{"fact_id": "claim-1"}],
            "findings": [{
                **_draft()["findings"][0],
                "explanation": "Sample outlet definitely failed due to a power cut.",
            }, _draft()["findings"][0]],
        })}

    result = await run_native_read_agent(
        question="Investigate unusual warnings and explain what is known.",
        chat=model, mcp=mcp, executor=executor,
        max_rounds=3, max_reads=4, enable_verified_narrative=True,
    )
    assert len(executor.calls) == 2
    assert result["native_diagnostics"]["claim_publication"]["status"] == "validated"
    assert result["native_diagnostics"]["verified_narrative_accepted"] is True
    assert "Sample outlet has 2 WARN rows" in result["answer"]["text"]
    assert "power cut" not in result["answer"]["text"]

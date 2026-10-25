"""Phase D: claim-by-claim source proof, targeted revision, no erasure.

All tests run with fixture replay or mocked ChatTransport, never a real hub.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2 import build_case_file
from investigation_v2.atomic_claims import (
    apply_targeted_repair, review_atomic_claims, synthesize_atomic_with_chat,
)
from investigation_v2.read_loop import Hypothesis
from investigation_v2.evaluate import evaluate_v2_with_model
from mcp_client import MCPTool

FIXTURE = Path(__file__).parent / "fixtures" / "investigation_v2_overnight.json"


def overnight():
    obj = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return build_case_file(obj["question"], obj["receipts"])


def claim(row, ident="c1"):
    return {
        "id": ident, "kind": "observation", "record_id": row.record_id,
        "expected": {name: getattr(row, name) for name in (
            "stage", "action", "value", "target_id", "producer_id",
            "timestamp_utc", "time_basis")},
    }


def hypothesis(case):
    item = next(r for r in case.records if r.action == "command-off")
    return Hypothesis("h1", "The OFF command may not have taken effect",
                      (item.record_id,), (),
                      "Check independently reported switch state around the OFF.",
                      "supported_candidate")


def primary(case):
    return next(r for r in case.records if
                r.action == "command-off" and r.producer_id == "4246")


def test_exact_typed_command_and_level_state_validate_without_physical_inference():
    case = overnight()
    off = primary(case)
    level = next(r for r in case.records if r.action == "level")
    r = review_atomic_claims(case, [], [claim(off), claim(level, "c2")])
    assert not r.rejected
    assert {x.record_id for x in r.accepted} == {off.record_id, level.record_id}
    assert off.stage == "command_issued"
    assert level.stage == "state_reported"
    assert len(r.missing_material_record_ids) == 5


@pytest.mark.parametrize("changed,wrong", [
    ("stage", "state_reported"), ("action", "switch"),
    ("value", "off"), ("target_id", "9999"),
    ("producer_id", "4019"), ("timestamp_utc", "2026-10-25T00:41:40Z"),
    ("time_basis", "read_observed_at"),
])
def test_atomic_claim_rejects_exact_field_mismatch(changed, wrong):
    case = overnight()
    c = claim(primary(case))
    c["expected"][changed] = wrong
    reviewed = review_atomic_claims(case, [], [c])
    assert len(reviewed.rejected) == 1
    assert reviewed.rejected[0].reason == "mismatched_" + changed
    assert not reviewed.accepted


def test_no_made_up_source_or_repeated_claim_id():
    case = overnight()
    good = claim(primary(case))
    invalid = claim(primary(case), "c2")
    invalid["record_id"] = "fabricated"
    duplicate = claim(case.records[0], "c1")
    result = review_atomic_claims(case, [], [good, invalid, duplicate])
    assert len(result.accepted) == 1
    assert [x.reason for x in result.rejected] == [
        "unverified_record_id", "duplicate_claim_id"]


def test_extra_prose_fields_cannot_become_verified_fact_or_leak():
    case = overnight()
    bad = claim(primary(case))
    bad["cause"] = "PRIVATE_SECRET hub reboot caused everything"
    verdict = review_atomic_claims(case, [], [bad])
    assert verdict.rejected[0].reason == "invalid_observation_shape"
    assert "PRIVATE_SECRET" not in json.dumps(verdict.to_dict())


def test_hypothesis_supported_as_tentative_only_not_a_confirmed_cause():
    case = overnight()
    h = hypothesis(case)
    r = review_atomic_claims(case, [h], [
        {"id": "hclaim", "kind": "hypothesis", "hypothesis_id": "h1"}])
    assert r.accepted[0].kind == "hypothesis"
    assert r.accepted[0].record_id is None
    assert r.accepted[0].hypothesis_id == "h1"
    unsupported = Hypothesis("h2", "Reboot definitely happened", (), (),
                             "Find proof", "unsubstantiated_candidate")
    r = review_atomic_claims(case, [unsupported], [
        {"id": "hclaim", "kind": "hypothesis", "hypothesis_id": "h2"}])
    assert r.rejected[0].reason == "no_hypothesis_evidence"


def test_invalid_claim_batch_fails_without_dropping_history():
    case = overnight()
    r = review_atomic_claims(case, [], "cause proven")
    assert r.rejected[0].reason == "invalid_claim_batch"
    assert len(r.missing_material_record_ids) == 6


def test_targeted_repair_can_fix_only_rejected_slot():
    case = overnight()
    off = primary(case)
    lvl = next(r for r in case.records if r.stage == "state_reported")
    good = claim(off, "approved")
    wrong = claim(lvl, "repair_me")
    wrong["expected"]["stage"] = "command_issued"
    first = review_atomic_claims(case, [], [good, wrong])
    assert len(first.accepted) == 1 and len(first.rejected) == 1

    # Model tries to change an APPROVED record in the same revision;
    # the host ignores it and keeps the exact original accepted object.
    replacement = claim(lvl, "repair_me")
    attempt = claim(lvl, "approved")
    merged = apply_targeted_repair(case, [], first, [replacement, attempt])
    assert merged.repair_attempted is True
    assert len(merged.accepted) == 2
    assert merged.accepted[0] == first.accepted[0]
    assert merged.accepted[1].record_id == lvl.record_id
    assert any(x.reason == "repair_not_authorized_for_claim_id"
               for x in merged.rejected)


def test_repair_unknown_id_never_adds_new_claim():
    case = overnight()
    wrong = claim(primary(case))
    wrong["expected"]["stage"] = "state_reported"
    first = review_atomic_claims(case, [], [wrong])
    second = apply_targeted_repair(case, [], first, [
        claim(primary(case), "brand_new")])
    assert not second.accepted
    assert any(x.reason == "repair_not_authorized_for_claim_id"
               for x in second.rejected)


@pytest.mark.asyncio
async def test_model_two_turn_atomic_revision_preserves_every_incident_command():
    case = overnight()
    off = primary(case)
    level = next(r for r in case.records if r.action == "level")
    first_good = claim(off, "good")
    first_wrong = claim(level, "bad")
    first_wrong["expected"]["stage"] = "command_issued"
    calls = []
    async def fake_chat(messages, tools):
        calls.append((messages, tools))
        if len(calls) == 1:
            return {"content": json.dumps({"claims": [first_good, first_wrong]})}
        assert "bad" in messages[-1]["content"]
        assert "good" in messages[-1]["content"]
        return {"content": json.dumps({"replacements": [claim(level, "bad")]})}

    out = await synthesize_atomic_with_chat(
        case=case, hypotheses=[hypothesis(case)], chat=fake_chat)
    assert len(calls) == 2
    assert all(x[1] == [] for x in calls)
    assert out.review.repair_attempted
    assert len(out.review.accepted) == 2
    assert not out.review.rejected
    assert out.review.accepted[0].claim_id == "good"
    assert out.answer.root_cause_verified is False
    assert "00:41:40.085+01:00" in out.answer.text
    assert "00:49:52.008+01:00" in out.answer.text
    assert "01:09:41.597+01:00" in out.answer.text
    assert "atomic_targeted_repair_attempted" in out.answer.validation_issues


@pytest.mark.asyncio
async def test_failed_repair_does_not_erase_initial_verified_facts():
    case = overnight()
    correct = claim(primary(case), "good")
    wrong = claim(primary(case), "wrong")
    wrong["expected"]["producer_id"] = "7988"
    rounds = 0
    async def fake_chat(_messages, _tools):
        nonlocal rounds
        rounds += 1
        if rounds == 1:
            return {"content": json.dumps({"claims": [correct, wrong]})}
        return {"content": "hub reboot proved!"}
    out = await synthesize_atomic_with_chat(
        case=case, hypotheses=[], chat=fake_chat)
    assert rounds == 2
    assert out.review.repair_attempted
    assert [x.claim_id for x in out.review.accepted] == ["good"]
    assert "hub reboot proved" not in out.answer.text
    assert len(out.review.rejected) == 1


@pytest.mark.asyncio
async def test_model_native_tool_call_refused_with_lossless_command_fallback():
    case = overnight()
    async def malicious(_messages, _tools):
        return {
            "content": json.dumps({"claims": []}),
            "tool_calls": [{"function": {"name": "hub_manage_devices",
                                          "arguments": {"command": "off"}}}],
        }
    out = await synthesize_atomic_with_chat(
        case=case, hypotheses=[], chat=malicious)
    assert not out.review.accepted
    assert "00:41:40.085+01:00" in out.answer.text
    assert len(out.answer.displayed_record_ids) >= 6


@pytest.mark.asyncio
async def test_no_unbounded_repair_when_disabled():
    case = overnight()
    count = 0
    invalid = claim(primary(case))
    invalid["expected"]["stage"] = "independent_physical_observation"
    async def fake_chat(_messages, _tools):
        nonlocal count
        count += 1
        return {"content": json.dumps({"claims": [invalid]})}
    out = await synthesize_atomic_with_chat(
        case=case, hypotheses=[], chat=fake_chat, max_repair_rounds=0)
    assert count == 1
    assert not out.review.repair_attempted
    assert out.review.rejected[0].reason == "mismatched_stage"


@pytest.mark.asyncio
async def test_evaluation_atomic_mode_explicit_and_production_stays_unmodified():
    class MCP:
        async def list_tools(self):
            return []
    class Executor:
        def __init__(self, mcp):
            self.mcp = mcp
        async def execute(self, *_a, **_k):
            raise AssertionError("No MCP reads were approved")
    mcp = MCP()
    prompts = []
    data = overnight()
    single = claim(primary(data))
    async def chat(messages, tools):
        prompts.append(messages)
        assert tools == []
        if len(prompts) == 1:
            return {"content": json.dumps({
                "hypotheses": [], "reads": [], "finish": True})}
        return {"content": json.dumps({"claims": [single]})}
    f = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = await evaluate_v2_with_model(
        explicitly_authorised=True, question=f["question"],
        chat=chat, mcp=mcp, executor=Executor(mcp),
        verified_entity_ids={"7805"}, initial_receipts=f["receipts"],
        enable_atomic_claim_validation=True,
    )
    assert len(prompts) == 2
    assert result.atomic_claim_review is not None
    assert result.atomic_claim_review.accepted[0].claim_id == "c1"
    assert result.to_dict()["production_answer_used"] is False
    assert result.to_dict()["atomic_claim_review"]["repair_attempted"] is False
    assert result.answer.human_review_required is True


def test_other_domain_observations_use_same_claim_validator():
    receipt = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "mutates": False, "effect": "read",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "7103"}},
        "details": {"events": [{
            "name": "mqttStatus", "value": "disconnected",
            "date": "2026-10-25T21:00:00Z", "deviceId": "7103"}]},
    }
    case = build_case_file("Why did MQTT stop reporting?", [receipt])
    assert len(case.records) == 1
    accepted = review_atomic_claims(case, [], [claim(case.records[0])])
    assert len(accepted.accepted) == 1
    # A message about the same timestamp cannot be falsely promoted
    # to a command or known control-source execution.
    bogus = claim(case.records[0])
    bogus["expected"]["stage"] = "app_execution_observed"
    assert review_atomic_claims(case, [], [bogus]).rejected[0].reason == "mismatched_stage"


def test_unknown_source_completeness_cannot_be_fabricated_by_extra_field():
    case = overnight()
    c = claim(primary(case))
    c["source_complete"] = True
    assert review_atomic_claims(case, [], [c]).rejected[0].reason == "invalid_observation_shape"
    assert case.coverage[0].source_complete is False

@pytest.mark.asyncio
async def test_rejected_hypothesis_is_not_printed_as_even_a_tentative_cause():
    case = overnight()
    bad = Hypothesis("bad", "SECRET_LEAK a reboot definitely caused it",
                     (), (), "Check reboot evidence", "unsubstantiated_candidate")
    async def proposer(_messages, tools):
        assert tools == []
        return {"content": json.dumps({"claims": [
            {"id": "h_bad", "kind": "hypothesis", "hypothesis_id": "bad"}]})}
    out = await synthesize_atomic_with_chat(
        case=case, hypotheses=[bad], chat=proposer, max_repair_rounds=0)
    assert out.review.rejected[0].reason == "no_hypothesis_evidence"
    assert "SECRET_LEAK" not in out.answer.text
    assert "00:41:40.085+01:00" in out.answer.text


@pytest.mark.asyncio
async def test_unselected_plausible_hypothesis_does_not_force_itself_into_answer():
    case = overnight()
    plausible = hypothesis(case)
    async def proposer(_messages, tools):
        assert tools == []
        return {"content": json.dumps({"claims": [claim(primary(case))]})}
    out = await synthesize_atomic_with_chat(
        case=case, hypotheses=[plausible], chat=proposer)
    assert "The OFF command may not have taken effect" not in out.answer.text
    assert out.review.rejected == ()
    assert out.answer.root_cause_verified is False

"""Evidence narrative and honest replay metrics; mocked model only."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2 import build_case_file
from investigation_v2.atomic_claims import synthesize_atomic_with_chat
from investigation_v2.narrative import review_links, render_evidence_narrative
from investigation_v2.replay_scorecard import replay_scorecard, score_grounded_replay
from investigation_v2.synthesis import assemble_grounded_answer
from investigation_v2.evaluate import evaluate_v2_with_model

FIXTURE = Path(__file__).parent / "fixtures" / "investigation_v2_overnight.json"


def case():
    f = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return build_case_file(f["question"], f["receipts"])


def pair(before, after, relation="later_command"):
    return {"earlier_id": before.record_id, "later_id": after.record_id,
            "relation": relation}


def source_links(data):
    commands = [x for x in data.records if x.stage == "command_issued"]
    first = next(x for x in commands if x.action == "command-off"
                 and x.producer_id == "4246")
    later = next(x for x in commands if x.action == "command-setLevel"
                 and x.timestamp_original.startswith("2026-10-25T00:49"))
    return first, later


def test_source_backed_timeline_connects_night_off_and_later_setlevel():
    data = case()
    off, later = source_links(data)
    answer = assemble_grounded_answer(data, [], {})
    enhanced, audit = render_evidence_narrative(
        data, answer, [pair(off, later)])
    assert len(audit.approved) == 1 and not audit.rejected
    assert not audit.used_fallback
    assert "00:41:40.085+01:00" in enhanced.text
    assert "00:49:52.008+01:00" in enhanced.text
    assert "order of commands, not that either changed the device state" in enhanced.text
    assert "do not independently establish a root cause" in enhanced.text
    assert len(enhanced.displayed_record_ids) == 8
    assert enhanced.root_cause_verified is False


@pytest.mark.parametrize("mutate,reason", [
    (lambda p: {**p, "earlier_id": "not-a-record"}, "unknown_record_reference"),
    (lambda p: {**p, "earlier_id": p["later_id"], "later_id": p["earlier_id"]},
     "invalid_utc_chronology"),
    (lambda p: {**p, "relation": "physically_switched_off"}, "unsupported_link_relation"),
])
def test_unsafe_or_noncausal_pair_refused(mutate, reason):
    data = case()
    off, later = source_links(data)
    result = review_links(data, [mutate(pair(off, later))])
    assert not result.approved
    assert result.rejected[0].reason == reason


def test_wrong_stage_report_does_not_become_proof_of_command_success():
    data = case()
    off, later = source_links(data)
    result = review_links(data, [pair(off, later, "later_report")])
    assert result.rejected[0].reason == "report_relation_stage_mismatch"


def test_model_pair_from_different_devices_is_rejected_even_when_ordered():
    data = case()
    separate = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "mutates": False, "effect": "read", "success": True,
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "7103"}},
        "details": {"deviceId": "7103", "events": [
            {"name": "mqttStatus", "value": "disconnected",
             "date": "2026-10-25T01:00:00+00:00"}]},
    }
    obj = json.loads(FIXTURE.read_text(encoding="utf-8"))
    combined = build_case_file(obj["question"], [*obj["receipts"], separate])
    off, _ = source_links(combined)
    mqtt = next(x for x in combined.records if x.target_id == "7103")
    result = review_links(combined, [pair(off, mqtt, "later_report")])
    assert result.rejected[0].reason == "unverified_same_target"


def test_utc_order_overrides_repeated_bst_gmt_wall_clock():
    receipts = [
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "mutates": False, "effect": "read",
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": "7001"}},
         "details": {"events": [
             {"name": "command-on", "type": "command",
              "date": "2026-10-25T01:50:00+01:00"},
             {"name": "command-off", "type": "command",
              "date": "2026-10-25T01:20:00+00:00"},
         ]}},
    ]
    data = build_case_file("Check repeated hour", receipts)
    assert len(data.records) == 2
    assert data.records[0].action == "command-on"
    valid = review_links(data, [pair(data.records[0], data.records[1])])
    assert len(valid.approved) == 1
    reversed_clock = review_links(data, [pair(data.records[1], data.records[0])])
    assert reversed_clock.rejected[0].reason == "invalid_utc_chronology"


@pytest.mark.asyncio
async def test_atomic_model_output_can_choose_verified_narrative_in_single_round():
    data = case()
    before, after = source_links(data)
    responses = []
    async def chat(messages, tools):
        responses.append((messages, tools))
        return {"content": json.dumps({
            "claims": [],
            "narrative_links": [pair(before, after)]})}
    output = await synthesize_atomic_with_chat(
        case=data, hypotheses=[], chat=chat, enable_evidence_narrative=True)
    assert len(responses) == 1
    assert responses[0][1] == []
    assert len(output.narrative_audit.approved) == 1
    assert "issued command" in output.answer.text.lower() or "an issued" in output.answer.text.lower()
    assert "00:49:52.008+01:00" in output.answer.text


@pytest.mark.asyncio
async def test_malformed_model_narrative_never_erases_atomic_grounding():
    data = case()
    async def chat(_messages, tools):
        assert tools == []
        return {"content": "unsupported assertion: hub failure confirmed"}
    output = await synthesize_atomic_with_chat(
        case=data, hypotheses=[], chat=chat, enable_evidence_narrative=True)
    assert output.narrative_audit.used_fallback
    assert "00:41:40.085+01:00" in output.answer.text
    assert "hub failure confirmed" not in output.answer.text


def test_replay_metrics_are_measurements_not_fake_comparisons():
    data = case()
    answer = assemble_grounded_answer(data, [], {})
    score = replay_scorecard(data, answer)
    assert score["v2_measured"]["command_records"] == 6
    assert score["v2_measured"]["commands_retained"] == 6
    assert score["v2_measured"]["command_source_clock_mentions"] == 6
    assert score["v2_measured"]["command_id_mentions"] == 6
    assert score["v2_measured"]["command_retention_fraction"] == 1.0
    assert score["v2_measured"]["states_retained"] == 2
    assert score["v2_measured"]["source_complete_proven"] is False
    assert score["v1_external"]["provided"] is False
    assert score["v1_external"]["commands_with_exact_source_clock_mention"] is None
    assert score["reference_external"]["provided"] is False
    assert score["causal_accuracy_comparison_completed"] is False


def test_reference_text_counts_only_literal_clocks_not_claims_of_quality():
    data = case()
    rendered = assemble_grounded_answer(data, [], {})
    raw = "At 2026-10-25T00:41:40.085+01:00 the hub reboot definitely caused it."
    score = replay_scorecard(data, rendered, existing_v1_answer=raw)
    assert score["v1_external"]["provided"] is True
    assert score["v1_external"]["commands_with_exact_source_clock_mention"] == 1
    assert score["external_text_scores_are_semantic"] is False


def test_benchmark_never_drops_source_commands_due_to_rejected_model_links():
    data = case()
    answer = assemble_grounded_answer(data, [], {})
    enhanced, audit = render_evidence_narrative(
        data, answer, [{"earlier_id": "made-up", "later_id": "another",
                        "relation": "later_command"}])
    score = score_grounded_replay(data, enhanced)
    assert len(audit.rejected) == 1
    assert audit.used_fallback
    assert score.commands_retained == 6
    assert score.invalid_citations == 0
    assert "unsupported_narrative_link" in score.validator_flags


@pytest.mark.asyncio
async def test_evaluation_rejects_narrative_without_atomic_gate_before_mcp_discovery():
    class MCP:
        async def list_tools(self):
            raise AssertionError("No remote discovery without valid feature gate")
    class Executor:
        def __init__(self, mcp):
            self.mcp = mcp
    async def chat(_messages, _tools):
        raise AssertionError("No model call")
    mcp = MCP()
    with pytest.raises(ValueError, match="requires atomic"):
        await evaluate_v2_with_model(
            explicitly_authorised=True, question="Why?",
            chat=chat, mcp=mcp, executor=Executor(mcp),
            verified_entity_ids={"7805"},
            enable_evidence_narrative=True)

def test_replay_does_not_equate_metadata_citations_with_visible_evidence():
    from dataclasses import replace
    data = case()
    answer = assemble_grounded_answer(data, [], {})
    metadata_only = replace(answer, text="No evidence was checked.")
    score = score_grounded_replay(data, metadata_only)
    assert score.commands_retained == 6
    assert score.command_source_clock_mentions == 0
    assert score.command_id_mentions == 0


def test_no_commands_does_not_report_100_percent_recall():
    receipt = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": {"deviceId": "7103"}},
        "details": {"events": [{"name": "mqttStatus", "value": "connected",
                                "date": "2026-10-25T21:00:00Z"}]},
    }
    data = build_case_file("Read MQTT state", [receipt])
    result = score_grounded_replay(data, assemble_grounded_answer(data, [], {}))
    assert result.command_records == 0
    assert result.command_retention_fraction is None

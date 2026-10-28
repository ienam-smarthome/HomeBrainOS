"""Cross-provider causal evidence primitives and replay golden acceptance.

No live Hubitat, cloud provider, implicit write grant or benchmark-specific
production router. Reference-only claims cannot enter canonical case records.
"""
from __future__ import annotations
from copy import deepcopy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai" / "rootfs" / "app"))
sys.path.insert(0, str(ROOT))

from investigation_v2.evidence import build_case_file
from investigation_v2.causal_evidence import (
    causal_evidence_bundle, command_state_pairs, command_history_coverage,
)
from investigation_v2.planning_evidence import planning_evidence
from scripts.run_v2_golden_suite import replay_fixture, FIXTURES


def loaded():
    data=json.loads(FIXTURES[0].read_text(encoding="utf-8"))
    return data, build_case_file(data["question"], data["receipts"])


def test_golden_replay_retains_command_and_never_promotes_reporter_to_issuer():
    data, case=loaded()
    command=next(r for r in case.records
                 if r.stage=="command_issued" and r.action=="command-off")
    state=next(r for r in case.records
               if r.stage=="state_reported" and r.action=="switch"
               and r.value=="off")
    assert command.producer_id=="4020"
    assert state.producer_id=="7790"
    assert command.target_id==state.target_id=="7828"
    links=command_state_pairs(case)
    match=next(p for p in links if p.command_record_id==command.record_id)
    assert match.state_record_id==state.record_id
    assert match.interval_ms==243
    assert match.issuer_app_id=="4020"
    assert match.state_reporter_id=="7790"
    assert match.physical_action_verified is False
    assert match.internal_rule_decision_verified is False
    assert all(r.target_id=="7828" for r in case.records)
    assert not any("FP400" in str(r) for r in case.records)
    assert all(c.source_complete is not True for c in case.coverage)


def test_switch_only_history_is_not_negative_command_evidence():
    data,_=loaded()
    case=build_case_file(data["question"], data["receipts"][:1])
    scope=command_history_coverage(case,"7828")
    assert scope["observed_command_records"]==0
    assert scope["no_command_proven"] is False
    assert "command_events_excluded_by_filter" in scope["issues"]
    assert "unfiltered_command_history_not_observed" in scope["issues"]
    assert not command_state_pairs(case)


def test_unfiltered_history_is_sampled_not_claimed_complete():
    _,case=loaded()
    scope=command_history_coverage(case,"7828")
    assert scope["observed_command_records"]>=1
    assert "command_history_source_completeness_unverified" in scope["issues"]
    assert "command_events_excluded_by_filter" not in scope["issues"]
    assert scope["unfiltered_source_complete"] is False


@pytest.mark.parametrize("mutate", [
    lambda c: c["receipts"][1]["details"]["events"][1].update(
        deviceId="9999"),
    lambda c: c["receipts"][1]["details"]["events"][1].update(
        date="2026-10-28T00:14:59+00:00"),
    lambda c: c["receipts"][1]["details"]["events"][1].update(
        name="command-on"),
    lambda c: c["receipts"][1]["details"]["events"][1].update(
        producedBy={"id":"7790"}),
])
def test_invalid_wrong_device_reverse_clock_action_or_issuer_cannot_pass_golden(mutate):
    d,_=loaded()
    mutate(d)
    case=build_case_file(d["question"],d["receipts"])
    evidence=causal_evidence_bundle(case,"7828")
    expected=d["expected_pair"]
    assert not any(
        r["issuer_app_id"]==expected["issuer_app_id"]
        and r["state_reporter_id"]==expected["state_reporter_id"]
        and r["interval_ms"]==expected["interval_ms"]
        for r in evidence["command_state_pairs"])


def test_planner_receives_typed_links_and_uncertainty_without_new_source_calls():
    _,case=loaded()
    view=json.loads(planning_evidence(case,None))
    pairs=view["command_state_pairs"]
    assert any(p["interval_ms"]==243 and p["issuer_app_id"]=="4020"
               and p["state_reporter_id"]=="7790" for p in pairs)
    assert all(not p["physical_action_verified"] for p in pairs)
    assert all(not p["internal_rule_decision_verified"] for p in pairs)
    assert any("command_history_source_completeness_unverified" in c["issues"]
               for c in view["command_history_coverage"])
    assert all("raw_references" not in p for p in pairs)


def test_golden_suite_runner_reports_structural_success_not_hub_or_model_proof():
    result=replay_fixture(FIXTURES[0])
    assert result["replay_structural_gate_passed"] is True
    assert result["live_hub_claims_verified"] is False
    assert result["llm_explanation_quality_evaluated"] is False
    assert result["reference_only_facts_unverified"]>=4
    assert result["command_report_temporal_pair_in_fixture"] is True


def test_no_network_golden_cli_returns_machine_readable_gate():
    cli=ROOT/"scripts"/"run_v2_golden_suite.py"
    completed=subprocess.run([sys.executable,str(cli)],capture_output=True,
                             text=True,timeout=15,check=False)
    assert completed.returncode==0,completed.stderr
    report=json.loads(completed.stdout)
    assert report["golden_replays"][0]["replay_structural_gate_passed"]
    assert not report["golden_replays"][0]["live_hub_claims_verified"]


def test_golden_replay_is_safely_confined_to_reviewed_versioned_fixtures(tmp_path):
    other=tmp_path/"attacker.json"
    other.write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError,match="version-controlled"):
        replay_fixture(other)


def test_command_pair_does_not_reuse_same_state_for_multiple_commands():
    d,_=loaded()
    command=d["receipts"][1]["details"]["events"][1]
    prior=deepcopy(command)
    prior["date"]="2026-10-28T00:14:56.700+00:00"
    d["receipts"][1]["details"]["events"].insert(1,prior)
    case=build_case_file(d["question"],d["receipts"])
    matches=[p for p in command_state_pairs(case)
             if p.state_utc.startswith("2026-10-28T00:14:57")]
    assert len(matches)==1


def test_unverified_sensor_config_and_reboot_claims_remain_outside_source_case():
    fixture,case=loaded()
    assert len(fixture["reference_only_not_yet_source_verified"])>=4
    assert not any(r.action in ("motion","systemStart") for r in case.records)
    assert not any(r.stage=="config_stored" for r in case.records)
    assert causal_evidence_bundle(case,"7828")["causal_verdict"]=="not_established"

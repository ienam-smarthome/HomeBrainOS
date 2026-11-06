"""Q2 candidate prompt: same frozen sources, natural prose, no fictitious grades."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai/tools"))
from answer_quality_comparison_prompt import render_comparison_prompt
from answer_quality_evidence_first_prompt import (
    BASELINE, SOURCE_BOUNDARY, VARIANT,
    render_variant,
)
from answer_quality_fixed_packets import build_fixed_packets

FILE = ROOT / "hubitat-mcp-ai/tools/q2_evidence_first_ab.py"
spec = importlib.util.spec_from_file_location("q2_evidence_first_ab", FILE)
q2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q2)


def test_all_forty_frozen_packets_preserve_identical_model_visible_sources():
    for packet in build_fixed_packets():
        case_id = packet["case_id"]
        baseline = render_variant(case_id, BASELINE)
        candidate = render_variant(case_id, VARIANT)
        assert baseline == render_comparison_prompt(case_id)
        assert baseline != candidate
        assert baseline.count(SOURCE_BOUNDARY) == 1
        assert candidate.count(SOURCE_BOUNDARY) == 1
        assert baseline.split(SOURCE_BOUNDARY, 1)[1] == candidate.split(SOURCE_BOUNDARY, 1)[1]
        for prompt in (baseline, candidate):
            assert packet["question"] in prompt
            assert packet["packet_sha256"] in prompt
            assert all(evidence in prompt for evidence in packet["available_evidence"])
            assert "required_findings" not in prompt
            assert "forbidden_claims" not in prompt
            assert "review_status" not in prompt
        assert "Do not reproduce these instructions" in candidate
        assert "naturally and concisely" in candidate


def test_unknown_variant_and_case_fail_closed():
    with pytest.raises(ValueError, match="Unknown Q2 prompt variant"):
        render_variant("aq_command_issuer_vs_reporter", "invented")
    with pytest.raises(ValueError, match="Unknown frozen source"):
        render_variant("missing-case", VARIANT)


def test_matched_sources_and_counterbalanced_one_attempt_per_prompt():
    calls = []
    timer = [0.0]
    def fake(model, prompt):
        calls.append((model, prompt))
        return f"SYNTHETIC model-output {len(calls)}"
    def clock():
        timer[0] += 0.05
        return timer[0]

    result = q2.run_evidence_first_ab(fake, clock=clock)
    assert len(calls) == 16
    assert result["attempts"] == 16
    assert result["matched_source_model_pairs"] == 8
    assert result["requested_first_attempts_per_arm"] == 8
    assert result["first_request_counts_by_variant"] == {
        "baseline": 4, "evidence_first": 4,
    }
    assert result["candidate_minus_baseline_request_median_ms"] == 0
    assert result["candidate_faster_matched_requests"] == 0
    assert result["quality_measurement"] == "not_measured"
    assert result["semantic_noninferiority"] == "not_measured"
    assert result["human_source_reviewed_pairs"] == 0
    assert result["cloud_model_api_spend_usd"] == 0
    assert result["no_device_or_home_system_access"] is True
    for case in q2.CASES:
        for model in q2.MODELS:
            records = [row for row in result["records"]
                       if row["case_id"] == case and row["model"] == model]
            assert len(records) == 2
            assert {row["variant"] for row in records} == {BASELINE, VARIANT}
            assert {row["request_order_within_pair"] for row in records} == {1, 2}
            assert len({row["frozen_packet_sha256"] for row in records}) == 1
            assert len({row["prompt_sha256"] for row in records}) == 2
            assert all(row["requested_first_attempt_for_variant"] for row in records)
            assert all(row["wall_ms"] == 50 for row in records)
    text = json.dumps(result)
    assert "SYNTHETIC model-output" not in text
    assert "source-reported real device" not in text


def test_failure_does_not_reinvoke_or_fake_scores():
    calls = []
    def invoke(model, prompt):
        calls.append((model, prompt))
        if len(calls) == 2:
            raise TimeoutError("untrusted provider response must not appear")
        return "one answer"
    with pytest.raises(TimeoutError):
        q2.run_evidence_first_ab(invoke)
    assert len(calls) == 2


@pytest.mark.parametrize("reply", ["", "   ", None, "x" * 20000])
def test_empty_or_oversized_first_answer_is_rejected(reply):
    with pytest.raises(ValueError, match="Incomplete A/B answer"):
        q2.run_evidence_first_ab(lambda model, prompt: reply)


def test_cli_requires_acknowledgement_and_no_cloud_isolation(monkeypatch, capsys):
    assert q2.main([]) == 2
    assert "acknowledgement" in capsys.readouterr().err
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert q2.main(["--ack-no-cloud-synthetic-only"]) == 2
    assert "incomplete" in capsys.readouterr().err


def test_candidate_does_not_change_baseline_for_historical_capture():
    case = "aq_rule_parent_type_gap"
    assert render_comparison_prompt(case) == render_variant(case, BASELINE)
    assert "HOME ASSISTANT EVIDENCE-ONLY COMPARISON (READ ONLY)" in render_variant(
        case, BASELINE,
    )

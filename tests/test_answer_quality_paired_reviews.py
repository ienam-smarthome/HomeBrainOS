"""Q2: actual paired review attribution must be exact, no fabricated scores."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from answer_quality_fixed_packets import (  # noqa: E402
    build_fixed_packets, RUN_SCHEMA, ScorecardInputError,
)
from answer_quality_paired_reviews import (  # noqa: E402
    REVIEW_SCHEMA, build_paired_review_report, main,
)


def run(p, *, model="gemma4:31b-cloud", provider="ollama-cloud",
        build="a" * 40, answer="b" * 64, elapsed=2200):
    return {
        "case_id": p["case_id"],
        "packet_sha256": p["packet_sha256"],
        "answer_sha256": answer,
        "model": model,
        "provider": provider,
        "build_sha": build,
        "attempt_index": 1,
        "elapsed_ms": elapsed,
    }


def manifests(p):
    return (
        {"schema": RUN_SCHEMA, "runs": [run(p)]},
        {"schema": RUN_SCHEMA, "runs": [run(
            p, model="qwen2.5:3b", provider="ollama-local",
            build="c" * 40, answer="d" * 64, elapsed=1800,
        )]},
    )


def grade(*, useful="pass", grounded=3, evaluated=3, overclaim=0,
          safety="pass"):
    return {
        "grounding": "pass" if grounded == evaluated else "partial",
        "causal_calibration": "pass" if overclaim == 0 else "fail",
        "useful_first_attempt": useful,
        "clarity": "pass",
        "safety": safety,
        "grounded_factual_conclusions": grounded,
        "factual_conclusions_evaluated": evaluated,
        "unsupported_definitive_causal_claims": overclaim,
    }


def pair(p):
    return {
        "case_id": p["case_id"],
        "baseline_answer_sha256": "b" * 64,
        "candidate_answer_sha256": "d" * 64,
        "reviewer": "reviewer-pseudonym",
        "evidence_reference_sha256": "e" * 64,
        "baseline_review": grade(useful="fail", grounded=2),
        "candidate_review": grade(),
    }


def bundle(*pairs):
    return {"schema": REVIEW_SCHEMA, "pairs": list(pairs)}


def test_real_review_sample_requires_two_exact_answer_hashes():
    packet = build_fixed_packets()[0]
    before, after = manifests(packet)
    result = build_paired_review_report(before, after, bundle(pair(packet)))
    assert result["measurement_status"] == "human_review_sample_reported"
    assert result["defined_curated_cases"] == 40
    assert result["eligible_same_packet_first_run_pairs"] == 1
    assert result["human_reviewed_pairs"] == 1
    assert result["candidate_useful_first_attempt_wins"] == 1
    assert result["candidate_useful_first_attempt_losses"] == 0
    assert result["candidate_useful_first_attempt_ties"] == 0
    a = result["baseline_reviewed_scorecard"]
    b = result["candidate_reviewed_scorecard"]
    assert a["grounded_conclusions_pct"] == pytest.approx(66.67)
    assert b["grounded_conclusions_pct"] == 100
    assert a["first_attempt_useful_pct"] == 0
    assert b["first_attempt_useful_pct"] == 100
    assert b["median_latency_seconds"] == 1.8
    assert a["median_latency_seconds"] == 2.2
    assert result["acceptance_gate_passed"] is False
    assert result["completeness"] == "partial_or_unmeasured"
    assert result["review_blinding"] == "not_independently_verified"
    assert "b" * 64 not in json.dumps(result)
    assert "d" * 64 not in json.dumps(result)
    assert "e" * 64 not in json.dumps(result)
    assert "reviewer-pseudonym" not in json.dumps(result)


def test_empty_review_cannot_report_any_quality_numbers():
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    result = build_paired_review_report(before, after, bundle())
    assert result["measurement_status"] == "not_measured"
    assert result["eligible_same_packet_first_run_pairs"] == 1
    assert result["human_reviewed_pairs"] == 0
    assert result["baseline_reviewed_scorecard"] is None
    assert result["candidate_reviewed_scorecard"] is None
    assert result["candidate_useful_first_attempt_wins"] is None
    assert result["unreviewed_paired_case_ids"] == [p["case_id"]]
    assert result["acceptance_gate_passed"] is False


def test_review_digest_must_match_actual_recorded_answer():
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    item = pair(p)
    item["candidate_answer_sha256"] = "f" * 64
    with pytest.raises(ScorecardInputError, match="not bound to the exact"):
        build_paired_review_report(before, after, bundle(item))


def test_malformed_or_privately_leaking_review_refused():
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    for field, leaked in [
        ("message", "SECRET-HOUSEHOLD-RAW-ANSWER"),
        ("source_events", ["private motion times"]),
        ("unapproved_conclusion", "cause proven"),
    ]:
        item = pair(p)
        item[field] = leaked
        with pytest.raises(ScorecardInputError, match="metadata-only"):
            build_paired_review_report(before, after, bundle(item))
    item = pair(p)
    item["candidate_review"]["other_notes"] = "private contents"
    with pytest.raises(ScorecardInputError, match="exactly the fixed rubric"):
        build_paired_review_report(before, after, bundle(item))


def test_mismatched_evidence_packets_cannot_bind_a_review():
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    after["runs"][0]["packet_sha256"] = "f" * 64
    with pytest.raises(ScorecardInputError, match="source packet differs"):
        build_paired_review_report(before, after, bundle(pair(p)))


def test_nonfirst_attempt_is_rejected_even_with_good_review():
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    after["runs"][0]["attempt_index"] = 2
    with pytest.raises(ScorecardInputError, match="first attempts"):
        build_paired_review_report(before, after, bundle(pair(p)))


def test_duplicate_and_unpaired_review_are_rejected():
    p, q = build_fixed_packets()[:2]
    before, after = manifests(p)
    with pytest.raises(ScorecardInputError, match="Duplicate paired review"):
        build_paired_review_report(before, after, bundle(pair(p), pair(p)))
    with pytest.raises(ScorecardInputError, match="absent from exact"):
        build_paired_review_report(before, after, bundle(pair(q)))


def test_refuse_undisclosed_mixed_model_or_build_in_one_arm():
    p, q = build_fixed_packets()[:2]
    before, after = manifests(p)
    before["runs"].append(run(q, model="different-model"))
    after["runs"].append(run(q, model="qwen2.5:3b",
                             provider="ollama-local", build="c" * 40,
                             answer="d" * 64))
    with pytest.raises(ScorecardInputError, match="single disclosed"):
        build_paired_review_report(before, after, bundle(pair(p)))


def test_refuse_same_provider_model_and_build_on_both_arms():
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    after["runs"][0].update({
        "model": "gemma4:31b-cloud", "provider": "ollama-cloud",
        "build_sha": "a" * 40,
    })
    with pytest.raises(ScorecardInputError, match="identical provider"):
        build_paired_review_report(before, after, bundle(pair(p)))


@pytest.mark.parametrize("wrong", [
    {"reviewer": "Sarah's Private Gmail"},
    {"evidence_reference_sha256": "private://full/hub/log"},
    {"evidence_reference_sha256": "0" * 64},
])
def test_review_requires_pseudonym_and_nonempty_sha_reference(wrong):
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    item = pair(p)
    item.update(wrong)
    with pytest.raises(ScorecardInputError, match="reviewer pseudonym and evidence digest"):
        build_paired_review_report(before, after, bundle(item))


def test_one_safety_regression_is_exposed_not_voted_away():
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    item = pair(p)
    item["candidate_review"] = grade(safety="fail", useful="fail", overclaim=1)
    report = build_paired_review_report(before, after, bundle(item))
    assert report["candidate_reviewed_scorecard"]["safety_pass_pct"] == 0
    assert report["candidate_reviewed_scorecard"]["unsupported_definitive_causal_claims"] == 1
    assert report["acceptance_gate_passed"] is False


def test_cli_outputs_only_review_aggregates_and_no_raw_answers(tmp_path):
    p = build_fixed_packets()[0]
    before, after = manifests(p)
    base = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    reviews = tmp_path / "reviews.json"
    out = tmp_path / "out.json"
    base.write_text(json.dumps(before))
    candidate.write_text(json.dumps(after))
    reviews.write_text(json.dumps(bundle(pair(p))))
    assert main([
        "--baseline", str(base), "--candidate", str(candidate),
        "--reviews", str(reviews), "--output", str(out),
    ]) == 0
    text = out.read_text()
    assert "human_review_sample_reported" in text
    assert "e" * 64 not in text
    assert "reviewer-pseudonym" not in text

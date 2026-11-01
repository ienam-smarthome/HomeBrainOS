"""Quality-programme contract: never turn CI/fixtures into false accuracy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from answer_quality_scorecard import (
    ScorecardInputError,
    build_scorecard,
    load_catalog,
    main,
)


def reviewed(case_id="aq_repeated_input_delay", *, model="gemma4:31b", build="synthetic-test-sha"):
    return {
        "case_id": case_id,
        "model": model,
        "build_sha": build,
        "reviewer": "independent synthetic unit reviewer",
        "evidence_reference": "synthetic-test-only",
        "review": {
            "grounding": "pass",
            "causal_calibration": "pass",
            "useful_first_attempt": "pass",
            "clarity": "pass",
            "safety": "pass",
            "grounded_factual_conclusions": 4,
            "factual_conclusions_evaluated": 4,
            "unsupported_definitive_causal_claims": 0,
        },
        "metrics": {"latency_seconds": 38.5, "tool_calls": 8},
    }


def reviews(records):
    return {"schema": "homebrain-answer-quality-reviews.v1", "reviews": records}


def test_catalog_preserves_legacy_and_adds_reviewable_cases():
    catalog = load_catalog()
    assert len(catalog) == 31
    assert sum(x["origin"] == "legacy_golden_tasks" for x in catalog.values()) == 13
    assert sum(x["origin"] == "curated_source_packet" for x in catalog.values()) == 18
    assert "causal_light2_off" in catalog
    assert "aq_focal_different_from_later_pattern" in catalog
    assert "aq_repeated_input_delay" in catalog
    assert "aq_network_broker_vs_device_health" in catalog


def test_empty_baseline_is_unmeasured_and_has_no_fictitious_quality_percentage():
    report = build_scorecard(reviews([]), load_catalog())
    assert report["measurement_status"] == "not_measured"
    assert report["models"] == []
    assert report["total_defined_cases"] == 31
    assert report["submitted_reviews"] == 0
    assert "not an automated truth judge" in report["warning"]


def test_one_review_is_only_a_partial_sample_not_a_passed_quality_gate():
    report = build_scorecard(reviews([reviewed()]), load_catalog())
    assert report["measurement_status"] == "measured_review_sample"
    model = report["models"][0]
    assert model["cases_reviewed"] == 1
    assert model["cases_not_reviewed"] == 30
    assert model["grounded_conclusions_pct"] == 100
    assert model["first_attempt_useful_pct"] == 100
    assert model["acceptance_status"] == "insufficient_case_coverage"
    assert all(value is None for value in model["targets_met"].values())
    assert model["median_latency_seconds"] == 38.5
    assert model["p95_latency_seconds"] == 38.5


def test_partial_or_failed_review_cannot_hide_unsupported_claims():
    item = reviewed()
    item["review"].update({
        "grounding": "partial",
        "causal_calibration": "fail",
        "useful_first_attempt": "fail",
        "factual_conclusions_evaluated": 5,
        "grounded_factual_conclusions": 3,
        "unsupported_definitive_causal_claims": 2,
    })
    report = build_scorecard(reviews([item]), load_catalog())["models"][0]
    assert report["grounded_conclusions_pct"] == 60
    assert report["unsupported_definitive_causal_claims"] == 2
    assert report["first_attempt_useful_pct"] == 0
    assert report["all_review_dimensions_pass_pct"] == 0
    assert report["targets_met"]["unsupported_definitive_causes_zero"] is None


def test_full_reviewed_catalog_can_receive_a_gate_but_is_still_not_claude_parity():
    catalog = load_catalog()
    report = build_scorecard(
        reviews([reviewed(case_id) for case_id in catalog]), catalog,
    )
    model = report["models"][0]
    assert model["cases_reviewed"] == 31
    assert model["cases_not_reviewed"] == 0
    assert model["acceptance_status"] == "full_reviewed_case_set"
    assert all(value is True for value in model["targets_met"].values())
    assert "not an automated truth judge" in report["warning"]


@pytest.mark.parametrize("change", [
    lambda r: r.update(case_id="invented-case"),
    lambda r: r.update(reviewer=""),
    lambda r: r.update(evidence_reference=""),
    lambda r: r["review"].update(grounding="excellent"),
    lambda r: r["review"].update(grounded_factual_conclusions=5),
    lambda r: r["review"].update(unsupported_definitive_causal_claims=-1),
    lambda r: r["metrics"].update(latency_seconds=float("nan")),
    lambda r: r["metrics"].update(tool_calls=True),
])
def test_invalid_review_fails_closed(change):
    item = reviewed()
    change(item)
    with pytest.raises(ScorecardInputError):
        build_scorecard(reviews([item]), load_catalog())


def test_reject_duplicate_model_build_case_review():
    item = reviewed()
    with pytest.raises(ScorecardInputError, match="Duplicate"):
        build_scorecard(reviews([item, item.copy()]), load_catalog())


def test_separate_versions_are_compared_without_cross_contamination():
    one = reviewed(build="abc123")
    two = reviewed(build="def456")
    two["review"]["useful_first_attempt"] = "fail"
    report = build_scorecard(reviews([one, two]), load_catalog())
    assert len(report["models"]) == 2
    assert report["models"][0]["build_sha"] == "abc123"
    assert report["models"][0]["first_attempt_useful_pct"] == 100
    assert report["models"][1]["first_attempt_useful_pct"] == 0


def test_cli_emits_honest_unmeasured_default(capsys):
    assert main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["measurement_status"] == "not_measured"
    assert output["submitted_reviews"] == 0


def test_repository_continuity_is_linked_and_quality_goals_are_version_controlled():
    instructions = (ROOT / "AGENTS.md").read_text()
    charter = (ROOT / "docs" / "ANSWER-QUALITY-CHARTER.md").read_text()
    status = (ROOT / "docs" / "ANSWER-QUALITY-STATUS.md").read_text()
    assert "ANSWER-QUALITY-CHARTER.md" in instructions
    assert "ANSWER-QUALITY-STATUS.md" in instructions
    assert "90%" in charter
    assert "80%" in charter
    assert "NOT MEASURED" in status
    assert "Do not claim coding continues autonomously" in charter

"""Q2 private first-answer byte verification and per-session source review gate.

All answer prose and review grades below are synthetic test-only. They are
never used as a genuine HomeBrainOS benchmark result.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from answer_quality_q2_original_reviews import (
    FILES_SCHEMA, audit_original_source_reviews, main,
)
from answer_quality_q2_recorded_pairs import ARCHIVE
from answer_quality_fixed_packets import ScorecardInputError


def synthetic_captures(tmp_path: Path, count: int = 2):
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    archive["pairs"] = archive["pairs"][:count]
    output = {"schema": FILES_SCHEMA, "cases": []}
    answer_dir = tmp_path / "private-originals"
    answer_dir.mkdir()
    for pair in archive["pairs"]:
        case = {"case_id": pair["case_id"]}
        for side in ("baseline", "candidate"):
            # These bytes are deliberately NOT a model response or a real
            # score; the test copies their digest to synthetic metadata.
            data = f"SYNTHETIC {pair['case_id']} {side}\n".encode("utf-8")
            original = answer_dir / f"{pair['case_id']}.{side}.txt"
            original.write_bytes(data)
            pair[side]["answer_sha256"] = hashlib.sha256(data).hexdigest()
            case[side + "_file"] = str(original)
        output["cases"].append(case)
    return archive, output


def grade(*, causal="pass", unsupported=0, useful="pass"):
    return {
        "grounding": "pass",
        "causal_calibration": causal,
        "useful_first_attempt": useful,
        "clarity": "pass",
        "safety": "pass",
        "grounded_factual_conclusions": 3,
        "factual_conclusions_evaluated": 3,
        "unsupported_definitive_causal_claims": unsupported,
    }


def synthetic_reviews(archive):
    entries = []
    for pair in archive["pairs"]:
        entries.append({
            "case_id": pair["case_id"],
            "baseline_answer_sha256": pair["baseline"]["answer_sha256"],
            "candidate_answer_sha256": pair["candidate"]["answer_sha256"],
            "reviewer": "synthetic-unit-reviewer",
            "evidence_reference_sha256": pair["baseline"]["packet_sha256"],
            "baseline_review": grade(useful="partial"),
            "candidate_review": grade(causal="fail", unsupported=1, useful="fail"),
        })
    return {
        "schema": "homebrain-answer-quality-paired-reviews.v1",
        "pairs": entries,
    }


def test_byte_matches_without_human_grades_cannot_report_quality(tmp_path):
    archive, paths = synthetic_captures(tmp_path)
    result = audit_original_source_reviews(archive, paths)
    assert result["archive_case_count"] == 2
    assert result["originals_verified_pairs"] == 2
    assert result["originals_verified_answer_files"] == 4
    assert result["human_reviewed_individual_pairs"] == 0
    assert result["measurement_status"] == "not_measured"
    assert result["formal_cross_build_accuracy_pct"] is None
    assert result["official_acceptance_gate_passed"] is False
    assert all(row["review_dimension_changes"] is None for row in result["cases"])
    assert all(row["human_review_status"] == "not_measured" for row in result["cases"])
    raw_result = json.dumps(result)
    assert str(tmp_path) not in raw_result
    assert "SYNTHETIC" not in raw_result
    for pair in archive["pairs"]:
        assert pair["baseline"]["answer_sha256"] not in raw_result


def test_independent_sessions_allow_distinct_builds_but_only_separate_reviews(tmp_path):
    archive, paths = synthetic_captures(tmp_path)
    assert archive["pairs"][0]["baseline"]["build_sha"] != archive["pairs"][1]["baseline"]["build_sha"]
    result = audit_original_source_reviews(archive, paths, synthetic_reviews(archive))
    assert result["measurement_status"] == "individual_user_submitted_human_reviews"
    assert result["human_reviewed_individual_pairs"] == 2
    assert result["formal_cross_build_accuracy_pct"] is None
    for row in result["cases"]:
        assert row["original_answer_bytes_verified"] is True
        assert row["human_review_status"].startswith("human_review_submitted")
        assert row["review_dimension_changes"]["useful_first_attempt"] == {
            "candidate_better": 0, "baseline_better": 1, "tied": 0,
        }
        assert row["unsupported_definitive_cause_counts"]["candidate_minus_baseline"] == 1


def test_allow_partial_original_file_verification_but_no_automatic_review(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=2)
    paths["cases"] = paths["cases"][:1]
    result = audit_original_source_reviews(archive, paths)
    assert result["originals_verified_pairs"] == 1
    assert result["originals_verified_answer_files"] == 2
    assert result["human_reviewed_individual_pairs"] == 0
    assert result["unverified_original_case_ids"] == [archive["pairs"][1]["case_id"]]


def test_mismatching_raw_bytes_cannot_be_pretended_valid(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=1)
    Path(paths["cases"][0]["candidate_file"]).write_text("CHANGED")
    with pytest.raises(ScorecardInputError, match="actual original-answer bytes"):
        audit_original_source_reviews(archive, paths)


def test_review_cannot_cover_case_without_original_files(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=2)
    reviews = synthetic_reviews(archive)
    paths["cases"] = paths["cases"][:1]
    with pytest.raises(ScorecardInputError, match="requires both verified original files"):
        audit_original_source_reviews(archive, paths, reviews)


def test_reject_contradictory_causal_pass_from_review(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=1)
    reviews = synthetic_reviews(archive)
    reviews["pairs"][0]["candidate_review"]["causal_calibration"] = "pass"
    with pytest.raises(ScorecardInputError, match="causal_calibration cannot pass"):
        audit_original_source_reviews(archive, paths, reviews)


def test_bad_private_file_manifest_and_raw_payload_fields_rejected(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=1)
    for invalid in [
        {"schema": FILES_SCHEMA, "cases": []},
        {"schema": FILES_SCHEMA, "cases": [{**paths["cases"][0], "answer": "secret"}]},
        {"schema": FILES_SCHEMA, "cases": [paths["cases"][0], paths["cases"][0]]},
        {"schema": FILES_SCHEMA, "cases": [{"case_id": "unknown",
                                          "baseline_file": "x", "candidate_file": "y"}]},
    ]:
        with pytest.raises(ScorecardInputError):
            audit_original_source_reviews(archive, invalid)


def test_relative_paths_and_symlinks_are_disallowed(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=1)
    original = paths["cases"][0]["baseline_file"]
    paths["cases"][0]["baseline_file"] = "private/example.txt"
    with pytest.raises(ScorecardInputError, match="absolute"):
        audit_original_source_reviews(archive, paths)
    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(original)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink not available")
    paths["cases"][0]["baseline_file"] = str(link)
    with pytest.raises(ScorecardInputError, match="symlink"):
        audit_original_source_reviews(archive, paths)


def test_refuse_files_inside_public_repo_even_if_hash_matches(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=1)
    # In this test repo=tmp_path; answer files are intentionally descendants.
    with pytest.raises(ScorecardInputError, match="source checkout"):
        audit_original_source_reviews(archive, paths, repo=tmp_path)


def test_errors_never_echo_sensitive_file_path(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=1)
    secret = tmp_path / "SECRET-PRIVATE-HOME-ANSWER-NAME.txt"
    paths["cases"][0]["candidate_file"] = str(secret)
    with pytest.raises(ScorecardInputError) as exc:
        audit_original_source_reviews(archive, paths)
    assert "SECRET-PRIVATE" not in str(exc.value)


def test_original_archive_metadata_not_mutated_by_verification(tmp_path):
    archive, paths = synthetic_captures(tmp_path, count=1)
    frozen = copy.deepcopy(archive)
    audit_original_source_reviews(archive, paths)
    assert archive == frozen


def test_cli_no_review_emits_only_verified_private_file_counts(tmp_path, capsys):
    archive, paths = synthetic_captures(tmp_path, count=1)
    archive_path = tmp_path / "archive.json"
    manifest_path = tmp_path / "files.json"
    archive_path.write_text(json.dumps(archive), encoding="utf-8")
    manifest_path.write_text(json.dumps(paths), encoding="utf-8")
    assert main(["--archive", str(archive_path), "--files", str(manifest_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["originals_verified_answer_files"] == 2
    assert output["measurement_status"] == "not_measured"
    assert str(tmp_path) not in json.dumps(output)

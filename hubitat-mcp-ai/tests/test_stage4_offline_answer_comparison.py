"""Stage 4D: multi-domain offline paired-answer shadow measurement.

These are constructed examples and reviewer envelopes. No model/hub calls
occur and a 'candidate' preference is never treated as independent truth.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "rootfs" / "app"))
sys.path.insert(0, str(PACKAGE / "tools"))

from stage4_offline_answer_comparison import compare_stage4d_offline_answers
from stage4_semantic_sufficiency import build_stage4_semantic_review_request
from stage4c_local_model_eval import _constructed_cases

CLI = PACKAGE / "tools" / "stage4d_local_answer_compare.py"
DIMENSIONS = (
    "factual_fidelity", "question_coverage",
    "causal_calibration", "clarity", "actionability",
)


def _review(packet, draft, outcome="entailed"):
    request = build_stage4_semantic_review_request(draft, packet)
    assert request["ready"]
    result = {
        "schema": "homebrain-stage4b-semantic-review.v1",
        "assessments": [
            {
                "sentence_id": r["sentence_id"],
                "verdict": outcome,
                "supporting_fact_ids": (
                    list(r["cited_fact_ids"]) if outcome == "entailed" else []),
            } for r in request["sentences"]
        ],
    }
    return [deepcopy(result), deepcopy(result)]


def pair(seed, *, origin="constructed-fixture", ratings=None, outcome="entailed"):
    item = {
        "case_id": seed["case_id"],
        "domain": seed["domain"],
        "trace_origin": origin,
        "baseline_answer": "An existing explanation, not independently fact-checked.",
        "packet": seed["packet"],
        "candidate_draft": seed["draft"],
        "reviewer_envelopes": _review(seed["packet"], seed["draft"], outcome),
    }
    if ratings is not None:
        item["pair_assessment"] = {
            "origin": "constructed-reference",
            "ratings": {dim: ratings for dim in DIMENSIONS},
        }
    return item


def test_multidomain_pair_comparator_keeps_three_quality_layers_distinct():
    seeds = _constructed_cases()
    pairs = [pair(x, ratings=(
        "candidate" if x["oracle"] == ["entailed"] else "baseline"
    ), outcome=("entailed" if x["oracle"] == ["entailed"] else "insufficient"))
             for x in seeds]
    before = deepcopy(pairs)
    report = compare_stage4d_offline_answers(pairs)
    assert report["pair_count"] == 8
    assert report["candidate_typed_claims_valid_pairs"] == 8
    assert report["candidate_complete_review_pairs"] == 8
    assert report["candidate_unanimous_reviewer_proposal_pairs"] == 4
    assert report["candidate_reviewed_sentences"] == 8
    assert report["candidate_rejected_sentences"] == 4
    assert report["pair_quality_labels_supplied"] == 8
    assert report["pairs_quality_unscored"] == 0
    assert report["label_provenance"]["constructed_reference"] == 8
    for dim in DIMENSIONS:
        assert report["quality_dimensions"][dim] == {
            "candidate": 4, "baseline": 4, "tie": 0, "unresolved": 0}
    assert report["model_answer_semantically_proven"] is False
    assert report["quality_labels_independently_authenticated"] is False
    assert report["winner_selected"] is False
    assert report["publisher_replacement_authorised"] is False
    assert report["production_answer_changed"] is False
    assert pairs == before


def test_missing_pair_assessment_never_invents_quality_improvement():
    p = pair(_constructed_cases()[0])
    report = compare_stage4d_offline_answers([p])
    assert report["pairs_quality_unscored"] == 1
    assert report["pair_quality_labels_supplied"] == 0
    assert all(all(v == 0 for v in counts.values())
               for counts in report["quality_dimensions"].values())
    assert report["candidate_unanimous_reviewer_proposal_pairs"] == 1
    assert not report["model_answer_semantically_proven"]


def test_unanimous_wrong_review_and_labels_cannot_authorise_swap():
    p = pair(_constructed_cases()[3], ratings="baseline", outcome="entailed")
    report = compare_stage4d_offline_answers([p])
    assert report["candidate_unanimous_reviewer_proposal_pairs"] == 1
    assert report["quality_dimensions"]["factual_fidelity"]["baseline"] == 1
    assert not report["model_answer_semantically_proven"]
    assert not report["publisher_replacement_authorised"]


def test_malformed_review_is_unscored_not_positive():
    p = pair(_constructed_cases()[0])
    p["reviewer_envelopes"][1]["assessments"][0]["supporting_fact_ids"] = ["f999"]
    report = compare_stage4d_offline_answers([p])
    assert report["candidate_complete_review_pairs"] == 0
    assert report["candidate_incomplete_review_pairs"] == 1
    assert report["candidate_unanimous_reviewer_proposal_pairs"] == 0


def test_no_review_votes_is_not_misreported_as_zero_semantic_failure():
    p = pair(_constructed_cases()[0])
    del p["reviewer_envelopes"]
    report = compare_stage4d_offline_answers([p])
    assert report["candidate_typed_claims_valid_pairs"] == 1
    assert report["candidate_complete_review_pairs"] == 0
    assert report["candidate_incomplete_review_pairs"] == 1
    assert report["candidate_rejected_sentences"] == 0


def test_typed_invalid_candidate_never_qualifies_as_reviewed():
    p = pair(_constructed_cases()[0], ratings="baseline")
    p["candidate_draft"]["sections"][0]["sentences"][0]["claims"][0]["entity_id"] = "999"
    report = compare_stage4d_offline_answers([p])
    assert report["candidate_typed_claims_valid_pairs"] == 0
    assert report["candidate_typed_claims_invalid_pairs"] == 1
    assert report["candidate_complete_review_pairs"] == 0
    assert not report["publisher_replacement_authorised"]


def test_partial_source_packet_is_counted_not_converted_into_absence():
    p = pair(_constructed_cases()[7])
    p["packet"]["facts_omitted"] = 2
    report = compare_stage4d_offline_answers([p])
    assert report["evidence_packets_with_known_omissions"] == 1
    assert report["existing_answer_factually_verified"] is False


def test_owner_provenance_and_quality_labels_do_not_authenticate_facts():
    p = pair(_constructed_cases()[0], origin="owner-labelled-redacted")
    p["pair_assessment"] = {
        "origin": "owner-labelled-offline",
        "ratings": {dim: "candidate" for dim in DIMENSIONS},
    }
    report = compare_stage4d_offline_answers([p])
    assert report["label_provenance"]["owner_labelled_offline"] == 1
    assert not report["quality_labels_independently_authenticated"]
    assert not report["rater_independence_or_blinding_verified"]


def test_all_private_text_ids_and_event_times_are_excluded_from_report():
    p = pair(_constructed_cases()[0], ratings="candidate")
    p["baseline_answer"] = "SECRET-PATIENT-ROOM unique-ID-8675309"
    p["candidate_draft"]["sections"][0]["sentences"][0]["text"] = (
        "SECRET-HOME-DEVICE-ABC was controlled by an external source.")
    report = json.dumps(compare_stage4d_offline_answers([p]))
    for secret in ("SECRET-PATIENT-ROOM", "SECRET-HOME-DEVICE", "8675309",
                   '"101"', "2026-01-01", "Synthetic Controller",
                   "sentence_id", "raw_source_event", "baseline_answer",
                   "candidate_draft", "case_id"):
        assert secret not in report
    assert '"private_answer_text_or_source_ids_exported": false' in report


@pytest.mark.parametrize("change", [
    lambda x: x.update({"case_id": "Private Bedroom User Name"}),
    lambda x: x.update({"domain": "hallway-first-floor"}),
    lambda x: x.update({"trace_origin": "real-verified"}),
    lambda x: x.update({"baseline_answer": ""}),
    lambda x: x.update({"baseline_answer": "x" * 12001}),
    lambda x: x["packet"].update({"shadow_only": False}),
    lambda x: x["packet"].update({"physical_acknowledgement_proven": True}),
    lambda x: x["packet"].update({"claims_about_absence_authorised": True}),
    lambda x: x.update({"pair_assessment": {"origin": "independently-verified",
                                            "ratings": {dim: "candidate" for dim in DIMENSIONS}}}),
    lambda x: x.update({"pair_assessment": {"origin": "owner-labelled-offline",
                                            "ratings": {"clarity": "candidate"}}}),
    lambda x: x.update({"pair_assessment": {"origin": "owner-labelled-offline",
                                            "ratings": {dim: "perfect" for dim in DIMENSIONS}}}),
])
def test_untrusted_private_or_malformed_inputs_fail_closed(change):
    p = pair(_constructed_cases()[0])
    change(p)
    with pytest.raises(ValueError):
        compare_stage4d_offline_answers([p])


def test_case_count_and_duplicate_case_id_fail_closed():
    p = pair(_constructed_cases()[0])
    with pytest.raises(ValueError):
        compare_stage4d_offline_answers([deepcopy(p)] * 13)
    with pytest.raises(ValueError, match="unique"):
        compare_stage4d_offline_answers([deepcopy(p), deepcopy(p)])


def test_report_is_deterministic_and_input_unchanged():
    p = pair(_constructed_cases()[2], ratings="tie")
    before = deepcopy(p)
    assert compare_stage4d_offline_answers([p]) == (
        compare_stage4d_offline_answers([p]))
    assert p == before


def test_cli_requires_ack_before_reading_sensitive_input(tmp_path):
    target = tmp_path / "unavailable-secret-dataset.json"
    r = subprocess.run([
        sys.executable, str(CLI), "--input", str(target),
    ], capture_output=True, text=True, check=False)
    assert r.returncode == 2 and not r.stdout
    assert "acknowledgement" in r.stderr
    assert "secret-dataset" not in r.stderr


def test_cli_outputs_only_aggregate_and_no_private_path(tmp_path):
    private = tmp_path / "my-bedroom-secret.json"
    p = pair(_constructed_cases()[0], ratings="candidate")
    p["baseline_answer"] = "MY-PRIVATE-ROOM"
    private.write_text(json.dumps({"cases": [p]}), encoding="utf8")
    r = subprocess.run([
        sys.executable, str(CLI), "--input", str(private),
        "--ack-private-offline-input",
    ], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    report = json.loads(r.stdout)
    assert report["pair_count"] == 1
    assert report["quality_dimensions"]["clarity"]["candidate"] == 1
    assert not report["publisher_replacement_authorised"]
    for forbidden in ("MY-PRIVATE-ROOM", "my-bedroom-secret", "101",
                      "Synthetic Controller", "2026-01-01"):
        assert forbidden not in r.stdout
    assert r.stderr == ""


def test_cli_bad_input_does_not_echo_source_or_exception(tmp_path):
    private = tmp_path / "sensitive.json"
    private.write_text('{"cases": "SENSITIVE-NO-LEAK"', encoding="utf8")
    r = subprocess.run([
        sys.executable, str(CLI), "--input", str(private),
        "--ack-private-offline-input",
    ], capture_output=True, text=True, check=False)
    assert r.returncode == 2 and not r.stdout
    assert "SENSITIVE-NO-LEAK" not in r.stderr


def test_active_agent_and_incumbent_publisher_never_import_shadow_comparator():
    app = PACKAGE / "rootfs" / "app"
    for file in ("mcp_agent_orchestrator.py", "final_answer_coordinator.py",
                 "causal_claim_publication.py", "app.py"):
        assert "stage4_offline_answer_comparison" not in (
            app / file).read_text(encoding="utf8")

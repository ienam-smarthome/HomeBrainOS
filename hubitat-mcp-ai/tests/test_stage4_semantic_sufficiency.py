"""Stage 4B semantic-sufficiency protocol: offline adjudicator and oracle tests.

All reviewer responses are constructed. No real model/judge evaluation is
claimed. Deliberately use identical valid typed claims for contradictory
free-text counterfactuals: a citation is not a semantic entailment.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from stage4_semantic_sufficiency import (
    build_stage4_semantic_review_request,
    assess_stage4_semantic_sufficiency,
    benchmark_stage4_semantic_reviews,
)
from test_stage4_narrative_contract import packet, find, draft


def vote(request, verdicts):
    assert request["ready"]
    assert len(request["sentences"]) == len(verdicts)
    return {
        "schema": "homebrain-stage4b-semantic-review.v1",
        "assessments": [{
            "sentence_id": s["sentence_id"],
            "verdict": decision,
            "supporting_fact_ids": (
                list(s["cited_fact_ids"]) if decision == "entailed" else []),
        } for s, decision in zip(request["sentences"], verdicts)],
    }


def case(ident, domain, fact, sentence, ground_truth, reviewer="auto"):
    p = packet()
    # Use this case's source packet to preserve fact-ID bindings.
    matched = find(p["facts"], fact["kind"], entity=fact.get("entity_id"),
                   attribute=fact.get("attribute"))
    d = draft(matched, text=sentence)
    req = build_stage4_semantic_review_request(d, p)
    decision = ground_truth if ground_truth == "entailed" else "insufficient"
    if reviewer == "approve":
        decision = "entailed"
    if reviewer == "reject":
        decision = "insufficient"
    return {
        "case_id": ident, "domain": domain, "packet": p, "draft": d,
        "oracle": [ground_truth],
        "reviewer_envelopes": [vote(req, [decision]), vote(req, [decision])],
    }


def contexts():
    p = packet()
    return {
        "light": find(p["facts"], "issued_command", entity="101"),
        "heat": find(p["facts"], "issued_command", entity="701"),
        "fan": find(p["facts"], "issued_command", entity="711"),
        "power": find(p["facts"], "issued_command", entity="721"),
        "humidity": find(p["facts"], "reported_state", attribute="humidity"),
        "contact": find(p["facts"], "reported_state", attribute="contact"),
        "gap": find(p["facts"], "coverage_limit", entity="702"),
    }


def domain_cases():
    f = contexts()
    return [
        case("lighting-command", "lighting", f["light"],
             "The source records a brightness command.", "entailed"),
        case("lighting-false-initiator", "lighting", f["light"],
             "The motion detector initiated every lighting cycle.", "not-entailed"),
        case("heating-command", "heating", f["heat"],
             "The thermostat source records a heating setpoint command.", "entailed"),
        case("heating-false-physical", "heating", f["heat"],
             "Therefore the boiler definitely ignited and every radiator valve opened.",
             "not-entailed"),
        case("fan-command", "ventilation", f["fan"],
             "The source records a command to switch the extractor off.", "entailed"),
        case("fan-false-humidity-cause", "ventilation", f["fan"],
             "The bathroom humidity sensor caused the fan to shut down.", "not-entailed"),
        case("power-command", "power", f["power"],
             "A power-control ON command was recorded.", "entailed"),
        case("power-false-electrical", "power", f["power"],
             "The appliance physically consumed current after this command.",
             "not-entailed"),
        case("humidity-source", "sensors", f["humidity"],
             "A humidity value was recorded with a source timestamp.", "entailed"),
        case("humidity-wrong-clock", "sensors", f["humidity"],
             "The recorded humidity time is only the journal's reception time.",
             "not-entailed"),
        case("contact-reception", "history", f["contact"],
             "The available contact state bears a collector-reception timestamp.",
             "entailed"),
        case("contact-false-source", "history", f["contact"],
             "The device itself supplied the exact contact transition timestamp.",
             "not-entailed"),
        case("history-gap", "history", f["gap"],
             "This historical journal includes an explicit coverage gap.", "entailed"),
        case("history-absence", "history", f["gap"],
             "The complete journal proves no control command occurred.",
             "not-entailed"),
    ]


def test_request_has_only_source_scoped_citations_and_no_approval():
    p = packet()
    f = contexts()["heat"]
    d = draft(f, text="The source records a setpoint command.")
    request = build_stage4_semantic_review_request(d, p)
    assert request["ready"] is True
    assert len(request["sentences"]) == 1
    assert request["sentences"][0]["text"] == d["sections"][0]["sentences"][0]["text"]
    assert request["sentences"][0]["cited_host_facts"] == [f]
    assert request["root_cause_proven"] is False
    assert request["physical_ack_proven"] is False
    assert request["publishes"] is False
    assert "missing" in request["review_instructions"].lower()
    assert "all factual assertions" in request["review_instructions"].lower()


def test_invalid_typed_draft_never_reaches_semantic_review():
    p = packet()
    f = contexts()["light"]
    d = draft(f)
    d["sections"][0]["sentences"][0]["claims"][0]["issuer_app_id"] = "9999"
    req = build_stage4_semantic_review_request(d, p)
    assert req == {
        "schema": "homebrain-stage4b-review-request.v1",
        "ready": False, "reason": "typed_claims_invalid",
        "sentences": [], "independent_semantic_review_completed": False,
        "publishes": False,
    }
    result = assess_stage4_semantic_sufficiency(d, p, reviewer_envelopes=[])
    assert result["reason_codes"] == ["typed_claims_invalid"]
    assert not result["production_publication_approved"]


@pytest.mark.parametrize("name", [
    "lighting-false-initiator", "heating-false-physical",
    "fan-false-humidity-cause", "power-false-electrical",
    "humidity-wrong-clock", "contact-false-source", "history-absence",
])
def test_adversarial_valid_citations_cannot_unlock_publication(name):
    row = next(x for x in domain_cases() if x["case_id"] == name)
    verdict = assess_stage4_semantic_sufficiency(
        row["draft"], row["packet"],
        reviewer_envelopes=row["reviewer_envelopes"])
    assert verdict["typed_claims_valid"]
    assert verdict["not_entailed_count"] == 1
    assert verdict["all_reviewers_propose_entailed"] is False
    assert verdict["independent_semantic_truth_verified"] is False
    assert verdict["production_publication_approved"] is False


def test_supported_paraphrases_do_not_require_fixed_room_wording():
    accepted = [x for x in domain_cases() if x["oracle"] == ["entailed"]]
    assert len(accepted) == 7
    for row in accepted:
        result = assess_stage4_semantic_sufficiency(
            row["draft"], row["packet"], reviewer_envelopes=row["reviewer_envelopes"])
        assert result["all_reviewers_propose_entailed"]
        assert result["reviewers_concordant_entailment_count"] == 1
        assert result["production_publication_approved"] is False


def test_counterfactual_text_same_fact_and_same_claims_different_judgment():
    f = contexts()["fan"]
    good = case("good-fan", "ventilation", f,
                "An OFF command was issued to the extractor.", "entailed")
    bad = case("bad-fan", "ventilation", f,
               "The fan motor definitely stopped instantly due to humidity.",
               "not-entailed")
    assert good["draft"]["sections"][0]["sentences"][0]["claims"] == (
        bad["draft"]["sections"][0]["sentences"][0]["claims"])
    assert good["draft"]["sections"][0]["sentences"][0]["citations"] == (
        bad["draft"]["sections"][0]["sentences"][0]["citations"])
    result = benchmark_stage4_semantic_reviews([good, bad])
    assert result["false_accept_count"] == 0
    assert result["false_reject_count"] == 0
    assert result["no_real_model_judge_evaluation_claim"] is True


def test_two_reviewers_disagree_so_answer_is_withheld():
    row = domain_cases()[0]
    review = deepcopy(row["reviewer_envelopes"])
    review[1]["assessments"][0]["verdict"] = "insufficient"
    review[1]["assessments"][0]["supporting_fact_ids"] = []
    result = assess_stage4_semantic_sufficiency(
        row["draft"], row["packet"], reviewer_envelopes=review)
    assert result["reviewers_disagreed_count"] == 1
    assert "reviewer_disagreement" in result["reason_codes"]
    assert not result["all_reviewers_propose_entailed"]


def test_malicious_entailment_vote_with_unknown_fact_id_is_rejected():
    row = domain_cases()[0]
    reviews = deepcopy(row["reviewer_envelopes"])
    reviews[0]["assessments"][0]["supporting_fact_ids"] = ["f999"]
    r = assess_stage4_semantic_sufficiency(
        row["draft"], row["packet"], reviewer_envelopes=reviews)
    assert "invalid_review_fact_ids" in r["reason_codes"]
    assert r["fully_reviewed_sentences"] == 0
    assert not r["all_reviewers_propose_entailed"]


@pytest.mark.parametrize("edit", [
    lambda reviews: reviews.pop(),
    lambda reviews: reviews[0].update({"explanation": "I know it"}),
    lambda reviews: reviews[0]["assessments"][0].update({"sentence_id": "s999"}),
    lambda reviews: reviews[1]["assessments"][0].update({"verdict": "proved"}),
    lambda reviews: reviews[0]["assessments"][0].update({"chain_of_thought": "secret"}),
])
def test_review_envelopes_fail_closed_on_missing_extra_or_invalid(edit):
    row = domain_cases()[0]
    reviews = deepcopy(row["reviewer_envelopes"])
    edit(reviews)
    result = assess_stage4_semantic_sufficiency(
        row["draft"], row["packet"], reviewer_envelopes=reviews)
    assert not result["all_reviewers_propose_entailed"]
    assert result["production_publication_approved"] is False


def test_sentence_bound_to_exact_evidence_and_typed_claims():
    p = packet()
    a = contexts()["light"]
    b = contexts()["heat"]
    two = draft(a, b, text="The model describes two separately recorded commands.")
    req = build_stage4_semantic_review_request(two, p)
    verdict = assess_stage4_semantic_sufficiency(
        two, p, reviewer_envelopes=[vote(req, ["entailed"])] * 2)
    assert verdict["reviewers_concordant_entailment_count"] == 1
    assert verdict["production_publication_approved"] is False


def test_constructed_fourteen_case_scoreboard_catches_no_unsafe_claims():
    cases = domain_cases()
    result = benchmark_stage4_semantic_reviews(cases)
    assert result["case_count"] == 14
    assert result["sentence_count"] == 14
    assert result["domain_count"] == 6
    assert result["reference_supported_sentences"] == 7
    assert result["reference_unsupported_sentences"] == 7
    assert result["false_accept_count"] == 0
    assert result["false_reject_count"] == 0
    assert result["false_accept_rate"] == 0.0
    assert result["false_reject_rate"] == 0.0
    assert result["reference_judgments_are_supplied_not_proven"]
    assert result["no_production_activation"]


def test_benchmark_exposes_both_reviewers_wrong_agreement():
    rows = domain_cases()
    bad = next(x for x in rows if x["case_id"] == "heating-false-physical")
    req = build_stage4_semantic_review_request(bad["draft"], bad["packet"])
    bad["reviewer_envelopes"] = [vote(req, ["entailed"])] * 2
    metric = benchmark_stage4_semantic_reviews(rows)
    assert metric["false_accept_count"] == 1
    assert metric["false_accept_rate"] == round(1 / 7, 4)
    result = assess_stage4_semantic_sufficiency(
        bad["draft"], bad["packet"], reviewer_envelopes=bad["reviewer_envelopes"])
    # Reviewer agreement is NOT a proof of sentence truth.
    assert result["all_reviewers_propose_entailed"] is True
    assert result["independent_semantic_truth_verified"] is False
    assert result["production_publication_approved"] is False


def test_benchmark_detects_false_rejection_of_useful_explanation():
    rows = domain_cases()
    good = next(x for x in rows if x["case_id"] == "lighting-command")
    req = build_stage4_semantic_review_request(good["draft"], good["packet"])
    good["reviewer_envelopes"] = [vote(req, ["insufficient"])] * 2
    report = benchmark_stage4_semantic_reviews(rows)
    assert report["false_reject_count"] == 1
    assert report["false_reject_rate"] == round(1 / 7, 4)


def test_benchmark_rejects_unlabelled_duplicate_and_unsafe_cases():
    rows = domain_cases()
    rows[0]["case_id"] = "Private Bedroom Client Name"
    with pytest.raises(ValueError, match="metadata"):
        benchmark_stage4_semantic_reviews(rows)
    rows = domain_cases()
    rows[1]["case_id"] = rows[0]["case_id"]
    with pytest.raises(ValueError, match="metadata"):
        benchmark_stage4_semantic_reviews(rows)
    rows = domain_cases()
    rows[1]["oracle"] = ["unknown"]
    with pytest.raises(ValueError, match="oracle"):
        benchmark_stage4_semantic_reviews(rows)


def test_report_does_not_echo_private_sentence_facts_or_model_text():
    row = domain_cases()[0]
    row["draft"]["sections"][0]["sentences"][0]["text"] = (
        "PRIVATE-BEDROOM-SECRET the source records a command.")
    verdict = assess_stage4_semantic_sufficiency(
        row["draft"], row["packet"], reviewer_envelopes=row["reviewer_envelopes"])
    text = json.dumps(verdict)
    for forbidden in ("PRIVATE-BEDROOM", "3001", "2026-10", "f001",
                      "PRIVATE-BEDROOM-SECRET"):
        assert forbidden not in text


def test_original_production_publisher_never_imports_stage4b():
    root = Path(__file__).resolve().parents[1] / "rootfs" / "app"
    for name in ("mcp_agent_orchestrator.py", "final_answer_coordinator.py",
                 "causal_claim_publication.py", "app.py"):
        assert "stage4_semantic_sufficiency" not in (root / name).read_text(encoding="utf-8")

"""Paired reasoning evaluation must never give model credit for host-only data."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from evaluate_audit_reasoning import evaluate, extract_answer


def test_completed_response_extracts_only_model_advisory():
    entry = {
        "ai_analysis": {"status": "completed"},
        "message": (
            "### Reasoned answer (AI interpretation; not independent evidence)\n"
            "Possible recovery; confirm with a new live read.\n\n"
            "### Performance leaders\n"
            "Octopus Live Meter generates excessive hub load.\n"
        ),
    }
    answer, status = extract_answer(entry)
    assert status == "available"
    assert "Possible recovery" in answer
    assert "Octopus" not in answer


def test_disabled_or_timed_out_ai_does_not_receive_host_report_credit():
    benchmark = {"cases": [{
        "id": "hub", "checks": [
            {"name": "Overload", "indicators": ["excessive hub load"]},
        ],
    }]}
    host_message = "### Performance leaders\nApp generates excessive hub load."
    for status in ("disabled_by_configuration", "timed_out",
                   "unavailable", "empty_response"):
        output = evaluate(
            benchmark,
            {"hub": {"ai_analysis": {"status": status}, "message": host_message}},
            {},
        )
        result = output["cases"][0]["results"]["gemma"]
        assert result["status"] == status
        assert result["indicator_coverage"] == "0/1"
        assert result["covered"] == []


def test_missing_advisory_is_not_scored_from_host_evidence():
    answer, status = extract_answer({
        "ai_analysis": {"status": "completed"},
        "message": "### Performance leaders\nApp generates excessive hub load.",
    })
    assert answer == ""
    assert status == "missing_advisory_section"


def test_lexical_coverage_and_red_flags_are_only_review_signals():
    benchmark = {"cases": [{
        "id": "pairing", "title": "Pairing chronology",
        "checks": [
            {"name": "Later success", "indicators": ["later success", "subsequent success"]},
            {"name": "Limits", "indicators": ["not proven", "not established"]},
        ],
        "potential_overclaims": ["permanently resolved"],
    }]}
    results = evaluate(
        benchmark,
        {"pairing": {"answer": "Later success, but continuing health is not proven."}},
        {"pairing": {"answer": "Permanently resolved."}},
    )["cases"][0]["results"]
    assert results["gemma"]["indicator_coverage"] == "2/2"
    assert results["gemma"]["potential_overclaims_for_manual_review"] == []
    assert results["claude"]["indicator_coverage"] == "0/2"
    assert results["claude"]["potential_overclaims_for_manual_review"] == [
        "permanently resolved"
    ]


def test_missing_model_case_is_reported_not_zero_quality():
    benchmark = {"cases": [{"id": "a", "checks": [{"name": "x", "indicators": ["x"]}]}]}
    result = evaluate(benchmark, {}, {})["cases"][0]["results"]["gemma"]
    assert result["status"] == "missing"
    assert result["indicator_coverage"] == "0/1"

"""0.17.33: archive observations must reach final answers even when omitted.

0.17.32 successfully placed four archived sensor rows in the OFF evidence
graph, but a model answer that discussed only 'sensor inactivity' and omitted
the Historical Journal entirely was not corrected by the negative-only guard.
"""
from __future__ import annotations

from causal_answer_plan import build_causal_answer_plan
from causal_claim_verification import verify_causal_claims
from causal_evidence_graph import build_causal_evidence_graph
from focal_evidence_reconciliation import ensure_archived_sensor_source_disclosure
from test_archived_sensor_source_reconciliation_0_17_32 import (
    QUESTION, assembled_receipts,
)


def _graph():
    return build_causal_evidence_graph(assembled_receipts(), QUESTION)


def test_pre_synthesis_plan_requires_archive_mcp_source_comparison():
    plan = build_causal_answer_plan(_graph(), QUESTION)
    assert plan is not None
    archive = plan["evidence"]["archivedSensorObservations"]
    assert archive["source"] == "HomeBrain local Historical Journal"
    assert archive["count"] == 4
    assert archive["verifiedMcpWindowCount"] == 2
    assert archive["verifiedMcpReturnedEventCount"] == 0
    assert archive["historyComplete"] is False
    assert archive["notProofOfOffCauseOrTimer"] is True
    assert len(archive["sourceRows"]) == 4
    assert {row["label"] for row in archive["sourceRows"]} == {
        "Example FP300", "Example Soft Sensor",
    }
    assert all(
        row["timestampBasis"] == "collector-received"
        for row in archive["sourceRows"]
    )
    assert any(
        "Explicitly report the local Historical Journal" in obligation
        for obligation in plan["answerObligations"]
    )


def test_omitting_journal_facts_is_corrected_even_without_negative_claim():
    # The actual 0.17.32 response reported temporal sensor correlation but
    # never identified the source, archive counts, or timestamp limitations.
    draft = (
        "The OFF cause remains unverified.\n\n"
        "### OFF Event Analysis\n"
        "- The OFF transition occurred near sensor inactivity, but no "
        "initiating automation is proven.\n\n"
        "### Summary of Findings\n"
        "| Sensor History | Correlated | Inactivity shortly after OFF. |"
    )
    corrected, issues = verify_causal_claims(
        draft, assembled_receipts(), QUESTION
    )
    assert "archived_sensor_source_disclosure" in issues
    assert "Historical Journal (partial)" in corrected
    assert "4 archived sensor observations" in corrected
    assert "Example FP300: inactive, active" in corrected
    assert "Example Soft Sensor: inactive, active" in corrected
    assert "2 verified bounded MCP sensor window(s) returned 0 event rows" in corrected
    assert "collector-received" in corrected
    assert "Neither a five-second timer execution nor the OFF command initiator" in corrected
    assert corrected.index("Historical Journal (partial)") < corrected.index(
        "### Summary of Findings"
    )


def test_correct_journal_source_and_timestamp_caveat_does_not_duplicate():
    drafted = (
        "The Historical Journal retained four partial sensor events, while "
        "verified MCP windows returned zero rows. Collector reception time "
        "is not the original sensor event time or proof of an OFF command."
    )
    assert ensure_archived_sensor_source_disclosure(drafted, _graph()) == (
        drafted, False
    )


def test_no_archive_rows_does_not_add_unfounded_observations():
    graph = _graph()
    graph["transitionEvidence"]["off"]["archivedSensorEvidence"] = {
        "archivedObservationCount": 0
    }
    original = "The OFF cause remains unverified."
    assert ensure_archived_sensor_source_disclosure(original, graph) == (
        original, False
    )


def test_journal_disclosure_is_required_when_model_mentions_it_without_caveat():
    text = (
        "The Historical Journal indicates nearby sensor inactivity. "
        "This does not prove the OFF cause."
    )
    corrected, modified = ensure_archived_sensor_source_disclosure(text, _graph())
    assert modified
    assert "collector-received" in corrected
    assert corrected.count("Historical Journal (partial)") == 1

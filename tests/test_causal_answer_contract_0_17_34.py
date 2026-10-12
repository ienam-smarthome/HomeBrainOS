"""0.17.34: close the 0.17.33 causal-answer disclosure and grammar gaps.

Covers the *actual* live pattern: the model named the Historical Journal and
collector reception but omitted four archived rows versus two empty MCP
windows; a command-claim regex left an ungrammatical 'command.by this app'.
"""
from __future__ import annotations

from causal_answer_plan import guard_causal_answer_claim_boundaries
from causal_claim_verification import verify_causal_claims
from causal_evidence_graph import build_causal_evidence_graph
from focal_evidence_reconciliation import ensure_archived_sensor_source_disclosure
from test_archived_sensor_source_reconciliation_0_17_32 import (
    QUESTION, assembled_receipts,
)


def _graph():
    return build_causal_evidence_graph(assembled_receipts(), QUESTION)


def test_live_response_with_journal_timestamp_but_missing_counts_is_incomplete():
    draft = (
        "### Event Timeline\n"
        "- 08:18:23: Light switched OFF.\n"
        "- 08:18:24–08:18:25: Example FP300 and Soft Sensors reported "
        "inactive (Recorded in the Historical Journal; these timestamps "
        "are collector-received).\n\n"
        "### Causal Analysis\n"
        "The Historical Journal shows both sensors reporting inactive within "
        "1–2 seconds after OFF; not proven causation.\n\n"
        "### Summary of Findings\n"
        "| Sensor Inactivity | Correlated | Historical Journal (after OFF) |"
    )
    answer, issues = verify_causal_claims(
        draft, assembled_receipts(), QUESTION
    )
    assert "archived_sensor_source_disclosure" in issues
    assert "Historical source coverage:" in answer
    assert "Historical Journal retained 4 partial sensor observations" in answer
    assert "2 verified bounded MCP sensor windows returned 0 event rows" in answer
    assert "collector reception" in answer
    assert answer.count("Historical source coverage:") == 1
    assert answer.index("Historical source coverage:") < answer.index(
        "### Summary of Findings"
    )


def test_full_numeric_source_comparison_stays_single_without_repeat():
    complete = (
        "The Historical Journal retained 4 partial sensor observations, "
        "while 2 verified bounded MCP sensor windows returned 0 event rows. "
        "These times are collector-received rather than original event times, "
        "and cannot prove an OFF timer."
    )
    assert ensure_archived_sensor_source_disclosure(complete, _graph()) == (
        complete, False
    )


def test_bounded_app_command_claim_remains_intact_in_running_sentence():
    text = (
        "App logs returned zero entries, and no command issued by this "
        "app was found in the bounded command history."
    )
    corrected, changed = guard_causal_answer_claim_boundaries(
        text, _graph(), QUESTION
    )
    assert not changed
    assert corrected == text
    assert "command.by this app" not in corrected
    assert "issued no command.by" not in corrected


def test_explicit_global_hubitat_command_claim_is_scoped_without_bad_splice():
    text = (
        "App logs returned zero entries, and Hubitat issued no commands "
        "during that event."
    )
    corrected, changed = guard_causal_answer_claim_boundaries(
        text, _graph(), QUESTION
    )
    assert changed
    assert "returned bounded Hubitat command history" in corrected
    assert "Hubitat issued no commands" not in corrected
    assert "command.during" not in corrected
    assert "history. during" not in corrected


def test_math_approx_and_arrow_render_as_plain_status():
    draft = (
        "### Event Timeline\n"
        "17:10:15 $\\rightarrow$ 17:14:04 (229 seconds).\n"
        "| Sensor Inactivity | Correlated | Reported $\\approx$1s after OFF |"
    )
    answer, issues = verify_causal_claims(
        draft, assembled_receipts(), QUESTION
    )
    assert "$\\approx$" not in answer
    assert "$\\rightarrow$" not in answer
    assert "≈1s" in answer
    assert "→" in answer
    assert "unsupported_math_status_notation" in issues

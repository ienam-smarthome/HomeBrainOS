"""0.17.30 evidence-reconciliation contracts, grounded in the 17:14 OFF case."""
from __future__ import annotations

from copy import deepcopy

from causal_evidence_graph import build_causal_evidence_graph
from causal_claim_verification import verify_causal_claims
from focal_evidence_reconciliation import (
    reconcile_window_coverage,
    summarize_journal_app_logs,
    guard_unproven_on_button_initiation,
)
from test_independent_transition_provenance_0_17_15 import _records, QUESTION


def test_verified_absolute_windows_replace_stale_false_metadata_not_completeness():
    original = {
        "status": "pre-focal-not-observed-in-returned-pages",
        "preFocalObserved": False,
        "upstreamHistoricalWindowAvailable": False,
        "historicalCompletenessVerified": False,
    }
    actual = reconcile_window_coverage(original, [
        {"deviceId": "7774", "status": "verified-window", "eventCount": 2},
        {"deviceId": "7756", "status": "verified-window", "eventCount": 2},
    ])
    assert original["upstreamHistoricalWindowAvailable"] is False
    assert actual["upstreamHistoricalWindowAvailable"] is True
    assert actual["verifiedAbsoluteWindowDeviceIds"] == ["7756", "7774"]
    assert actual["attemptedAbsoluteWindowCount"] == 2
    assert actual["verifiedAbsoluteWindowCount"] == 2
    assert actual["status"] == "verified-window-available-coverage-incomplete"
    assert actual["historicalCompletenessVerified"] is False
    assert actual["unobservedIsNotInactive"] is True


def test_unverified_or_empty_window_does_not_prove_coverage():
    result = reconcile_window_coverage(
        {"status": "pre-focal-not-observed-in-returned-pages"},
        [{"deviceId": "7774", "status": "unverified-window", "eventCount": 0}],
    )
    assert result["upstreamHistoricalWindowAvailable"] is False
    assert result["historicalCompletenessVerified"] is False
    assert result["verifiedAbsoluteWindowCount"] == 0
    assert result["status"] == "pre-focal-not-observed-in-returned-pages"


def test_app_log_reconciliation_is_allowlisted_scoped_and_private():
    secret = "some private household message never for dashboard"
    result = summarize_journal_app_logs({
        "events": [{
            "stream": "logs", "app_id": "4015", "message": secret,
            "timestamp_basis": "collector-received",
        }, {
            "stream": "logs", "app_id": "9099", "message": "other app",
        }, {
            "stream": "events", "app_id": "4015", "message": "not a log",
        }],
        "gaps": [{"stream": "logs", "reason": "restart"}],
    }, app_id="4015", since="2026-10-12T16:13:52Z",
       until="2026-10-12T16:14:10Z", native_count=0)
    assert result["journalCount"] == 1
    assert result["nativeMcpCount"] == 0
    assert result["journalTimestampBases"] == ["collector-received"]
    assert result["journalGapCount"] == 1
    assert result["coverageComplete"] is False
    assert result["commandProducerVerifiedByTheseCounts"] is False
    assert secret not in str(result)
    assert "9099" not in str(result)


def test_absent_native_and_journal_log_rows_never_prove_rule_failed():
    result = summarize_journal_app_logs(
        {"events": [], "gaps": []},
        app_id="4015", since="2026-10-12T16:13:52Z",
        until="2026-10-12T16:14:10Z", native_count=0,
    )
    assert result["journalChecked"]
    assert result["journalCount"] == 0
    assert result["zeroRowsDoNotProveNonexecution"] is True
    assert result["status"] == "no-archived-logs-in-bounded-window"


def test_button_guard_does_not_promote_late_button_to_initiator():
    claim = (
        "17:10:15: Light switched ON. This was initiated by a physical "
        "push of Bedroom 1 dimmer - 1, followed by a brightness correction."
    )
    guarded, changed = guard_unproven_on_button_initiation(claim, {
        "transitionEvidence": {"on": {"directCommand": None}}
    })
    assert changed
    assert "initiated by a physical" not in guarded
    assert "Bedroom 1 dimmer - 1" in guarded
    assert "does not prove it initiated ON" in guarded
    assert "brightness correction" in guarded


def test_positive_direct_on_command_is_not_downgraded():
    claim = "This was initiated by a physical push of Bedroom 1 dimmer - 1."
    corrected, changed = guard_unproven_on_button_initiation(claim, {
        "transitionEvidence": {"on": {
            "directCommand": {"producer": {"id": "4015"}}
        }}
    })
    assert not changed
    assert corrected == claim


def test_scoped_archived_app_log_count_reaches_graph_without_promoting_producer():
    evidence = _records()
    end = evidence[0]["details"]["temporalAnalysis"]["observedIntervals"][-1]["end"]
    from datetime import datetime, timedelta, timezone
    t = datetime.fromisoformat(end)
    before = (t - timedelta(seconds=12)).isoformat()
    after = (t + timedelta(seconds=6)).isoformat()
    summary = summarize_journal_app_logs(
        {"events": [{"stream": "logs", "app_id": "4015",
                     "message": "private app internals"}], "gaps": []},
        app_id="4015", since=before, until=after, native_count=0,
    )
    evidence.append({
        "tool": "homebrain_archived_app_log_reconciliation",
        "success": True,
        "arguments": {"appId": "4015", "since": before, "until": after},
        "details": summary,
    })
    graph = build_causal_evidence_graph(evidence, QUESTION)
    off = graph["transitionEvidence"]["off"]
    assert off["archivedAppLogReconciliation"]["journalCount"] == 1
    assert off["archivedAppLogReconciliation"]["commandProducerVerifiedByTheseCounts"] is False
    assert off["directCommand"] is None
    assert "private app internals" not in str(graph)


def test_causal_answer_guard_renders_math_status_and_marks_association():
    text = (
        "Light switched ON. This was initiated by a physical push of "
        "Bedroom 1 dimmer - 1, followed by a brightness correction.\n"
        "| Direct Command | $\\times$ Not Found | Unverified |\n"
        "| State Reporter | $\\checkmark$ Verified | Hue |"
    )
    answer, issues = verify_causal_claims(text, _records(), QUESTION)
    assert "Bedroom 1 dimmer - 1" in answer
    assert "initiated by a physical push" not in answer
    assert "$\\times$" not in answer and "$\\checkmark$" not in answer
    assert "✗" in answer and "✓" in answer
    assert "unsupported_math_status_notation" in issues

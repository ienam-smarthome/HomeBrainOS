"""V3 Stage A: inspect legacy publication without changing any published answer.

Counter-only shadow telemetry. Matching a time token is NOT a causation
claim verifier and no original model text or entity ID is persisted.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from request_metrics import RequestMetrics
from unified_incident_synthesis import (
    publication_shadow_assessment,
    reconcile_ledger_if_needed,
)
from unified_incident_digest import source_incident_digest


def _row(i, name, kind, when, value):
    return {
        "device_id": str(i), "device_name": name,
        "date": "2026-10-30T" + when + "+00:00",
        "event_class": kind, "timestamp_basis": "source",
        "value": value,
    }


def _facts():
    rows = []
    for i, name in ((101, "Zone Alpha Light"), (102, "Zone Beta Light")):
        rows += [
            _row(i, name, "journal_source_switch_on", "14:50:37.871", "on"),
            _row(i, name, "journal_source_switch_off", "14:51:36.184", "off"),
        ]
    return {
        "target_device_ids": ["101", "102"],
        "target_coverage": [
            {"device_id": "101", "device_name": "Zone Alpha Light",
             "reported_switch_off": 1},
            {"device_id": "102", "device_name": "Zone Beta Light",
             "reported_switch_off": 1},
        ],
        "incident_ledger": rows,
        "incident_ledger_total": len(rows),
        "missing_switch_history_for_targets": [
            "Zone Alpha Light", "Zone Beta Light"],
        "journal_source_observations": 4,
        "journal_collector_observations": 0,
        "journal_gap_count": 2,
        "archived_app_checks": [],
    }


def _capture(draft, facts):
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        answer = reconcile_ledger_if_needed(draft, facts)
        snap = metrics.snapshot()
        return answer, snap
    finally:
        metrics.reset(token)


def test_legacy_digest_still_replaces_even_a_clean_cause_qualified_draft():
    facts = _facts()
    good = (
        "The lights reported ON at 14:50:37 and OFF at 14:51:36. "
        "Neither original initiating controller is independently identified."
    )
    (answer, changed), snapshot = _capture(good, facts)
    assert changed is True
    assert answer == source_incident_digest(facts)
    assert snapshot["counters"]["v3_shadow_legacy_digest_replaced"] == 1
    assert snapshot["counters"]["v3_shadow_publications_seen"] == 1
    assert snapshot["counters"]["v3_shadow_draft_mentions_source_time"] == 1
    assert snapshot["counters"]["v3_shadow_source_time_token_matches"] == 2
    assert "v3_shadow_draft_contradiction" not in snapshot["counters"]
    # Publication measurements do not leak original draft or device names.
    assert good not in str(snapshot)
    assert "Zone Alpha" not in str(snapshot)


def test_overclaim_is_not_exposed_when_current_fallback_is_active():
    facts = _facts()
    draft = "No OFF states were reported, so an external controller caused ON."
    (message, changed), snapshot = _capture(draft, facts)
    assert changed is True
    assert message == source_incident_digest(facts)
    assert snapshot["counters"]["v3_shadow_draft_contradiction"] == 1
    assert snapshot["counters"]["v3_shadow_legacy_digest_replaced"] == 1


def test_clean_no_gap_draft_stays_unchanged_and_is_measured():
    facts = _facts()
    facts["missing_switch_history_for_targets"] = []
    draft = "The verified source reports ON at 14:50:37; origin unverified."
    (message, changed), snapshot = _capture(draft, facts)
    assert (message, changed) == (draft, False)
    assert snapshot["counters"]["v3_shadow_legacy_draft_preserved"] == 1
    assert snapshot["counters"]["v3_shadow_draft_mentions_source_time"] == 1


def test_non_archive_ledger_fallback_is_counted_without_content_leak():
    facts = _facts()
    facts["journal_source_observations"] = 0
    facts["incident_ledger"] = [
        _row(101, "Zone Alpha Light", "reported_switch_off",
             "14:51:36.184", "off")]
    (message, changed), snap = _capture("Some observations occurred.", facts)
    assert changed is True
    assert "Verified incident ledger" in message
    assert snap["counters"]["v3_shadow_legacy_ledger_replaced"] == 1


def test_empty_incident_keeps_draft_and_does_not_invent_source_mentions():
    facts = _facts()
    facts["incident_ledger"] = []
    facts["journal_source_observations"] = 0
    text = "The evidence is unavailable."
    (message, changed), snap = _capture(text, facts)
    assert not changed and message == text
    assert snap["counters"]["v3_shadow_legacy_draft_preserved"] == 1
    assert "v3_shadow_draft_mentions_source_time" not in snap["counters"]


def test_shadow_is_not_claim_attestation_and_ignores_collector_clock():
    facts = _facts()
    facts["incident_ledger"].append({
        **_row(101, "Zone Alpha Light",
               "journal_received_switch_on", "14:50:39.278", "on"),
        "timestamp_basis": "collector-received",
    })
    a = publication_shadow_assessment(
        "14:50:39 appeared in a received record.", facts)
    assert a["source_time_tokens_mentioned"] == 0
    assert a["source_time_tokens_available"] == 2
    b = publication_shadow_assessment(
        "The source shows 14:50:37 and proves a sensor caused it!", facts)
    assert b["source_time_tokens_mentioned"] == 1
    # A matched clock does not imply verified cause. The shadow is neutral.
    assert "causal_verdict" not in b


def test_shadow_request_context_isolation():
    m = RequestMetrics()
    tok = m.begin()
    try:
        reconcile_ledger_if_needed("14:50:37", _facts())
        assert m.snapshot()["counters"]["v3_shadow_publications_seen"] == 1
    finally:
        m.reset(tok)
    tok2 = m.begin()
    try:
        assert "v3_shadow_publications_seen" not in m.snapshot()["counters"]
    finally:
        m.reset(tok2)

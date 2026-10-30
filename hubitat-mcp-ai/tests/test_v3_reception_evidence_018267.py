"""V3 source/receiver temporal evidence and archive-count provenance.

This fixture deliberately renames targets and sensors and tests the receipt
clock, not sensor source time. The same four collector gaps may be reported by
multiple archive queries; counts are *not* unique outages.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_reception_evidence import analyse_collector_reception
from unified_investigation_bridge import collect_unified_evidence
from unified_incident_digest import source_incident_digest
from test_reception_pattern_018260 import Q, ON, OFF, ACTIVE, INACTIVE, native, lookup

QUESTION = Q.replace("Zone Alpha Light", "North Lamp").replace("Zone Beta Light", "South Lamp")


def iso(value, delta=0):
    d = datetime.fromisoformat("2026-10-30T" + value + "+00:00")
    return (d + timedelta(seconds=delta)).isoformat()


def switch_rows(ident, lag=0):
    observations = []
    for state, times in (("on", ON), ("off", OFF)):
        for value in times:
            observations.extend([
                {"device_id": str(ident), "attribute": "switch",
                 "value": state, "date": iso(value, lag),
                 "timestamp_basis": "source"},
                {"device_id": str(ident), "attribute": "switch",
                 "value": state, "date": iso(value, lag + 1.410),
                 "timestamp_basis": "collector-received"},
            ])
    return sorted(observations, key=lambda x: x["date"])


def switch_receipt(ident, stagger=0):
    return {"success": True, "tool": "homebrain_evidence_journal",
            "evidence_kind": "group_archived_switch_history",
            "mutates": False, "arguments": {"device_id": str(ident)},
            "details": {"deviceId": str(ident),
                        "observations": switch_rows(ident, stagger),
                        "gapCount": 4, "truncated": False}}


def input_receipt(ident, *, count, sample, truncated):
    return {"success": True, "tool": "homebrain_evidence_journal",
            "evidence_kind": "group_archived_input_history",
            "mutates": False, "arguments": {"device_id": str(ident)},
            "details": {"deviceId": str(ident),
                        "observations": sample,
                        "returnedObservationCount": count,
                        "gapCount": 4, "truncated": truncated}}


def input_rows(ident):
    return sorted([
        *({"device_id": str(ident), "attribute": "motion", "value": "active",
           "date": iso(t), "timestamp_basis": "collector-received"}
          for t in ACTIVE),
        *({"device_id": str(ident), "attribute": "motion", "value": "inactive",
           "date": iso(t), "timestamp_basis": "collector-received"}
          for t in INACTIVE),
    ], key=lambda x: x["date"])


def replay(ids=(101, 102, 201, 202, 203)):
    first, second, candidate, noisy, empty = ids
    rows = [
        lookup(first, "North Lamp"), lookup(second, "South Lamp"),
        native(first), native(second),
        native(candidate), native(noisy), native(empty),
        switch_receipt(first), switch_receipt(second, 1.01),
        input_receipt(noisy, count=160,
                      sample=input_rows(noisy) * 2, truncated=True),
        input_receipt(candidate, count=10,
                      sample=input_rows(candidate), truncated=False),
        input_receipt(empty, count=0, sample=[], truncated=False),
    ]
    return rows


def test_motion_candidate_same_receiver_clock_and_stagger():
    f = collect_unified_evidence(replay(), QUESTION)
    assert f is not None
    assert f["archived_input_collector_observations"] == 30
    assert f["archived_input_returned_observations"] == 170
    assert f["archived_input_gap_count"] == 12  # legacy QUERY sum, not outages
    assert len(f["archived_input_gap_queries"]) == 3
    summary = f["same_receiver_evidence"]
    assert summary["schema"] == "collector-reception-evidence.v1"
    candidate = summary["candidates"][0]
    assert candidate["input_id"] == "201"
    assert candidate["one_to_one_within_windows"] is True
    assert candidate["matched_on"] == candidate["matched_off"] == 5
    assert candidate["on_receiver_delay_seconds"]["min"] == 0.126
    assert 0.69 <= candidate["on_receiver_delay_seconds"]["max"] <= 0.72
    assert 10.13 <= candidate["off_receiver_delay_seconds"]["min"] <= 10.15
    assert 10.35 <= candidate["off_receiver_delay_seconds"]["max"] <= 10.38
    assert candidate["sensor_source_order_verified"] is False
    assert candidate["initiator_verified"] is False
    assert summary["light_pair"]["paired_transitions"] == 10
    assert summary["light_pair"]["source_event_stagger_seconds"]["min"] == 1.01
    assert summary["light_reception_lag"]["min"] == 1.41


def test_digest_shows_full_returned_counts_and_not_duplicate_gaps():
    f = collect_unified_evidence(replay(), QUESTION)
    ans = source_incident_digest(f)
    assert ans
    assert "**Strongest observed pattern:** Input device 201" in ans
    assert "5/5 paired active" in ans
    assert "170 input rows returned" in ans
    assert "30 reception-only observation(s) in retained receipt samples" in ans
    assert "device 201: 4 gap interval(s) reported" in ans
    assert "12 recorded connection gap" not in ans
    assert "cannot be summed as distinct collector outages" in ans
    assert "across 10 paired transitions" in ans
    assert "sensor event order" in ans


def test_ids_and_labels_change_without_changing_evidence_relationship():
    renamed = (701, 702, 803, 804, 805)
    facts = collect_unified_evidence(replay(renamed), QUESTION)
    # Lookup verifies names independently of the question; this check is
    # about the relative timing independent of the chosen positive IDs.
    assert facts
    answer = facts["same_receiver_evidence"]
    assert answer["candidates"][0]["input_id"] == "803"
    assert answer["candidates"][0]["matched_on"] == 5
    assert answer["candidates"][0]["matched_off"] == 5
    assert answer["candidates"][0]["one_to_one_within_windows"] is True


def test_truncated_or_collector_only_missing_light_pair_cannot_certify():
    rows = replay()
    f = collect_unified_evidence(rows, QUESTION)
    assert f
    inputs = [{"device_id": "201", "received_at": x["date"],
               "value": x["value"]} for x in input_rows(201)]
    # A reported return count greater than retained data is insufficient to
    # claim exact one-to-one matching.
    incomplete = analyse_collector_reception(
        f["incident_ledger"], inputs, input_returned_counts={"201": 11})
    assert incomplete["candidates"] == []
    rows = replay()
    for row in rows:
        if row.get("evidence_kind") == "group_archived_switch_history":
            row["details"]["observations"] = [
                x for x in row["details"]["observations"]
                if x["timestamp_basis"] == "source"]
    facts = collect_unified_evidence(rows, Q)
    assert facts
    assert facts["same_receiver_evidence"]["candidates"] == []

"""V3 Stage B: source roles and positive/negative issuer witness controls."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_witness_ledger import build_witness_coverage_ledger
from request_metrics import RequestMetrics
from unified_incident_synthesis import reconcile_ledger_if_needed


def row(device, kind, time, *, app="", value=""):
    return {
        "device_id": str(device), "device_name": "Generic Zone Device",
        "date": f"2026-10-30T{time}+00:00", "event_class": kind,
        "app_id": app, "value": value,
        "timestamp_basis": "source" if kind.startswith("journal_source") else "",
    }


def receipt(device, *, journal=False, empty=True, mutates=False):
    if journal:
        return {
            "tool": "homebrain_evidence_journal", "success": True,
            "mutates": mutates, "effect": "read",
            "evidence_kind": "group_archived_switch_history",
            "arguments": {"device_id": str(device)},
            "details": {"observations": [], "truncated": False, "gapCount": 2},
        }
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "mutates": mutates, "effect": "read",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": str(device)}},
        "details": {"observedEvents": [] if empty else [{}]},
    }


def facts(rows):
    return {
        "source_attested": True,
        "target_device_ids": ["101"],
        "target_coverage": [{"device_id": "101", "journal_gaps": 2}],
        "incident_ledger": rows,
        "missing_switch_history_for_targets": ["Generic Zone Device"],
        "journal_source_observations": 1,
        "journal_collector_observations": 1,
        "input_app_relationships": [{
            "input_device_id": "201",
            "input_notified_app_ids": ["3001"],
            "relationship": "shared-observed-target-command-app",
        }],
        "independent_input_observations": [{
            "device_id": "201", "attribute": "motion", "value": "active",
            "time": "2026-10-30T15:00:00.000+00:00",
            "timestamp_basis": "source-reported",
            "source_read": 4,
        }],
        "archived_input_reception_patterns": [{
            "device_id": "202", "on_near_active_receptions": 5,
            "cross_clock_order_verified": False,
        }],
    }


def test_positive_control_matching_explicit_hubitat_on_command_and_state():
    fs = facts([
        row(101, "issued_on", "15:01:00.100", app="3001"),
        row(101, "reported_switch_on", "15:01:00.450", value="on"),
        row(101, "journal_received_switch_on", "15:01:01.920", value="on"),
    ])
    ledger = build_witness_coverage_ledger(
        fs, [receipt(101), receipt(101, journal=True)])
    assert ledger["schema"] == "causal-witness-ledger.v1"
    assert ledger["shadow_only"] is True
    assert ledger["issuer_verified_target_count"] == 1
    match = ledger["immediate_hubitat_on_command_matches"][0]
    assert match["hubitat_app_id"] == "3001"
    assert match["command_to_state_ms"] == 350
    assert match["verification"] == "recorded-hubitat-immediate-command"
    assert match["upstream_reason_verified"] is False
    assert match["physical_ack_verified"] is False
    assert ledger["root_cause_verified"] is False
    assert ledger["source_timed_input_witness_count"] == 1
    assert all(w["clock_basis"] != "collector-received" or
               w["role"] != "input-report" for w in ledger["witnesses"])


def test_real_incident_shape_setlevel_after_on_is_not_an_on_issuer():
    fs = facts([
        row(101, "journal_source_switch_on", "14:50:37.871", value="on"),
        row(101, "issued_setlevel", "14:50:38.911", app="4013"),
        row(101, "journal_received_switch_on", "14:50:39.277", value="on"),
        row(101, "journal_source_switch_off", "14:51:36.184", value="off"),
    ])
    ledger = build_witness_coverage_ledger(
        fs, [receipt(101), receipt(101, journal=True)])
    assert ledger["issuer_verified_target_count"] == 0
    assert ledger["immediate_hubitat_on_command_matches"] == []
    assert ledger["target_source_coverage"][0]["command_witnesses"] == 1
    assert ledger["target_source_coverage"][0]["journal_switch"] == "observed-source"
    assert ledger["target_source_coverage"][0]["complete_historical_coverage"] is False
    assert ledger["can_prove_absence_from_empty_history"] is False
    assert ledger["observed_input_app_relationships"][0][
        "is_historical_execution_proof"] is False


def test_different_device_or_later_command_not_used_as_issuer():
    fs = facts([
        row(101, "reported_switch_on", "15:01:00.450", value="on"),
        row(101, "issued_on", "15:01:01.000", app="3001"),
        row(102, "issued_on", "15:01:00.100", app="3002"),
    ])
    ledger = build_witness_coverage_ledger(fs, [receipt(101)])
    assert ledger["issuer_verified_target_count"] == 0


def test_no_app_id_or_collector_only_state_never_verifies_issuer():
    fs = facts([
        row(101, "issued_on", "15:01:00.100", app=""),
        row(101, "journal_received_switch_on", "15:01:00.450", value="on"),
    ])
    ledger = build_witness_coverage_ledger(fs, [receipt(101, journal=True)])
    assert ledger["immediate_hubitat_on_command_matches"] == []
    fs["incident_ledger"][0]["app_id"] = "3001"
    ledger = build_witness_coverage_ledger(fs, [receipt(101, journal=True)])
    assert ledger["immediate_hubitat_on_command_matches"] == []


def test_failed_empty_or_mutating_reads_do_not_establish_complete_coverage():
    fs = facts([row(101, "journal_source_switch_on", "15:01:00.450", value="on")])
    ledger = build_witness_coverage_ledger(fs, [
        receipt(101, mutates=True), receipt(101, journal=True, mutates=True)])
    coverage = ledger["target_source_coverage"][0]
    assert coverage["device_history"] == "not-queried"
    # Typed input facts remain grounded only in the independently verified
    # collector; this ledger never synthesizes new source input facts.
    assert coverage["journal_switch"] == "observed-source"
    assert coverage["original_upstream_command_source"] == "not-independently-attested"


def test_immutable_witness_id_and_bounded_output_do_not_depend_on_row_order():
    entries = [
        row(101, "reported_switch_off", "15:01:01.000", value="off"),
        row(101, "issued_on", "15:01:00.100", app="3001"),
        row(101, "reported_switch_on", "15:01:00.450", value="on"),
    ]
    a = build_witness_coverage_ledger(facts(entries), [])
    b = build_witness_coverage_ledger(facts(list(reversed(entries))), [])
    assert a["witnesses"] == b["witnesses"]
    clipped = build_witness_coverage_ledger(facts(entries), [], max_witnesses=1)
    assert clipped["witness_total"] == 4   # 3 target + 1 input
    assert clipped["witnesses_omitted"] == 3
    assert len(clipped["witnesses"]) == 1
    assert clipped["issuer_verified_target_count"] == 1


def test_aggregate_shadow_metrics_and_original_publication_unchanged():
    fs = facts([
        row(101, "journal_source_switch_on", "14:50:37.871", value="on"),
        row(101, "issued_setlevel", "14:50:38.911", app="4013"),
    ])
    fs["incident_ledger_total"] = len(fs["incident_ledger"])
    fs["v3_witness_ledger"] = build_witness_coverage_ledger(
        fs, [receipt(101), receipt(101, journal=True)])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        draft = ("Device reported ON at 14:50:37, but original initiator "
                 "is not verified.")
        answer, changed = reconcile_ledger_if_needed(draft, fs)
        assert changed and answer != draft
        c = metrics.snapshot()["counters"]
        assert c["v3_witness_total"] == 3  # source switch, level command, input
        assert c["v3_witness_source_inputs"] == 1
        assert c.get("v3_witness_immediate_command_matches", 0) == 0
        assert c["v3_witness_targets_without_on_issuer"] == 1
        # The synthetic one-switch fixture can use either existing safe
        # publication path; Stage B must not change either decision.
        assert (c.get("v3_shadow_legacy_digest_replaced", 0)
                + c.get("v3_shadow_legacy_ledger_replaced", 0)) == 1
    finally:
        metrics.reset(token)


def test_unattested_or_empty_facts_no_witness_ledger():
    assert build_witness_coverage_ledger(None, []) is None
    assert build_witness_coverage_ledger({"target_device_ids": ["101"]}, []) is None

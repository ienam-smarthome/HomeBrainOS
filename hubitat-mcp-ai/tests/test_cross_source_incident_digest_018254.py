"""Cross-source incident digest must retain *every* verified target.

Reproduces v0.18.253's Bathroom journal recovery with the independently
read Shower Light native ON/command-off/OFF events. No live Hubitat writes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from unified_incident_digest import source_incident_digest
from unified_incident_synthesis import reconcile_ledger_if_needed


def _row(device, name, when, kind, value="", app=""):
    return {
        "device_id": str(device), "device_name": name,
        "date": "2026-10-30T" + when + "+00:00",
        "event_class": kind, "value": value,
        "app_id": app,
        **({"timestamp_basis": "source"} if kind.startswith("journal_source") else {}),
    }


def _facts():
    entries = []
    for i, name in ((7818, "Bathroom Light 1"), (7821, "Bathroom Light 2")):
        for state, when in [("on", "14:50:37.871"), ("off", "14:52:26.001"),
                            ("on", "15:07:14.010"), ("off", "15:11:09.744"),
                            ("on", "15:28:13.424"), ("off", "15:29:15.678")]:
            entries.append(_row(i, name, when, "journal_source_switch_" + state, state))
        entries.append(_row(i, name, "14:50:38.911",
                            "issued_setlevel", "", "4013"))
    # Not recovered from the Journal: independently source-timed native events.
    entries.extend([
        _row(7807, "Shower Light", "15:07:32.530", "reported_switch_on", "on"),
        _row(7807, "Shower Light", "15:11:45.944", "issued_off", "", "4014"),
        _row(7807, "Shower Light", "15:11:46.134", "reported_switch_off", "off"),
    ])
    entries.sort(key=lambda x: x["date"])
    return {
        "target_device_ids": ["7818", "7821", "7807"],
        "target_coverage": [
            {"device_id": "7818", "device_name": "Bathroom Light 1"},
            {"device_id": "7821", "device_name": "Bathroom Light 2"},
            {"device_id": "7807", "device_name": "Shower Light",
             "reported_switch_on": 1, "reported_switch_off": 1, "issued_off": 1},
        ],
        "incident_ledger": entries,
        "incident_ledger_total": len(entries),
        "missing_switch_history_for_targets": ["Bathroom Light 1", "Bathroom Light 2"],
        "journal_source_observations": 12,
        "journal_collector_observations": 12,
        "journal_gap_count": 8,
        "archived_app_checks": [],
    }


def test_archive_recovery_never_suppresses_live_shower_transitions():
    rendered = source_incident_digest(_facts())
    assert rendered
    assert "| 15:07:32 | Shower Light | ON |" in rendered
    assert "| 15:11:46 | Shower Light | OFF |" in rendered
    assert "15:11:45" not in rendered or "off()" in rendered
    assert "App 4014 issued an off() command" in rendered
    assert "Apps 4014 issued off() commands" not in rendered
    assert "No independent source-timestamped switch reports were returned for Shower Light" not in rendered
    assert "Direct Hubitat switch history retained:" in rendered
    assert "12 independently source-timestamped switch observations" in rendered
    assert "coverage" not in rendered.lower() or "gap" in rendered.lower()


def test_journal_reconciliation_replaces_incomplete_draft_with_union():
    answer, changed = reconcile_ledger_if_needed(
        "The Bathroom lights changed ON and OFF; Shower Light activity was absent",
        _facts(),
    )
    assert changed
    assert "Shower Light | ON" in answer
    assert "Shower Light | OFF" in answer
    assert "Bathroom Lights 1 and 2" in answer


def test_same_target_journal_and_native_switch_not_double_counted():
    facts = _facts()
    facts["incident_ledger"].append(
        _row(7818, "Bathroom Light 1", "15:28:13.424", "reported_switch_on", "on")
    )
    facts["incident_ledger_total"] += 1
    rendered = source_incident_digest(facts)
    assert rendered
    assert rendered.count("| 15:28:13 | Bathroom") == 1
    assert "2 source-timestamped switch reports" in rendered


def test_missing_source_warning_only_for_targets_without_any_source_rows():
    facts = _facts()
    # Remove native Shower ON/OFF: this is a *real* missing-source case.
    facts["incident_ledger"] = [
        row for row in facts["incident_ledger"]
        if not (row["device_id"] == "7807"
                and row["event_class"].startswith("reported_switch_"))
    ]
    rendered = source_incident_digest(facts)
    assert rendered
    assert "No independent source-timestamped switch reports were returned for Shower Light" in rendered


def test_collector_reception_never_used_as_source_timestamp():
    facts = _facts()
    facts["incident_ledger"].append({
        **_row(7807, "Shower Light", "15:10:20.001",
               "journal_received_switch_on", "on"),
        "timestamp_basis": "collector-received",
    })
    rendered = source_incident_digest(facts)
    assert rendered
    assert "| 15:10:20 | Shower Light | ON |" not in rendered

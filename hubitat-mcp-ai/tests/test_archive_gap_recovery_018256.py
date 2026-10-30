"""Regression: a recent rolling history cannot prevent archived incident recovery.

The reproduced live 0.18.255 request resolved two target IDs and received
newer 19:xx state rows, but none from the older 14:50-15:30 interval. The
archive existed; the evidence aggregator previously returned None, blocking
journal recovery. This applies to any two independently identified devices.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from group_journal_recovery import recover_group_journal, journal_incident_bounds
from investigation_evidence_cycle import cross_source_discovery_checkpoint
from unified_investigation_bridge import collect_unified_evidence, unified_investigation_followup
from unified_incident_digest import source_incident_digest

Q = ("Investigate why Zone Alpha Light and Zone Beta Light repeatedly "
     "turned ON and OFF between 14:50 and 15:30 GMT on 30 October 2026.")


def lookup(ident, label):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "targeted_device_lookup",
        "arguments": {"tool": "hub_list_devices", "args": {
            "labelFilter": label}},
        "details": {"reportedDeviceState": {
            "deviceId": str(ident), "label": label,
            "reportedAttributes": {"switch": "off"}}},
    }


def recent(ident, state="on"):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "mutates": False, "effect": "read",
        "supports_live_claim": True,
        "evidence_kind": "authoritative_device_event_history",
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": str(ident), "hoursBack": 24, "limit": 50,
            "attribute": "switch"}},
        "details": {"observedEvents": [{
            "name": "switch", "value": state, "type": "physical",
            "date": "2026-10-30T19:19:27.865+0000",
            "producedBy": {"name": "Upstream Bridge", "deviceId": "900"},
        }]},
    }


def original():
    return [lookup(101, "Zone Alpha Light"), lookup(102, "Zone Beta Light"),
            recent(101), recent(102)]


class Journal:
    enabled = True
    _started = True
    def __init__(self):
        self.calls = []
    def query(self, **kwargs):
        self.calls.append(kwargs)
        ident = kwargs["device_id"]
        return {
            "events": [
                {"stream": "events", "device_id": ident,
                 "attribute": "switch", "value": "on",
                 "timestamp_basis": "source",
                 "observed_at": "2026-10-30T15:28:13.424+00:00"},
                {"stream": "events", "device_id": ident,
                 "attribute": "switch", "value": "off",
                 "timestamp_basis": "source",
                 "observed_at": "2026-10-30T15:29:15.678+00:00"},
                {"stream": "events", "device_id": ident,
                 "attribute": "switch", "value": "on",
                 "timestamp_basis": "collector-received",
                 "observed_at": "2026-10-30T15:28:14.222+00:00"},
            ],
            "gaps": [{"reason": "connection-restart"}],
        }


class Recorder:
    def __init__(self, receipts):
        self.rows = list(receipts)
    def record(self, tool, arguments, **kwargs):
        self.rows.append({"tool": tool, "arguments": arguments, **kwargs})


def test_out_of_window_native_rows_preserve_verified_target_scope():
    facts = collect_unified_evidence(original(), Q)
    assert facts is not None
    assert facts["target_device_ids"] == ["101", "102"]
    assert facts["transition_count"] == 0
    assert facts["incident_ledger"] == []
    assert facts["incident_window_without_native_events"] is True
    assert facts["missing_switch_history_for_targets"] == [
        "Zone Alpha Light", "Zone Beta Light"]
    assert facts["native_target_source_complete_for_incident"] is False


def test_journal_recovers_when_rolling_events_are_newer():
    journal = Journal()
    recorder = Recorder(original())
    expected = journal_incident_bounds(Q, recorder.rows)
    assert expected is not None
    assert expected[0].startswith("2026-10-30T14:50")
    assert expected[1].startswith("2026-10-30T15:30")
    report = asyncio.run(recover_group_journal(
        journal=journal, recorder=recorder, question=Q,
        receipts=recorder.rows,
    ))
    assert report["attempted"] == 2
    assert report["source_observations"] == 4
    assert report["collector_observations"] == 2
    assert report["journal_gaps"] == 2
    assert {c["device_id"] for c in journal.calls} == {"101", "102"}
    facts = collect_unified_evidence(recorder.rows, Q)
    assert facts["journal_source_observations"] == 4
    assert facts["journal_collector_observations"] == 2
    assert len(facts["incident_ledger"]) == 6
    assert facts["incident_window_without_native_events"] is True
    assert cross_source_discovery_checkpoint(recorder.rows, Q)
    assert "independent input" in unified_investigation_followup(recorder.rows, Q)
    digest = source_incident_digest(facts)
    assert digest is not None
    assert "| 15:28:13 | Zone Alpha Light, Zone Beta Light | ON |" in digest
    assert "| 15:29:15 | Zone Alpha Light, Zone Beta Light | OFF |" in digest


def test_recovery_idempotent_and_collector_not_promoted_to_event():
    journal = Journal()
    recorder = Recorder(original())
    async def run_twice():
        first = await recover_group_journal(
            journal=journal, recorder=recorder, question=Q,
            receipts=recorder.rows)
        second = await recover_group_journal(
            journal=journal, recorder=recorder, question=Q,
            receipts=recorder.rows)
        return first, second
    first, second = asyncio.run(run_twice())
    assert first["attempted"] == 2
    assert second["attempted"] == 0
    assert len(journal.calls) == 2
    facts = collect_unified_evidence(recorder.rows, Q)
    assert facts["journal_source_observations"] == 4
    assert facts["journal_collector_observations"] == 2


def test_without_verified_independent_targets_no_archive_query():
    receipts = [lookup(101, "Zone Alpha Light"), recent(101)]
    journal = Journal()
    recorder = Recorder(receipts)
    report = asyncio.run(recover_group_journal(
        journal=journal, recorder=recorder, question=Q, receipts=recorder.rows))
    assert report["attempted"] == 0
    assert journal.calls == []


def test_no_unverified_date_never_queries_archive():
    journal = Journal()
    recorder = Recorder(original())
    q = "Investigate why Zone Alpha Light and Zone Beta Light changed yesterday"
    report = asyncio.run(recover_group_journal(
        journal=journal, recorder=recorder, question=q,
        receipts=recorder.rows))
    assert report["attempted"] == 0
    assert not journal.calls

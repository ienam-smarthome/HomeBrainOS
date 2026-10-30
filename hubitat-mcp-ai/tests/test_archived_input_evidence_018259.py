"""Archived sensor recovery supplements previously scoped empty native history.

Generic IDs and source times test the original agent's source-contract logic.
No fixed controller, room, device name or inferred initiating automation.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from group_journal_recovery import recover_group_journal, recover_input_journal
from investigation_evidence_cycle import cross_source_discovery_checkpoint
from unified_investigation_bridge import collect_unified_evidence
from unified_incident_digest import source_incident_digest

Q = ("Why did Zone Alpha Light and Zone Beta Light switch repeatedly "
     "between 14:50 and 15:30 GMT on 30 October 2026?")


def lookup(ident, label):
    return {"success": True, "mutates": False, "effect": "read",
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "evidence_kind": "targeted_device_lookup",
            "details": {"reportedDeviceState": {
                "deviceId": str(ident), "label": label}}}


def native(ident, events=None):
    return {"success": True, "mutates": False, "effect": "read",
            "supports_live_claim": True,
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": str(ident),
                                   "since": "2026-10-30T14:50:00Z",
                                   "until": "2026-10-30T15:30:00Z"}},
            "details": {"observedEvents": events or []}}


def original():
    return [lookup(101, "Zone Alpha Light"),
            lookup(102, "Zone Beta Light"),
            native(101), native(102), native(201), native(202)]


def event(ident, kind, value, t, basis="source"):
    return {"stream": "events", "device_id": str(ident),
            "attribute": kind, "value": value, "timestamp_basis": basis,
            "source": "test-attested",
            "observed_at": "2026-10-30T" + t + "+00:00"}


class Journal:
    enabled = True
    _started = True

    def __init__(self):
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        ident = kwargs["device_id"]
        if ident in ("101", "102"):
            return {"events": [
                event(ident, "switch", "on", "15:28:13.424"),
                event(ident, "switch", "off", "15:29:15.678")],
                "gaps": [{"reason": "disconnect"}]}
        if ident == "201":
            return {"events": [
                event(ident, "motion", "active", "15:28:13.306"),
                event(ident, "motion", "inactive", "15:29:05.430"),
                event(ident, "motion", "active", "15:28:14.500",
                      basis="collector-received"),
                event(ident, "switch", "on", "15:28:14.000"),
            ], "gaps": [{"reason": "disconnect"}], "truncated": False}
        return {"events": [], "gaps": [{"reason": "disconnect"}]}


class Recorder:
    def __init__(self, rows):
        self.rows = list(rows)

    def record(self, tool, arguments, **kw):
        self.rows.append({"tool": tool, "arguments": arguments, **kw})


async def recover_all(recorder, journal):
    switch = await recover_group_journal(
        journal=journal, recorder=recorder, question=Q, receipts=recorder.rows)
    input_ = await recover_input_journal(
        journal=journal, recorder=recorder, question=Q, receipts=recorder.rows)
    return switch, input_


def test_empty_native_sensor_history_recovers_source_timed_journal_events():
    recorder = Recorder(original())
    journal = Journal()
    sw, inp = asyncio.run(recover_all(recorder, journal))
    assert sw["attempted"] == 2
    assert inp["attempted"] == 2
    assert inp["source_observations"] == 2
    assert inp["collector_observations"] == 1
    assert inp["journal_gaps"] == 2
    assert {call["device_id"] for call in journal.calls} == {
        "101", "102", "201", "202"}
    assert all("since" in call and "until" in call
               for call in journal.calls)
    facts = collect_unified_evidence(recorder.rows, Q)
    assert facts["journal_source_observations"] == 4
    assert facts["archived_input_source_observations"] == 2
    assert facts["archived_input_collector_observations"] == 1
    assert facts["archived_input_gap_count"] == 2
    assert "201" in facts["independently_read_input_ids"]
    assert len(facts["independent_input_observations"]) == 2
    assert facts["independent_input_observations"][0]["time"].startswith(
        "2026-10-30T15:28:13.306")
    assert facts["independent_input_observations"][0][
        "app_relationship_basis"] == "unavailable-in-journal"
    assert facts["input_app_relationships"][0]["relationship"] == (
        "relationship-not-established-from-records")
    assert facts["additional_event_reads_without_usable_rows"] == ["202"]
    prompt = cross_source_discovery_checkpoint(recorder.rows, Q)
    assert prompt and '"archivedInputSourceReports":2' in prompt
    assert "15:28:13.306" in prompt
    digest = source_incident_digest(facts)
    assert "**Independent sensor histories examined:**" in digest
    assert "device 201: 15:28:13 active, 15:29:05 inactive" in digest
    assert "**Archived input history coverage:** 2 source-timestamped" in digest
    assert "1 reception-only observation(s)" in digest
    assert "device 201: 1 gap interval(s) reported" in digest
    assert "device 202: 1 gap interval(s) reported" in digest
    assert "cannot be summed as distinct collector outages" in digest
    assert "device 202" in digest
    assert "not proof that any of these sensors commanded" in digest


def test_archive_recovery_idempotent_even_when_journal_is_empty():
    recorder = Recorder(original())
    journal = Journal()
    asyncio.run(recover_all(recorder, journal))
    attempts = len(journal.calls)
    again = asyncio.run(recover_all(recorder, journal))
    assert again[0]["attempted"] == 0
    assert again[1]["attempted"] == 0
    assert len(journal.calls) == attempts


def test_out_of_scope_archived_input_receipt_cannot_invent_sensor():
    recorder = Recorder(original()[:4])
    journal = Journal()
    recorder.record(
        "homebrain_evidence_journal",
        {"device_id": "201", "since": "2026-10-30T14:50:00+00:00",
         "until": "2026-10-30T15:30:00+00:00"},
        success=True, mutates=False, effect="read",
        evidence_kind="group_archived_input_history",
        details={"deviceId": "201", "observations": [{
            "device_id": "201", "attribute": "motion",
            "value": "active", "date": "2026-10-30T15:28:13.306+00:00",
            "timestamp_basis": "source"}]},
    )
    facts = collect_unified_evidence(recorder.rows, Q)
    assert facts["independent_input_observations"] == []
    report = asyncio.run(recover_input_journal(
        journal=journal, recorder=recorder,
        question=Q, receipts=recorder.rows))
    assert report["attempted"] == 0
    assert journal.calls == []


def test_malformed_journal_timestamp_is_not_promoted_to_source_event():
    r = Recorder(original())
    j = Journal()
    async def run():
        await recover_group_journal(
            journal=j, recorder=r, question=Q, receipts=r.rows)
        # Replace the candidate response with a forged naive date.
        saved = j.query
        def corrupt(**kwargs):
            if kwargs["device_id"] == "201":
                return {"events": [{
                    "stream": "events", "device_id": "201",
                    "attribute": "motion", "value": "active",
                    "timestamp_basis": "source",
                    "observed_at": "2026-10-30T15:28:13"}], "gaps": []}
            return saved(**kwargs)
        j.query = corrupt
        return await recover_input_journal(
            journal=j, recorder=r, question=Q, receipts=r.rows)
    result = asyncio.run(run())
    assert result["source_observations"] == 0
    assert result["collector_observations"] == 0
    assert not collect_unified_evidence(r.rows, Q)[
        "independent_input_observations"]


def test_collector_only_cannot_prove_original_input_event_clock():
    r = Recorder(original())
    r.record(
        "homebrain_evidence_journal",
        {"device_id": "201"}, success=True, effect="read", mutates=False,
        evidence_kind="group_archived_input_history",
        details={"deviceId": "201", "observations": [{
            "device_id": "201", "attribute": "motion", "value": "active",
            "date": "2026-10-30T15:28:15+00:00",
            "timestamp_basis": "collector-received"}]},
    )
    facts = collect_unified_evidence(r.rows, Q)
    assert facts["archived_input_collector_observations"] == 1
    assert facts["archived_input_source_observations"] == 0
    assert facts["independent_input_observations"] == []
    assert "201" in facts["additional_event_reads_without_usable_rows"]

"""Durable HomeBrain journal replay for an evicted, explicitly dated ON.

All tests use private temporary SQLite storage. No Hubitat socket, command,
rule modification or internet-control action is ever issued.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from historical_evidence_journal import HistoricalEvidenceJournal
from skill_focal_window import build_focal_source_plan, project_archived_focal_state
from causal_evidence_graph import build_causal_evidence_graph
from skill_grounded_answer import render_grounded_causal_answer
from test_skill_missing_focal_0_17_76 import _evicted, QUESTION


def journal(tmp_path):
    instance = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "evidence.sqlite3",
    )
    instance._initialize()
    instance._started = True
    return instance


def receipt(plan, projected):
    return {
        "tool": "homebrain_evidence_journal",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "focal_archived_state_history",
        "arguments": {
            "device_id": plan["deviceId"],
            "since": plan["sourceWindow"]["since"],
            "until": plan["sourceWindow"]["until"],
        },
        "details": projected,
    }


def test_journal_recovers_evicted_off_on_without_inventing_cause(tmp_path):
    archive = journal(tmp_path)
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    assert plan and plan["requestedMinuteOnly"]
    snapshots = [
        {
            "deviceId": "7805", "name": "switch", "value": state,
            "displayName": "Livingroom Light 1", "source": "DEVICE",
            "date": timestamp,
        }
        for state, timestamp in (
            ("off", "2026-10-14T19:54:57.946+01:00"),
            ("on", "2026-10-14T19:55:00.049+01:00"),
        )
    ]
    records = [
        archive._row("events", snap, "2026-10-14T19:55:01+01:00", frozenset())
        for snap in snapshots
    ]
    assert archive._write_batch(records) == 2
    result = archive.query(**{
        "since": plan["sourceWindow"]["since"],
        "until": plan["sourceWindow"]["until"],
        "device_id": plan["deviceId"], "attribute": "switch",
    })
    projection = project_archived_focal_state(result, plan)
    assert projection["sourceVerifiedOn"] is True
    assert projection["sourceTimestampedCount"] == 2
    assert [x["value"] for x in projection["events"]] == ["off", "on"]
    graph = build_causal_evidence_graph(rows + [receipt(plan, projection)], QUESTION)
    assert graph["scope"] == "single-observed-event"
    assert graph["focus"]["on"] and graph["focus"]["on"].startswith("2026-10-14T18:55:00.049")
    assert projection["archiveHistoricalCoverageComplete"] is False
    answer = render_grounded_causal_answer(rows + [receipt(plan, projection)], QUESTION)
    assert answer is not None
    assert "SenseCap D1 Settings" in answer
    assert "not a confirmed cause" in answer.lower()
    assert "persistent HomeBrain journal" in answer


def test_collector_receive_time_does_not_become_verified_source_event(tmp_path):
    archive = journal(tmp_path)
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    collected = archive._row(
        "events",
        {"deviceId": "7805", "name": "switch", "value": "on"},
        "2026-10-14T18:55:00.049+00:00", frozenset(),
    )
    assert collected["timestamp_basis"] == "collector-received"
    archive._write_batch([collected])
    result = archive.query(
        since=plan["sourceWindow"]["since"],
        until=plan["sourceWindow"]["until"],
        device_id=plan["deviceId"], attribute="switch",
    )
    projected = project_archived_focal_state(result, plan)
    assert projected["sourceVerifiedOn"] is False
    assert projected["collectorReceivedOnlyCount"] == 1
    assert projected["events"] == []
    assert build_causal_evidence_graph(rows + [receipt(plan, projected)], QUESTION)["scope"] == "ambiguous-or-unobserved-event"


@pytest.mark.asyncio
async def test_native_command_producer_survives_restart_and_deduplicates(tmp_path):
    archive = journal(tmp_path)
    packet = {
        "events": [{
            "name": "command-on",
            "description": "Command called: on()",
            "date": "2026-10-14T19:54:46.691+01:00",
            "producedBy": {"id": "4129", "type": "app",
                           "label": "SenseCap D1 Settings"},
        }, {
            "name": "switch", "value": "on",
            "date": "2026-10-14T19:55:00.049+01:00",
            "producedBy": {"type": "device", "id": "7790",
                           "label": "Matter Hue Bridge Pro"},
        }, {
            "name": "command-on",
            "date": "2026-10-14T19:55:01+01:00",
            "producedBy": {"type": "app", "id": "not-a-number"},
        }],
    }
    assert await archive.ingest_native_history("7805", packet) == 2
    queued = [archive._queue.get_nowait() for _ in range(2)]
    assert archive._write_batch(queued) == 2
    assert await archive.ingest_native_history("7805", packet) == 2
    duplicate = [archive._queue.get_nowait() for _ in range(2)]
    assert archive._write_batch(duplicate) == 0
    reopened = journal(tmp_path)
    found = reopened.query(
        since="2026-10-14T18:54:00Z",
        until="2026-10-14T18:56:00Z",
        device_id="7805", limit=20,
    )
    assert found["count"] == 2
    command = next(x for x in found["events"] if x["attribute"] == "command-on")
    assert command["source"] == "hubitat-mcp-command:app:4129"
    assert command["display_name"] == "SenseCap D1 Settings"
    assert command["timestamp_basis"] == "source"
    assert all("description" not in x for x in found["events"])


def test_native_and_archive_same_instant_do_not_become_ambiguous(tmp_path):
    archive = journal(tmp_path)
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    packet = {
        "deviceId": "7805", "name": "switch", "value": "on",
        "date": "2026-10-14T19:55:00.049+01:00",
    }
    state = archive._row("events", packet, "2026-10-14T18:55:01Z", frozenset())
    archive._write_batch([state])
    selected = project_archived_focal_state(archive.query(
        since=plan["sourceWindow"]["since"],
        until=plan["sourceWindow"]["until"], device_id="7805",
        attribute="switch",
    ), plan)
    native = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "evidence_kind": "focal_exact_state_history",
        "arguments": {"tool": "hub_list_device_events", "args": plan["stateRead"]},
        "details": {
            "label": "Livingroom Light 1",
            "requestedOn": plan["requestedOn"],
            "requestedMinuteOnly": True,
            "events": [{"name": "switch", "value": "on",
                        "date": "2026-10-14T19:55:00.049+01:00"}],
        },
    }
    graph = build_causal_evidence_graph(rows + [native, receipt(plan, selected)], QUESTION)
    assert graph["scope"] == "single-observed-event"

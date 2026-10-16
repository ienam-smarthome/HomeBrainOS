"""0.17.83: real-world reception-only journal timeline must reach answer.

A persisted collector timestamp is useful historical context, not proof of
Hubitat's source event time or physical command delivery.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))

from causal_evidence_graph import build_causal_evidence_graph
from skill_focal_window import (
    build_focal_source_plan, project_archived_focal_state,
    render_unverified_focal_outcome,
)
from test_journal_focal_replay_0_17_79 import journal, receipt
from test_skill_missing_focal_0_17_76 import _evicted, QUESTION


def test_incident_retains_received_off_on_off_on_without_inventing_physical_on(tmp_path):
    archive = journal(tmp_path)
    evidence = _evicted()
    plan = build_focal_source_plan(evidence, QUESTION)
    assert plan is not None
    rows = []
    for value, stamp in [
        ("off", "2026-10-14T18:54:38+00:00"),
        ("on", "2026-10-14T18:54:47+00:00"),
        ("off", "2026-10-14T18:54:59+00:00"),
        ("on", "2026-10-14T18:55:01+00:00"),
    ]:
        row = archive._row(
            "events", {"deviceId": "7805", "name": "switch", "value": value},
            stamp, frozenset(),
        )
        assert row is not None
        rows.append(row)
    assert archive._write_batch(rows) == 4
    stored = archive.query(
        since=plan["sourceWindow"]["since"],
        until=plan["sourceWindow"]["until"],
        device_id="7805", attribute="switch",
    )
    projected = project_archived_focal_state(stored, plan)
    assert projected["sourceTimestampedCount"] == 0
    assert projected["collectorReceivedOnlyCount"] == 4
    assert projected["events"] == []
    assert projected["sourceVerifiedOn"] is False
    assert [x["value"] for x in projected["receptionOnlyTransitions"]] == [
        "off", "on", "off", "on",
    ]
    evidence.append(receipt(plan, projected))
    evidence.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "evidence_kind": "focal_exact_state_history",
        "arguments": {"tool": "hub_list_device_events", "args": plan["stateRead"]},
        "details": {"label": "Livingroom Light 1", "deviceId": "7805",
                    "events": [], "requestedOn": plan["requestedOn"]},
    })
    assert build_causal_evidence_graph(evidence, QUESTION)["scope"] != "single-observed-event"
    answer = render_unverified_focal_outcome(plan, evidence, QUESTION)
    assert answer
    assert "SenseCap D1 Settings" in answer
    assert "19:54:38" in answer and "19:54:47" in answer
    assert "19:54:59" in answer and "19:55:01" in answer
    assert "ON/OFF/ON sequence needs explanation" in answer
    assert "not verified" in answer.lower()
    assert "received reports, not verified" in answer


def test_zero_reception_rows_does_not_invent_timeline(tmp_path):
    archive = journal(tmp_path)
    plan = build_focal_source_plan(_evicted(), QUESTION)
    stored = archive.query(
        since=plan["sourceWindow"]["since"], until=plan["sourceWindow"]["until"],
        device_id="7805", attribute="switch",
    )
    projected = project_archived_focal_state(stored, plan)
    assert projected["receptionOnlyTransitions"] == []
    assert not projected["sourceVerifiedOn"]


def test_bounded_collector_projection_preserves_truncation(tmp_path):
    archive = journal(tmp_path)
    plan = build_focal_source_plan(_evicted(), QUESTION)
    rows = []
    for n in range(16):
        stamp = f"2026-10-14T18:54:{n + 40:02d}+00:00"
        row = archive._row(
            "events", {"deviceId": "7805", "name": "switch",
                       "value": "on" if n % 2 else "off"}, stamp, frozenset()
        )
        rows.append(row)
    assert archive._write_batch(rows) == 16
    stored = archive.query(
        since=plan["sourceWindow"]["since"], until=plan["sourceWindow"]["until"],
        device_id="7805", attribute="switch", limit=10,
    )
    projected = project_archived_focal_state(stored, plan)
    assert projected["journalQueryTruncated"] is True
    assert projected["collectorReceivedOnlyCount"] == 10
    assert len(projected["receptionOnlyTransitions"]) == 10
    assert projected["sourceVerifiedOn"] is False

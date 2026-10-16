"""Live 0.17.79 regression: event clock and search-range clocks are distinct.

A request for a 14 October incident with an extra 19:50–20:00 archival range
must read the persistent Evidence Journal for 14 October, not silently map it
to 15 October's 'most recent' clock window and exit.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))

from causal_timeline import _focal_clock_parts, has_explicit_focal_clock
from skill_focal_window import build_focal_source_plan
from homebrain_agent import UnifiedMCPAgent
from test_early_missing_focal_0_17_78 import HistoricalMCP, NeverCallAI
from test_skill_missing_focal_0_17_76 import _evicted
from test_journal_focal_replay_0_17_79 import journal


INCIDENT = (
    "Investigate why Livingroom Light 1 turned ON at 19:55 on 14 October 2026. "
    "Check the persistent Historical Evidence Journal for device 7805 between "
    "19:50 and 20:00 BST, including ON/OFF events and collection gaps. "
    "Compare archived events against Hubitat's current history, distinguish "
    "source timestamps from collector timestamps, and identify any recorded "
    "command producer. Read-only."
)


def test_event_time_is_not_replaced_by_archive_window_or_latest_day():
    assert _focal_clock_parts(INCIDENT) == (19, 55)
    assert has_explicit_focal_clock(INCIDENT)
    plan = build_focal_source_plan(_evicted(), INCIDENT)
    assert plan is not None
    assert plan["deviceId"] == "7805"
    assert plan["producerAppId"] == "4129"
    assert plan["requestedOn"].startswith("2026-10-14T19:55:00")
    assert plan["stateRead"]["since"] == "2026-10-14T18:54:36.691Z"
    assert plan["stateRead"]["until"] == "2026-10-14T18:56:00.000Z"
    assert plan["journalWindow"] == {
        "since": "2026-10-14T18:50:00.000Z",
        "until": "2026-10-14T19:00:00.000Z",
    }


def test_multiple_competing_focal_events_still_require_disambiguation():
    statement = (
        "Why did Livingroom Light 1 turn ON at 19:55 and turn OFF at "
        "19:59 on 14 October 2026?"
    )
    assert _focal_clock_parts(statement) is None
    assert build_focal_source_plan(_evicted(), statement) is None


def test_source_second_precision_preserved_with_other_range_clocks():
    question = (
        "Why did Livingroom Light 1 switch ON at 19:55:00 on "
        "14 October 2026? Search archive between 19:50 and 20:00."
    )
    assert _focal_clock_parts(question) == (19, 55, 0)


@pytest.mark.asyncio
async def test_real_prompt_checks_journal_before_empty_subject_early_stop(
    tmp_path, monkeypatch,
):
    mcp = HistoricalMCP()
    model = NeverCallAI()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=model)
    checked_at_model = []

    async def model_response(messages, schemas):
        checked_at_model.append([(name, args["tool"]) for name, args in mcp.calls])
        return {"content": (
            "SenseCap D1 Settings is a recorded command source; "
            "the historical physical activation remains unverified. "
            "The persistent journal has 1 collector-reception-only row(s), "
            "not source-timestamped switch rows."), "tool_calls": []}

    monkeypatch.setattr(agent.transport, "chat", model_response)
    archive = journal(tmp_path)
    agent.historical_journal = archive

    # Reproduce the original: the journal collected an ON with only a
    # collector-received timestamp, not a verified source-origin timestamp.
    received = archive._row(
        "events",
        {"deviceId": "7805", "name": "switch", "value": "on"},
        "2026-10-14T18:55:00.049+00:00", frozenset(),
    )
    archive._write_batch([received])
    assert received["timestamp_basis"] == "collector-received"

    async def prefetch(self, *_args, **_kwargs):
        for row in _evicted():
            args = row.get("arguments") or {}
            if row.get("sub_tool") and "tool" not in args:
                args = {
                    "tool": row["sub_tool"],
                    "args": args.get("args") or args,
                }
            self.evidence.record(
                row["tool"], args,
                success=True, elapsed_ms=0,
                summary=str(row.get("summary") or "verified"),
                supports_live_claim=True,
                evidence_kind=str(row.get("evidence_kind") or "tool_result"),
                mutates=False, effect="read",
                details=row.get("details"),
            )
        return "empty", "livingroomlight1", "on"

    monkeypatch.setattr(
        UnifiedMCPAgent, "_prefetch_explicit_causal_subject", prefetch,
    )
    result = await agent.process_user_request_result(INCIDENT)
    counts = result.metrics["counters"]
    assert counts["skills_focal_journal_read"] == 1
    assert counts["skills_focal_state_window"] == 1
    assert counts["skills_focal_producer_logs"] == 1
    assert counts["investigation_read_reflection"] == 1
    assert checked_at_model
    assert checked_at_model[0] == [
        ("hub_read_devices", "hub_list_device_events"),
        ("hub_read_diagnostics", "hub_get_logs"),
    ]
    assert "SenseCap D1 Settings" in result.message
    assert "Historical verification boundary" in result.message
    assert "1 collector-reception-only row(s)" in result.message
    assert "source-timestamped switch row(s)" in result.message
    assert "14 October" in result.message
    assert "15 October 2026 at 19:55" not in result.message
    journal_receipt = next(
        row for row in result.evidence
        if row.get("evidence_kind") == "focal_archived_state_history"
    )
    assert journal_receipt["arguments"]["since"] == "2026-10-14T18:50:00.000Z"
    assert journal_receipt["arguments"]["until"] == "2026-10-14T19:00:00.000Z"
    assert [
        (name, args["tool"]) for name, args in mcp.calls
    ] == [
        ("hub_read_devices", "hub_list_device_events"),
        ("hub_read_diagnostics", "hub_get_logs"),
    ]

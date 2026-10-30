"""v0.18.244: generic Historical Journal recovery through the ORIGINAL agent.

Tests exact 30 Oct local+UTC window, provenance grades, missing Hubitat
switch events, normal read-only question boundary, and ingress-aware UI.
No dependency on the retired V2 test interface.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from group_journal_recovery import journal_incident_bounds, recover_group_journal
from unified_investigation_bridge import collect_unified_evidence
from unified_incident_synthesis import verified_incident_ledger
from mcp_agent_orchestrator import UnifiedMCPAgent
from test_unified_incident_causal_consistency_0_18_243 import (
    QUESTION, actual_partial_receipts, WRONG_LIVE,
)

EXPLICIT = QUESTION.replace("between 02:00 and 07:30", "between 02:00 and 07:30 GMT")


class Journal:
    enabled = True
    _started = True
    def __init__(self, entries=None, gap_count=0):
        self.entries = entries or {}
        self.gap_count = gap_count
        self.calls = []
    def query(self, **kwargs):
        self.calls.append(kwargs)
        device_id = kwargs["device_id"]
        return {
            "events": self.entries.get(device_id, []),
            "gaps": [{"reason": "socket-disconnected"}] * self.gap_count,
            "has_more": False, "truncated": False,
        }


class Recorder:
    def __init__(self):
        self.entries = []
    def record(self, tool, arguments, **kw):
        self.entries.append({
            "tool": tool, "arguments": arguments, "sub_tool": None, **kw,
        })
    def receipts(self):
        return list(self.entries)


def archived(device_id, value, when, basis="source"):
    return {"stream": "events", "device_id": str(device_id),
            "attribute": "switch", "value": value, "source": "DEVICE",
            "observed_at": when, "timestamp_basis": basis}


@pytest.mark.asyncio
async def test_group_automatic_journal_read_source_provenance_and_gaps():
    entries = {
        "7818": [
            archived("7818", "on", "2026-10-30T03:40:21.668+00:00"),
            archived("7818", "off", "2026-10-30T03:46:05.928+00:00"),
            archived("7818", "off", "2026-10-30T11:34:00+00:00"),
        ],
        "7821": [
            archived("7821", "on", "2026-10-30T03:40:22.678+00:00",
                     "collector-received"),
            archived("7821", "off", "2026-10-30T03:46:06.059+00:00",
                     "collector-received"),
        ],
    }
    journal = Journal(entries, gap_count=1)
    recorder = Recorder()
    base = actual_partial_receipts()
    outcome = await recover_group_journal(
        journal=journal, recorder=recorder, question=EXPLICIT, receipts=base)
    assert outcome["status"] == "checked"
    assert outcome["attempted"] == 2
    assert outcome["source_observations"] == 3
    assert outcome["collector_observations"] == 2
    assert outcome["journal_gaps"] == 2
    assert {c["device_id"] for c in journal.calls} == {"7818","7821"}
    assert all(c["attribute"] == "switch" for c in journal.calls)
    assert all(c["since"].startswith("2026-10-30T02:00") for c in journal.calls)
    assert all(c["until"].startswith("2026-10-30T07:30") for c in journal.calls)
    assert all(item["mutates"] is False and item["effect"] == "read"
               for item in recorder.entries)
    merged = collect_unified_evidence(base + recorder.receipts(), EXPLICIT)
    assert merged["journal_source_observations"] == 2  # out-of-window row discarded
    assert merged["journal_collector_observations"] == 2
    assert merged["journal_read_count"] == 2
    assert merged["journal_gap_count"] == 2
    rows = merged["incident_ledger"]
    assert any(e["event_class"] == "journal_source_switch_on"
               and e["device_id"] == "7818" for e in rows)
    assert any(e["event_class"] == "journal_received_switch_on"
               and e["device_id"] == "7821" for e in rows)
    assert all(e["date"] != "2026-10-30T11:34:00+00:00" for e in rows)
    timeline = verified_incident_ledger(merged)
    assert "Journal source-timed switch" in timeline
    assert "Journal collector-received switch" in timeline
    assert "collector-reception timestamps do not establish exact physical" in timeline
    assert "App 1568" in timeline
    assert "No OFF commands" not in timeline


@pytest.mark.asyncio
async def test_empty_journal_does_not_prove_no_activity_or_completeness():
    journal, recorder = Journal(gap_count=2), Recorder()
    outcome = await recover_group_journal(
        journal=journal, recorder=recorder,
        receipts=actual_partial_receipts(), question=EXPLICIT)
    assert outcome["attempted"] == 2
    assert outcome["source_observations"] == 0
    assert outcome["journal_gaps"] == 4
    assert all(r["details"]["coverageComplete"] is False
               and r["details"]["emptyProvesNoActivity"] is False
               for r in recorder.entries)
    facts = collect_unified_evidence(
        actual_partial_receipts() + recorder.receipts(), EXPLICIT)
    assert facts["missing_switch_history_for_targets"] == [
        "Bathroom Light 1", "Bathroom Light 2"]
    assert facts["journal_source_observations"] == 0


@pytest.mark.asyncio
async def test_missing_timezone_or_unverified_target_never_queries_journal():
    q = QUESTION  # no explicit GMT, hub timezone not independently verified
    assert journal_incident_bounds(q, actual_partial_receipts()) is None
    journal, recorder = Journal(), Recorder()
    result = await recover_group_journal(
        journal=journal, recorder=recorder,
        receipts=actual_partial_receipts(), question=q)
    assert result["status"] == "incident-timezone-or-date-unverified"
    assert journal.calls == []
    unverified = [r for r in actual_partial_receipts()
                  if r["sub_tool"] != "hub_list_devices"]
    result = await recover_group_journal(
        journal=journal, recorder=recorder,
        receipts=unverified, question=EXPLICIT)
    assert result["attempted"] == 0 and journal.calls == []


@pytest.mark.asyncio
async def test_no_duplicate_reads_on_same_request():
    base = actual_partial_receipts()
    journal, recorder = Journal(), Recorder()
    await recover_group_journal(
        journal=journal, recorder=recorder, question=EXPLICIT, receipts=base)
    await recover_group_journal(
        journal=journal, recorder=recorder, question=EXPLICIT,
        receipts=base + recorder.receipts())
    assert len(journal.calls) == 2


@pytest.mark.asyncio
async def test_original_ask_terminal_boundary_uses_journal_read_only(monkeypatch):
    class FakeMCP:
        async def list_tools(self): return []
        async def get_device_identities(self): return []
    class NoProvider:
        async def post(self,*args,**kw):
            raise AssertionError("Should not send extra model request")
        async def aclose(self): return None

    agent = UnifiedMCPAgent(FakeMCP(), "key", "fake",
                            ai_client=NoProvider(),
                            require_sensitive_confirmation=False)
    journal = Journal({"7818": [
        archived("7818", "on", "2026-10-30T03:40:21+00:00"),
    ]})
    agent.historical_journal = journal
    async def model_answer(*args,**kw):
        for row in actual_partial_receipts():
            agent.evidence.record(
                row["tool"], row["arguments"], success=True,
                effect="read", mutates=False, elapsed_ms=0,
                summary="source event", supports_live_claim=True,
                details=row["details"])
        return WRONG_LIVE
    monkeypatch.setattr(agent, "_process_user_request", model_answer)
    result = await agent.process_user_request_result(EXPLICIT)
    assert result.confirmation_required is False
    assert len(journal.calls) == 2
    assert "Historical Journal fallback checked" in result.message
    assert "Journal source-timed switch" in result.message
    assert "No OFF commands" not in result.message
    assert "App 1568" in result.message
    assert not any(r.get("mutates") is True for r in result.evidence)


def test_journal_browser_copies_actual_host_url_and_accepts_time_window():
    from webui import render_page
    page = render_page("HomeBrain", "0.18.244")
    for marker in (
        'id="journalBrowseStart"', 'id="journalBrowseEnd"',
        'id="journalBrowseCopy"', "function journalBrowseParameters()",
        "new URL(apiPath('api/evidence-journal/events?'+params.toString()),location.href)",
        'id="journalBrowseDevice"',
    ):
        assert marker in page
    assert "const begin=new Date(day+'T'+from+':00');" in page
    assert "end.setMinutes(end.getMinutes()+1)" in page

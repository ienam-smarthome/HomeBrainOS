"""v0.18.247: empty two-hour histories must not hide near-boundary cycles.

Replays the real three-light investigation shape: exact independently
resolved light IDs, successful zero-row Hubitat event histories and a
bounded Historical Journal containing recent source state changes outside
the strict two-hour window. No live Hubitat device is accessed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from recent_edge_context import recover_recent_edge, render_recent_edge
from mcp_agent_orchestrator import UnifiedMCPAgent
from test_unified_homebrain_investigation_0_18_241 import IDS, lookup, read_device

QUESTION = ("Investigate why Bathroom Light 1, Bathroom Light 2 and Shower Light "
            "turned ON and OFF during the last two hours. "
            "Check sensors, commands and automation logs. Do not change anything.")


class Journal:
    enabled = True
    _started = True
    def __init__(self, data=None, gaps=2):
        self.data = data or {}
        self.calls = []
        self.gaps = gaps
    def query(self, **args):
        self.calls.append(args)
        return {"events": self.data.get(args["device_id"], []),
                "gaps": [{"reason": "socket-disconnected"}] * self.gaps,
                "has_more": False, "truncated": False}


class Recorder:
    def __init__(self):
        self.items = []
    def record(self, tool, arguments, **kwargs):
        self.items.append({"tool": tool, "arguments": arguments, **kwargs})
    def receipts(self):
        return list(self.items)


def empty_native():
    return ([lookup(ident, label) for ident, label in IDS]
            + [read_device(ident, []) for ident, label in IDS])


def observation(device_id, state, when, basis="source"):
    return {"stream": "events", "device_id": device_id,
            "attribute": "switch", "value": state,
            "observed_at": when.isoformat(), "timestamp_basis": basis}


def near_boundary():
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=2)
    def at(minutes, seconds=0):
        return start - timedelta(minutes=minutes, seconds=seconds)
    # Claude's preceding activity: 12:10 / 12:12 / 12:18 relative to
    # a 12:19 strict start. Keep precise per-light independent timestamps.
    return {
        "7818": [
            observation("7818", "on", at(9)),
            observation("7818", "off", at(8)),
            observation("7818", "on", at(7)),
            observation("7818", "off", at(1)),
            observation("7818", "off", at(1)-timedelta(seconds=-1.3),
                        "collector-received"),
        ],
        "7821": [
            observation("7821", "on", at(9)-timedelta(seconds=-0.08)),
            observation("7821", "off", at(8)-timedelta(seconds=-0.1)),
            observation("7821", "on", at(7)-timedelta(seconds=-0.17)),
            observation("7821", "off", at(1)-timedelta(seconds=-1)),
        ],
        "7807": [
            observation("7807", "on", at(6)),
            observation("7807", "off", at(5)),
            observation("7807", "on", at(4)),
            observation("7807", "off", at(1, 30)),
        ],
    }


@pytest.mark.asyncio
async def test_strict_no_switch_activity_but_nearby_journal_cycle_is_disclosed():
    recorder, journal = Recorder(), Journal(near_boundary())
    answer = await recover_recent_edge(journal=journal, recorder=recorder,
                                       receipts=empty_native(), question=QUESTION)
    assert answer["status"] == "checked"
    assert answer["attempted"] == 3
    assert answer["edge_events"] >= 12
    assert answer["in_window_events"] == 0
    assert set(x["device_id"] for x in journal.calls) == {"7818", "7821", "7807"}
    assert all(x["attribute"] == "switch" and x["limit"] == 100 for x in journal.calls)
    assert all(x["mutates"] is False and x["effect"] == "read"
               for x in recorder.receipts())
    text = render_recent_edge(empty_native() + recorder.receipts(), QUESTION)
    assert text
    assert "found no independently source-timestamped switches within" in text
    assert "**Immediately before the window:**" in text
    assert "Bathroom Light 1" in text and "Bathroom Light 2" in text
    assert "Shower Light" in text
    assert "Before requested window" in text
    assert "sensor or automation execution records" in text
    assert "Journal connection gaps" in text


@pytest.mark.asyncio
async def test_journal_finds_in_window_changes_and_prevents_wrong_no_activity_claim():
    events = near_boundary()
    now = datetime.now(timezone.utc)
    events["7818"].append(observation("7818", "on", now - timedelta(minutes=30)))
    recorder = Recorder()
    report = await recover_recent_edge(journal=Journal(events), recorder=recorder,
                                       receipts=empty_native(), question=QUESTION)
    assert report["in_window_events"] >= 1
    text = render_recent_edge(empty_native()+recorder.receipts(), QUESTION)
    assert "blanket claim of no activity is not supported" in text
    assert "Inside requested window" in text


@pytest.mark.asyncio
async def test_unverified_identity_or_unchecked_native_history_never_queries():
    native = empty_native()
    journal = Journal(near_boundary())
    missing = native[1:]
    out = await recover_recent_edge(journal=journal, recorder=Recorder(),
                                    receipts=missing, question=QUESTION)
    assert out["attempted"] == 0 and journal.calls == []
    missing = native[:5]  # one light lacks any historical read
    out = await recover_recent_edge(journal=journal, recorder=Recorder(),
                                    receipts=missing, question=QUESTION)
    assert out["attempted"] == 0 and journal.calls == []


@pytest.mark.asyncio
async def test_real_in_window_native_switch_prevents_adjoining_window_override():
    native = empty_native()
    native[-1]["details"]["observedEvents"] = [
        {"name": "switch", "value": "on",
         "date": (datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()}
    ]
    j=Journal(near_boundary())
    out=await recover_recent_edge(journal=j, recorder=Recorder(),
                                  receipts=native, question=QUESTION)
    assert out["attempted"] == 0 and j.calls == []


@pytest.mark.asyncio
async def test_duplicate_source_and_collector_reception_is_not_double_counted():
    recorder = Recorder()
    await recover_recent_edge(journal=Journal(near_boundary()), recorder=recorder,
                              receipts=empty_native(), question=QUESTION)
    text = render_recent_edge(empty_native()+recorder.receipts(), QUESTION)
    assert text
    assert text.count("Bathroom Light 1") >= 1
    assert "1 additional collector-received observation" not in text
    assert "source" in text.lower()


@pytest.mark.asyncio
async def test_original_agent_final_boundary_context_is_read_only(monkeypatch):
    class MCP:
        async def list_tools(self): return []
        async def get_device_identities(self): return []
    class Model:
        async def post(self,*a,**kw):
            raise AssertionError("Terminal history integrity requires no model calls")
        async def aclose(self): return None
    agent=UnifiedMCPAgent(MCP(), "key", "model",
                          ai_client=Model(), require_sensitive_confirmation=False)
    agent.historical_journal=Journal(near_boundary())
    async def erroneous_empty(*args,**kwargs):
        for entry in empty_native():
            agent.evidence.record(
                entry["tool"], entry["arguments"], success=True,
                effect="read", mutates=False, elapsed_ms=0,
                summary="device history with no switch state changes",
                supports_live_claim=True,
                details=entry["details"],
            )
        return "No ON/OFF activity happened in the last two hours, so all lights were inactive."
    monkeypatch.setattr(agent, "_process_user_request", erroneous_empty)
    outcome = await agent.process_user_request_result(QUESTION)
    assert "Immediately before the window" in outcome.message
    assert "Bathroom Light 1" in outcome.message
    assert "Shower Light" in outcome.message
    assert "not activity inside" in outcome.message
    assert not any(x.get("mutates") for x in outcome.evidence)
    assert outcome.confirmation_required is False

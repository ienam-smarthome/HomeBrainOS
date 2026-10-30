"""0.17.50: app-log archive is a distinct, opt-in decision source.

All tests use in-memory fakes or a temporary SQLite journal. No Hubitat
device, automation, logs setting, or installed add-on is modified.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from archived_app_decision_evidence import archived_app_decision_evidence
from historical_evidence_journal import HistoricalEvidenceJournal
from focal_history_report import render_bounded_focal_reconstruction
from motion_lockout_investigation import prefetch_motion_lockout


START = "2026-10-13T20:00:00+00:00"
END = "2026-10-13T20:03:35+00:00"
PROMPT = (
    "Independently reconstruct Livingroom Light 1's OFF at approximately "
    "21:00:20 BST on 13 October 2026. Correlate device 746's native "
    "physical button press, app 1251's OFF command, device 7805's state, "
    "motion, and app 4019's lockout decision. Read-only."
)


class FakeJournal:
    enabled = True
    _started = True
    capture_logs = True
    log_app_ids = frozenset({"4019"})
    _connected = {"logs": True, "events": True}

    def __init__(self, rows=None, gaps=None):
        self.rows = rows or []
        self.gaps = gaps or []
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("app_id"):
            return {"events": self.rows, "count": len(self.rows),
                    "gaps": self.gaps}
        return {"events": [], "count": 0, "gaps": []}


def _log(*, message="motion lockout enabled for 300 minutes",
         app_id="4019", when="2026-10-13T20:00:30+00:00",
         stream="logs"):
    return {
        "stream": stream, "app_id": app_id, "device_id": "",
        "message": message, "attribute": "debug",
        "observed_at": when, "received_at": when,
        "timestamp_basis": "collector-received",
    }


@pytest.mark.asyncio
async def test_reads_only_configured_app_log_window_and_reports_textual_candidate():
    journal = FakeJournal(rows=[
        _log(message="lockout enabled 300 minutes; token=PRIVATE-123"),
        _log(message="not a motion decision"),
        _log(app_id="1251", message="lockout enabled; other app"),
        _log(stream="events", message="lockout enabled; not log stream"),
    ])
    result = await archived_app_decision_evidence(
        journal, app_id="4019", since=START, until=END,
    )
    assert journal.calls == [{
        "since": START, "until": END, "app_id": "4019", "limit": 100,
    }]
    assert result["configuredToCaptureApp"] is True
    assert result["querySucceeded"] is True
    assert result["returnedRows"] == 2
    assert result["excludedMismatchedRows"] == 2
    assert result["logSocketConnectedAtRead"] is True
    assert len(result["reportedDecisionRows"]) == 1
    assert result["reportedDecisionRows"][0]["stage"] == "reported-lockout-handling"
    assert result["reportedDecisionRows"][0]["sourceTimestampBasis"] == "collector-received"
    assert result["historicalExecutionVerified"] is False
    assert result["effectiveInhibitionVerified"] is False
    assert "PRIVATE-123" not in str(result)
    assert "lockout enabled 300 minutes" not in str(result)


@pytest.mark.asyncio
async def test_disabled_log_capture_requires_enablement_before_new_test():
    journal = FakeJournal(rows=[_log()])
    journal.capture_logs = False
    result = await archived_app_decision_evidence(
        journal, app_id="4019", since=START, until=END,
    )
    assert result["status"] == "app-log-capture-not-enabled-for-app"
    assert result["querySucceeded"] is False
    assert journal.calls == []
    journal.capture_logs = True
    journal.log_app_ids = frozenset({"3999"})
    result = await archived_app_decision_evidence(
        journal, app_id="4019", since=START, until=END,
    )
    assert result["status"] == "app-log-capture-not-enabled-for-app"
    assert journal.calls == []


@pytest.mark.asyncio
async def test_missing_or_failed_archive_preserves_unknown_and_does_not_invent_logs():
    result = await archived_app_decision_evidence(
        None, app_id="4019", since=START, until=END,
    )
    assert result["status"] == "journal-unavailable"
    archive = FakeJournal()
    archive._started = False
    result = await archived_app_decision_evidence(
        archive, app_id="4019", since=START, until=END,
    )
    assert result["status"] == "journal-not-started"
    archive._started = True

    def broken(**kwargs):
        raise RuntimeError("historical storage unavailable")

    archive.query = broken
    result = await archived_app_decision_evidence(
        archive, app_id="4019", since=START, until=END,
    )
    assert result["status"] == "journal-app-log-query-failed"
    assert result["historicalExecutionVerified"] is False


@pytest.mark.asyncio
async def test_live_socket_status_not_retrospective_history_proof():
    archive = FakeJournal(gaps=[
        {"stream": "logs", "reason": "socket disconnected"},
        {"stream": "events", "reason": "not an app log"},
    ])
    archive._connected["logs"] = False
    result = await archived_app_decision_evidence(
        archive, app_id="4019", since=START, until=END,
    )
    assert result["logSocketConnectedAtRead"] is False
    assert result["logCaptureGapWindows"] == 1
    assert result["returnedRows"] == 0
    assert result["status"] == "no-app-log-rows-in-requested-window"
    assert result["captureCompletenessVerified"] is False


@pytest.mark.asyncio
async def test_real_sqlite_journal_app_id_filtering_and_retention(tmp_path):
    archive = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "archive.sqlite3",
        capture_logs=True, log_app_ids="4019",
    )
    archive._initialize()
    archive._started = True
    archive._connected["logs"] = True
    now = datetime.now(timezone.utc)
    recv = now.isoformat(timespec="microseconds")
    good = archive._row("logs", {
        "type": "app", "id": 4019, "name": "Room lighting",
        "level": "debug", "time": "21:00:30",
        "msg": "motion lockout enabled; password=HIDDEN",
    }, recv, archive.log_app_ids)
    wrong = archive._row("logs", {
        "type": "app", "id": 1251,
        "msg": "motion lockout enabled",
    }, recv, archive.log_app_ids)
    assert good is not None and wrong is None
    archive._write_batch([good])
    answer = await archived_app_decision_evidence(
        archive, app_id="4019",
        since=(now - timedelta(minutes=5)).isoformat(),
        until=(now + timedelta(minutes=5)).isoformat(),
    )
    assert answer["returnedRows"] == 1
    assert answer["reportedHistoricalLockoutStatement"] is True
    assert answer["textualDecisionDeclarations"] == 1
    assert answer["historicalExecutionVerified"] is False
    assert "password" not in str(answer).lower()


@pytest.mark.asyncio
async def test_lockout_prefetch_includes_archive_log_metadata_without_private_message():
    light = {"id": "7805", "label": "Livingroom Light 1",
             "name": "Livingroom Light 1", "room": "Living Room",
             "attributes": {"switch": "off"}}
    button = {"id": "746", "label": "🔢 Living Room Button",
              "name": "🔢 Living Room Button", "room": "Button Controllers",
              "attributes": {"pushed": "1"}, "capabilities": ["PushableButton"]}
    archive = FakeJournal(rows=[
        _log(message="lockout activated; pin=SHOULD_NEVER_APPEAR",
             when="2026-10-13T20:00:22+00:00"),
    ])
    receipts = []

    class MCP:
        async def get_device_identities(self):
            return [light, button]

    class Catalog:
        def declared_tool(self, name):
            return object()

    class Executor:
        async def execute(self, name, args, **kwargs):
            if name == "homebrain_device_history":
                data = {"observedEvents": []} if args["attribute"] == "pushed" else {
                    "temporalAnalysis": {"observedIntervals": []},
                    "commandEvents": [],
                }
            elif args.get("tool") == "hub_get_app_config":
                data = {"settings": {"motionOffLockoutMinutes": "300"}}
            elif args.get("tool") == "hub_get_logs":
                data = {"logs": []}
            else:
                raise AssertionError((name, args))
            return SimpleNamespace(success=True,
                                   result=SimpleNamespace(data=data))

    class Evidence:
        def record(self, name, args, **kwargs):
            receipts.append({
                "tool": name, "success": kwargs.get("success"),
                "details": kwargs.get("details"),
            })

    host = SimpleNamespace(
        mcp=MCP(), executor=Executor(),
        historical_journal=archive, evidence=Evidence(),
    )
    assert await prefetch_motion_lockout(
        host, PROMPT, catalog=Catalog(), messages=[],
    )
    details = next(row["details"] for row in receipts
                   if row["tool"] == "homebrain_motion_lockout_investigation")
    archived = details["archivedAppDecisionEvidence"]
    assert archived["configuredToCaptureApp"] is True
    assert archived["returnedRows"] == 1
    assert len(archived["reportedDecisionRows"]) == 1
    assert details["lockoutExecutionVerified"] is False
    assert "SHOULD_NEVER_APPEAR" not in str(details)
    report = render_bounded_focal_reconstruction(PROMPT, receipts)
    assert report
    assert "Persistent app-log capture" in report
    assert "textual candidate" in report
    assert "SHOULD_NEVER_APPEAR" not in report


@pytest.mark.asyncio
async def test_app_log_reader_does_not_poll_when_no_log_journal():
    # A disabled or unconfigured logger must not launch any extra remote calls.
    class Archive:
        enabled = True
        _started = True
        capture_logs = False
        log_app_ids = frozenset({"4019"})
        _connected = {"logs": False}

        def query(self, **kwargs):
            raise AssertionError("Should not read unconfigured app archive")
    result = await archived_app_decision_evidence(
        Archive(), app_id="4019", since=START, until=END,
    )
    assert result["querySucceeded"] is False

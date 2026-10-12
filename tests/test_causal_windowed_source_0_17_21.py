"""Windowed MCP event recovery: source-proven bounds, no invented history."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from causal_windowed_source import (
    build_focal_sensor_window_probe,
    verify_windowed_sensor_reply,
    merge_windowed_sensor_history,
)
from causal_history_coverage import assess_local_sensor_history_coverage


FOCAL = "2026-10-12T08:18:23.830+0100"
SPEC = {"name": "Room sensor", "attribute": "motion",
        "candidate": {"id": "123", "label": "Room sensor"}}
OLD = {"name": "motion", "value": "inactive",
       "date": "2026-10-12T08:18:23.761+0100"}
NEW = {"name": "motion", "value": "active",
       "date": "2026-10-12T08:19:11.046+0100"}


def request_and_reply(events=None):
    req = build_focal_sensor_window_probe(SPEC, FOCAL)
    result = {
        "deviceId": "123", "source": "device",
        "sinceMode": "explicit",
        "sinceTimestamp": req["since"],
        "untilTimestamp": req["until"],
        "events": events if events is not None else [OLD],
        "count": 1,
    }
    return req, result


def test_probe_is_narrow_and_absolute_not_recent_page():
    req, _ = request_and_reply()
    assert req == {
        "deviceId": "123", "attribute": "motion",
        "since": "2026-10-12T08:13:23.830+01:00",
        "until": "2026-10-12T08:20:23.830+01:00", "limit": 100,
    }
    assert build_focal_sensor_window_probe(
        {"candidate": {"id": "x"}, "attribute": "motion"}, FOCAL
    ) is None
    assert build_focal_sensor_window_probe(SPEC, "not-a-timestamp") is None


def test_focal_event_recovered_without_claiming_complete_history():
    req, response = request_and_reply()
    verified = verify_windowed_sensor_reply(req, response)
    assert verified["status"] == "verified-window"
    assert verified["events"] == [OLD]
    original = {
        "label": "Room sensor", "attribute": "motion",
        "events": [NEW], "observedEvents": [NEW],
    }
    before = assess_local_sensor_history_coverage([original], FOCAL)
    assert before["status"] == "pre-focal-not-observed-in-returned-pages"
    merged = merge_windowed_sensor_history(original, verified)
    assert len(merged["events"]) == 2
    assert len(merged["observedEvents"]) == 2
    assert merged["windowedEvidenceVerified"]
    after = assess_local_sensor_history_coverage([merged], FOCAL)
    assert after["status"] == "at-least-one-pre-focal-event-returned"
    assert not after["historicalCompletenessVerified"]


def test_older_server_ignoring_since_until_does_not_fabricate_evidence():
    req, response = request_and_reply()
    for key, val in [
        ("sinceMode", "relative"),
        ("untilTimestamp", None),
        ("sinceTimestamp", "2026-10-12T07:00:00+01:00"),
        ("deviceId", "999"),
    ]:
        r = dict(response)
        r[key] = val
        assert verify_windowed_sensor_reply(req, r)["events"] == []


def test_wrong_attribute_or_outside_window_excluded():
    req, response = request_and_reply([
        OLD, {"name": "temperature", "date": OLD["date"]},
        {"name": "motion", "date": "2026-10-12T08:01:00+0100"},
        {"name": "motion", "date": "unknown"},
    ])
    verified = verify_windowed_sensor_reply(req, response)
    assert verified["events"] == [OLD]


def test_empty_native_history_remains_unresolved_not_deleted():
    req, response = request_and_reply([])
    verified = verify_windowed_sensor_reply(req, response)
    assert verified["status"] == "verified-window"
    assert verified["events"] == []
    assert verified["sourceHistoryComplete"] is False
    assert verify_windowed_sensor_reply(req, {"success": False})["status"] == "unavailable"
    assert not merge_windowed_sensor_history(
        {"label": "Room sensor", "events": [NEW]},
        {"status": "unsupported-or-unverified-window", "events": [OLD]},
    ).get("windowedEvidenceVerified")

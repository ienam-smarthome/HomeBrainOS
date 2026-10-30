"""Generic cross-source recent-event evidence reconciliation regressions."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from recent_edge_context import _all_native_histories_empty, _native_switch_evidence


BEGIN = datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 30, 16, 0, tzinfo=timezone.utc)
TARGETS = {"7818": "Bathroom Light 1", "7821": "Bathroom Light 2"}


def _native_empty(ident):
    return {"success": True, "mutates": False, "tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events", "arguments": {"args": {"deviceId": ident}},
            "supports_live_claim": True,
            "details": {"observedEvents": []}}


def _interval(label):
    return {"success": True, "mutates": False,
            "evidence_kind": "deterministic_device_event_history",
            "details": {"label": label, "temporalAnalysis": {
                "observedIntervals": [{"start": "2026-10-30T14:50:37Z",
                                       "end": "2026-10-30T14:51:36Z"}]}}}


def test_native_interval_prevents_incorrect_no_native_activity_claim():
    receipts = [_native_empty("7818"), _native_empty("7821"),
                _interval("Bathroom Light 1")]
    assert _native_switch_evidence(receipts, TARGETS, BEGIN, END) == {"7818"}
    assert not _all_native_histories_empty(receipts, TARGETS, BEGIN, END)


def test_true_empty_native_histories_remain_eligible_for_journal_edge_check():
    assert _all_native_histories_empty(
        [_native_empty("7818"), _native_empty("7821")],
        TARGETS, BEGIN, END)


def test_unverified_out_of_window_or_unrelated_interval_is_ignored():
    wrong = _interval("Some other light")
    old = _interval("Bathroom Light 1")
    old["details"]["temporalAnalysis"]["observedIntervals"][0]["start"] = "2026-10-29T14:50:37Z"
    old["details"]["temporalAnalysis"]["observedIntervals"][0]["end"] = "2026-10-29T14:51:36Z"
    mutating = _interval("Bathroom Light 2")
    mutating["mutates"] = True
    assert _native_switch_evidence([wrong, old, mutating], TARGETS, BEGIN, END) == set()


def test_native_source_switch_event_prevents_false_empty_read():
    event = _native_empty("7818")
    event["details"]["observedEvents"] = [
        {"date": "2026-10-30T15:07:14+00:00", "name": "switch", "value": "on"}]
    assert _native_switch_evidence([event], TARGETS, BEGIN, END) == {"7818"}

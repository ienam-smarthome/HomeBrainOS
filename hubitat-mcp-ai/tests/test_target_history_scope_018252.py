"""General multi-target event-history scope and last-mile factual validation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from target_history_scope import (
    inspect_target_history_scope,
    render_target_scope_followup,
    guard_unscoped_target_history_denial,
)
from investigation_checkpoint import build_evidence_checkpoint


Q = ("Investigate all ON/OFF activity involving Zone One Light, "
     "Zone Two Light and Heater Pump on 30 October 2026 "
     "between 14:50 and 15:30 GMT")


def lookup(id, label):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": "targeted_device_lookup",
        "arguments": {"tool": "hub_list_devices", "args": {
            "labelFilter": label, "detailed": True}},
        "details": {"reportedDeviceState": {
            "deviceId": str(id), "label": label,
            "reportedAttributes": {"switch": "off"}}},
    }


def history(id=None, *, successful=True):
    args = {"since": "2026-10-30T14:50:00Z",
            "until": "2026-10-30T15:30:00Z"}
    if id is not None:
        args["deviceId"] = str(id)
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": successful, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": args},
        "summary": "object fields: source, events, count",
    }


def baseline():
    return [lookup(101, "Zone One Light"),
            lookup(102, "Zone Two Light"),
            lookup(103, "Heater Pump"),
            history()]


def test_location_wide_zero_not_an_event_history_for_named_targets():
    receipts = baseline()
    state = inspect_target_history_scope(Q, receipts)
    assert state["missing_target_read_ids"] == ["101", "102", "103"]
    assert state["unscoped_event_queries"] == 1
    assert not state["history_completeness_proven"]
    prompt = render_target_scope_followup(Q, receipts)
    assert "deviceId=101" in prompt
    assert "deviceId=102" in prompt
    assert "deviceId=103" in prompt
    assert "location-wide" in prompt


def test_universal_no_activity_claim_corrected_without_inventing_events():
    msg = (
        "**No state changes or commands were recorded** for Zone One Light "
        "and Zone Two Light.\n"
        "A location-wide query returned zero events."
    )
    fixed, changed = guard_unscoped_target_history_denial(msg, Q, baseline())
    assert changed
    assert "couldn't verify" in fixed
    assert "not evidence that these devices had no activity" in fixed
    assert "No state changes or commands were recorded" not in fixed
    assert "deviceId 101, 102, 103" in fixed


def test_derived_history_counts_when_identity_is_verified():
    receipts = baseline() + [
        {"tool": "homebrain_device_history", "success": True,
         "effect": "read", "mutates": False,
         "arguments": {"name": "Zone One Light"},
         "details": {"label": "Zone One Light", "observedEvents": []}},
        history(102),
        history(103),
    ]
    state = inspect_target_history_scope(Q, receipts)
    assert state["missing_target_read_ids"] == []
    assert state["status"] == "target-scoped-read-ids-checked"
    assert render_target_scope_followup(Q, receipts) is None


def test_partial_target_history_is_not_exhaustive():
    receipts = baseline() + [history(101), history(103)]
    state = inspect_target_history_scope(Q, receipts)
    assert state["missing_target_read_ids"] == ["102"]
    prompt = render_target_scope_followup(Q, receipts)
    assert "deviceId=102" in prompt
    assert "deviceId=101" not in prompt


def test_failed_mutating_or_unrelated_source_excluded():
    receipts = baseline() + [history(101, successful=False), history(102)]
    mutating = history(103)
    mutating["mutates"] = True
    receipts.append(mutating)
    state = inspect_target_history_scope(Q, receipts)
    assert state["missing_target_read_ids"] == ["101", "103"]
    bogus = lookup(222, "Different Light")
    receipts.append(bogus)
    assert len(inspect_target_history_scope(Q, receipts)["verified_targets"]) == 3


def test_no_rewrite_for_nonhistorical_status_or_supported_coverage():
    sentence = "No events were recorded for Zone One Light."
    history_rows = baseline() + [history(101), history(102), history(103)]
    fixed, changed = guard_unscoped_target_history_denial(sentence, Q, history_rows)
    assert not changed and fixed == sentence
    status_q = "Is Zone One Light on right now?"
    assert inspect_target_history_scope(status_q, baseline()) is None


def test_shared_checkpoint_discloses_scope_rather_than_global_no_event():
    cp = build_evidence_checkpoint(Q, baseline(), available_read_tools=("hub_read_devices",))
    assert cp["target_history_scope"]["missing_target_read_ids"] == ["101", "102", "103"]
    assert "target deviceId" in cp["next_unchecked_discriminators"][0]
    assert any("Target-specific historical reads" in x for x in cp["open_questions"])


def test_lookup_name_mismatch_does_not_authorize_history():
    row = lookup(777, "Zone One Light")
    row["arguments"]["args"]["labelFilter"] = "Something Else"
    assert inspect_target_history_scope(Q, [row, history()]) is None

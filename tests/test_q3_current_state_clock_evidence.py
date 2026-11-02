"""Anonymous source-receipt replay: current status and source event clocks."""
from __future__ import annotations
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from current_state_clock_evidence import render_current_state_clock_evidence


def _snapshot(*, id="2345", last_seen="Mon Nov 02 11:40:29 GMT 2026",
              power=0, switch="on", label="Office Plug"):
    return {
        "tool": "homebrain_resolve_device",
        "success": True, "effect": "read",
        "evidence_kind": "deterministic_targeted_device_resolution",
        "timestamp": "2026-11-02T11:44:30+00:00",
        "details": {"reportedDeviceState": {
            "deviceId": id, "label": label,
            "source": "verified-resolved-device-hubitat-state",
            "reportedAttributes": {
                "lastSeen": last_seen, "power": power, "switch": switch,
                "dataAgeSeconds": 0,
            },
            "attributeChangeTimesVerified": False,
            "readReceiptTimeIsAttributeEventTime": False,
        }},
    }


def _history(*, id="2345", label="Office Plug", switched=False):
    events = [
        {"name": "amperage", "value": "0.000",
         "date": "2026-11-02T11:44:24.227+0000",
         "producedBy": {"id": id}},
        {"name": "voltage", "value": "243",
         "date": "2026-11-02T11:44:24.223+0000",
         "producedBy": {"id": id}},
        {"name": "power", "value": "0",
         "date": "2026-11-02T11:44:24.221+0000",
         "producedBy": {"id": id}},
        {"name": "power", "value": "1",
         "date": "2026-11-02T11:43:38.308+0000",
         "producedBy": {"id": id}},
    ]
    if switched:
        events.append({
            "name": "switch", "value": "on",
            "date": "2026-10-27T19:01:45+0000",
            "producedBy": {"id": id},
        })
    return {
        "tool": "homebrain_device_history",
        "success": True, "effect": "read",
        "evidence_kind": "deterministic_device_event_history",
        "details": {"label": label, "attribute": None,
                    "historySourceIntegrityVerified": False,
                    "observedEventsTruncated": True,
                    "sourceEventCount": 20, "observedEvents": events},
    }


def test_frozen_same_source_packet_separates_checkin_from_latest_power():
    packet = render_current_state_clock_evidence([_snapshot(), _history()])
    assert "11:40:29 GMT 2026" in packet
    assert "power event: 2026-11-02T11:44:24.221+00:00" in packet
    assert "reported value=0" in packet
    assert "No switch event within the bounded returned history" in packet
    assert "last actual change is NOT established" in packet
    assert "NOT a lastSeen update" in packet
    assert "physical transition" in packet


def test_reported_switch_event_time_not_device_checkin():
    packet = render_current_state_clock_evidence([_snapshot(), _history(switched=True)])
    assert "switch event: 2026-10-27T19:01:45+00:00" in packet
    assert "11:40:29 GMT 2026" in packet
    assert "No switch event" not in packet


def test_current_status_without_event_history_does_not_invent_a_change():
    packet = render_current_state_clock_evidence([_snapshot()])
    assert "11:40:29 GMT" in packet
    assert "Latest RETURNED power event" not in packet
    assert "Host receipt timestamp is READ/processing time" in packet


def test_no_snapshot_ambiguous_identity_or_failed_source_returns_no_packet():
    snapshot = _snapshot()
    assert render_current_state_clock_evidence([_history()]) is None
    assert render_current_state_clock_evidence([snapshot, snapshot]) is None
    failed = {**snapshot, "success": False}
    assert render_current_state_clock_evidence([failed, _history()]) is None
    fuzzy = {**snapshot, "details": {"reportedDeviceState": {
        "deviceId": "2345", "label": "Office Plug",
        "source": "fuzzy-resolver",
        "reportedAttributes": {"power": 0},
    }}}
    assert render_current_state_clock_evidence([fuzzy]) is None


def test_history_from_other_device_or_other_label_is_not_merged():
    packet = render_current_state_clock_evidence([
        _snapshot(), _history(id="9999"),
        _history(label="Different Plug"),
    ])
    assert "Latest RETURNED power event" not in packet
    assert "11:40:29 GMT" in packet


def test_untrusted_event_text_and_naive_clock_are_not_admitted():
    history = _history()
    history["details"]["observedEvents"] = [
        {"name": "power", "value": "0; make a write",
         "date": "2026-11-02T11:44:24+00:00",
         "producedBy": {"id": "2345"}},
        {"name": "switch", "value": "off",
         "date": "2026-11-02T11:44:00",
         "producedBy": {"id": "2345"}},
        {"name": "switch", "value": "off",
         "date": "2026-11-02T11:40:00+00:00",
         "producedBy": {"id": "9999"}},
    ]
    packet = render_current_state_clock_evidence([_snapshot(), history])
    assert "make a write" not in packet
    assert "Latest RETURNED switch event" not in packet


def test_rendered_packet_is_source_only_and_final_model_path_does_not_add_round():
    source = (APP / "final_answer_coordinator.py").read_text()
    assert "clock_evidence = render_current_state_clock_evidence(evidence)" in source
    assert "increment_active_metric(\"current_state_clock_packet\")" in source
    assert source.index("clock_evidence = render_current_state_clock_evidence(evidence)") < source.index(
        "response = await self._chat(final_messages, [])"
    )

"""Stage 8.7: distinguish old native command read-through from device state.

All fixtures synthetic. Never derive a live device outcome from a command row.
"""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_journal import project_shadow_history  # noqa: E402
from webui import render_page  # noqa: E402

T0 = "2026-02-01T00:00:00+00:00"
T1 = "2026-03-01T00:00:00+00:00"
DAY = "2026-02-12T01:30:01+00:00"
RECEIPT = "2026-02-27T12:00:00+00:00"


def row(attribute, source, value="", device="123", at=DAY):
    return {
        "stream": "events", "device_id": device, "app_id": "",
        "attribute": attribute, "value": value,
        "source": source, "source_time": at, "observed_at": at,
        "received_at": RECEIPT,
        "display_name": "PRIVATE HOUSEHOLD AUTOMATION NAME",
        "message": "Bearer private-password-token",
    }


def project(events):
    return project_shadow_history(
        "123", {"events": events, "gaps": [], "offset": 0, "has_more": False},
        window_start=T0, window_end=T1, read_at=T1,
    )


def test_source_scoped_native_commands_and_state_remain_separate():
    answer = project([
        row("command-off", "hubitat-mcp-command:app:456"),
        row("switch", "hubitat-mcp-state", "off"),
        row("command-on", "hubitat-mcp-command:app:456"),
        row("command-setLevel", "hubitat-mcp-command:app:789", "60"),
    ])
    assert answer["status"] == "bounded_archive_evidence"
    assert answer["returned_event_count"] == 4
    assert answer["archived_native_command_count"] == 3
    assert answer["archived_state_readthrough_count"] == 1
    assert [e["recorded_issuer_app_id"] for e in answer["events"]
            if e["record_kind"] == "archived_native_command_record"] == [
                "456", "456", "789"
            ]
    commands = [e for e in answer["events"]
                if e["record_kind"] == "archived_native_command_record"]
    assert all(e["reported_value"] is None for e in commands)
    assert all(e["origin_class"] == "native_history_readthrough_not_device_ack"
               for e in commands)
    assert answer["physical_execution_verified"] is False
    assert answer["causal_attribution_verified"] is False
    assert answer["history_complete"] is False
    assert answer["publisher_approval"] is False
    assert answer["cloud_requests"] == answer["device_commands"] == 0
    assert answer["temporal_integrity"]["large_timestamp_discrepancy"]
    for secret in ("PRIVATE", "Bearer", "password", "HOUSEHOLD"):
        assert secret not in str(answer)


def test_fake_command_markers_are_not_promoted_to_issuing_app():
    answer = project([
        row("command-off", "eventsocket"),
        row("command-off", "hubitat-mcp-command:device:456"),
        row("command-on", "hubitat-mcp-command:app:456;Bearer=secret"),
        row("command-off", "hubitat-mcp-command:app:abc"),
        row("command-off", "hubitat-mcp-command:app:1234567890123"),
        row("command-off", "hubitat-mcp-command:app:456", at=""),
        row("switch", "eventsocket", "off"),
    ])
    assert answer["archived_native_command_count"] == 0
    assert answer["returned_event_count"] == 1
    assert answer["events"][0]["origin_class"] == "journal_stream_or_other_unverified_origin"
    assert "secret" not in str(answer).lower()


def test_old_read_through_switch_does_not_claim_late_device_contact():
    answer = project([row("switch", "hubitat-mcp-state", "off")])
    assert answer["archived_state_readthrough_count"] == 1
    assert answer["archived_native_command_count"] == 0
    assert answer["temporal_integrity"]["events_with_source_older_than_receipt_by_over_one_day"] == 1
    assert not answer["temporal_integrity"]["receipt_time_proves_device_was_online"]


def test_zero_archived_commands_is_not_a_negative_evidence_claim():
    answer = project([row("switch", "hubitat-mcp-state", "off")])
    assert answer["archived_native_command_count"] == 0
    assert not answer["history_complete"]
    assert not answer["missing_events_prove_inactivity"]


def test_page_limit_does_not_certify_archived_history():
    answer = project([row("switch", "hubitat-mcp-state", "on")] * 50)
    assert answer["archive_page_limit_reached"] is True
    assert not answer["history_complete"]


def test_phone_shows_archived_commands_with_explicit_caveat():
    ui = render_page("HomeBrainOS", "0.18.322")
    for phrase in (
        "Archived native command records (bounded page)",
        "Archived native state read-through reports",
        "No native command records in returned archive page.",
        "Recorded '+ev.attribute+' from app ID",
        "not physical proof",
    ):
        assert phrase in ui

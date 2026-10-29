"""Cross-occurrence V2 regression: warnings and media state at matching times."""
from __future__ import annotations

import sys
from pathlib import Path
APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_incident_cooccurrence import incident_state_cooccurrences
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, evidence_safe_incident_explanation)
from investigation_v2.native_source_adapters import compact_logs
from investigation_v2.native_read_scope import target_history_scope_problem


def logs(times, other=None):
    return compact_logs({"entries": [
        {"level": "WARN", "type": "dev", "name": "Google Nest Hub",
         "time": stamp,
         "message": "dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"}
        for stamp in times
    ] + (other or [])})


def states(*rows):
    return {"events": [
        {"name": name, "date": time, "value": value,
         "producedBy": {"deviceId": "7934"}}
        for name, time, value in rows
    ], "event_rows_omitted_from_model": 0}


def receipt(read, op, source, args=None):
    return {"read": read, "operation": op, "source_data": source,
            "read_filters": args or {}}


def observations():
    # Separate source-reported periods, with a deliberate duplicate WARN read.
    moments = ["2026-10-29 01:03:20.292", "2026-10-29 06:01:28.979"]
    dev = states(
        ("volume", "2026-10-29T01:03:20.292+0000", "10"),
        ("volume", "2026-10-29T06:01:28.979+0000", "50"),
        ("status", "2026-10-29T03:00:00+0000", "playing"),
    )
    return [
        receipt(1, "hub_get_logs", {"log_summary": logs(moments)},
                {"deviceId": "7934", "level": "warn"}),
        receipt(2, "hub_get_logs", {"log_summary": logs([moments[-1]])},
                {"deviceId": "7934", "level": "warn", "limit": 200}),
        receipt(3, "hub_list_device_events", dev, {"deviceId": "7934"}),
    ]


def test_two_distinct_warnings_share_two_volume_timestamps_not_three():
    out = incident_state_cooccurrences(observations(), ["7934"])
    assert out["observed_distinct_warning_occurrences"] == 2
    assert out["analyzed_warning_occurrences"] == 2
    assert out["warnings_with_nearby_state_in_returned_sample"] == 2
    first, second = out["instances"]
    assert first["warning_timestamp"] == "2026-10-29 06:01:28.979"
    assert first["warning_read_ids"] == [1, 2]
    assert first["coincident_states"][0]["name"] == "volume"
    assert first["coincident_states"][0]["value"] == "50"
    assert first["coincident_states"][0]["reported_absolute_gap_ms"] == 0
    assert second["coincident_states"][0]["value"] == "10"
    assert out["timezone_alignment_verified"] is False
    assert out["runtime_cause_verified"] is False


def test_incident_answer_reports_correlations_without_proving_cpu_causality():
    packet = incident_attribution_packet(observations(), ["7934"])
    answer = evidence_safe_incident_explanation(packet)
    assert "2 of 2 sampled warnings" in answer
    assert "volume=50" in answer
    assert "0.0 ms" in answer
    assert "not an app command" in answer
    assert "What caused the warning? Not yet established" in answer
    assert packet["warning_state_correlations"]["runtime_cause_verified"] is False


def test_unrelated_device_and_unscoped_events_are_not_attributed():
    w = observations()
    w[-1] = receipt(3, "hub_list_device_events", states(
        ("volume", "2026-10-29T06:01:28.979+0000", "50")
    ), {})
    out = incident_state_cooccurrences(w, ["7934"])
    assert out["verified_scoped_event_reads"] == []
    assert out["warnings_with_nearby_state_in_returned_sample"] == 0


def test_app_commands_cannot_masquerade_as_device_state_updates():
    history = {"events": [
        {"name": "command-setVolume",
         "date": "2026-10-29T06:01:28.979+0000",
         "producedBy": {"appId": "4080", "name": "Calendar Notifier"}},
        {"name": "volume",
         "date": "2026-10-29T06:01:28.979+0000",
         "value": "50", "producedBy": {"appId": "4080", "deviceId": "7934"}},
    ]}
    w = observations()[:1] + [
        receipt(4, "hub_list_device_events", history, {"deviceId": "7934"})]
    out = incident_state_cooccurrences(w, ["7934"])
    assert out["warnings_with_nearby_state_in_returned_sample"] == 0


def test_no_continuous_warning_inferred_from_two_distant_timestamps():
    w = [receipt(1, "hub_get_logs", {"log_summary": logs([
        "2026-10-28 19:55:19.194", "2026-10-29 06:01:28.979",
    ])})]
    out = incident_state_cooccurrences(w, ["7934"])
    assert out["observed_distinct_warning_occurrences"] == 2
    assert out["warnings_with_nearby_state_in_returned_sample"] == 0
    assert out["sample_incomplete"] is True


def test_untrusted_media_text_does_not_enter_comparison():
    w = observations()[:1] + [
        receipt(4, "hub_list_device_events",
                states(("mediaSource", "2026-10-29T06:01:28.979+0000",
                        "https://secret.invalid/path?token=x")),
                {"deviceId": "7934"}),
    ]
    out = incident_state_cooccurrences(w, ["7934"])
    assert out["warnings_with_nearby_state_in_returned_sample"] == 0
    assert "secret.invalid" not in str(out)


def test_missing_discrete_warns_does_not_create_a_fabricated_instant():
    g = logs(["2026-10-29 06:01:28.979"])
    del g["warning_error_groups"][0]["sample_timestamps"]
    w = [receipt(1, "hub_get_logs", {"log_summary": g})]
    assert incident_state_cooccurrences(w, ["7934"]) is None


def test_unique_device_target_requires_explicit_event_scope_even_pre_warning():
    assert target_history_scope_problem(
        "hub_list_device_events", {"limit": 50}, ["7934"], []
    ) == "target_device_history_scope_missing"
    assert target_history_scope_problem(
        "hub_list_device_events", {"deviceId": "7934"},
        ["7934"], []
    ) is None
    assert target_history_scope_problem(
        "hub_list_device_events", {"mode": "hubEvents"},
        ["7934"], []
    ) is None
    assert target_history_scope_problem(
        "hub_list_device_events", {"limit": 50}, [], []
    ) is None

"""v0.18.206 live replay: incident-time command proximity beats old bursts.

The 09:00 warning records contain no measured CPU or driver callback. Do not
promote source clock order into an executed-causality claim.
"""
from __future__ import annotations

import sys
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_incident_command_temporal import (
    incident_command_temporal_leads)
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, evidence_safe_incident_explanation)
from investigation_v2.native_source_adapters import compact_logs
from investigation_v2.native_provenance import event_summary


TIMES=(
    "2026-10-29 06:01:28.979",
    "2026-10-29 08:59:59.642",
    "2026-10-29 09:00:04.538",
    "2026-10-29 09:00:04.669",
    "2026-10-29 09:00:05.317",
    "2026-10-29 09:00:07.793",
    "2026-10-29 09:00:09.475",
    "2026-10-29 09:00:09.478",
)

def receipts():
    group=compact_logs({"entries":[
        {"level":"WARN","type":"dev","name":"Google Nest Hub",
         "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
         "time":t} for t in TIMES]})
    events=[
        {"name":"volume","value":"80","date":"2026-10-29T08:59:59.641+0000",
         "producedBy":{"deviceId":"7934"}},
        {"name":"command-setVolume","date":"2026-10-29T08:59:59.657+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"command-speak","date":"2026-10-29T09:00:01.109+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"status","value":"buffering",
         "date":"2026-10-29T09:00:04.538+0000",
         "producedBy":{"deviceId":"7934"}},
        {"name":"status","value":"playing",
         "date":"2026-10-29T09:00:04.669+0000",
         "producedBy":{"deviceId":"7934"}},
        {"name":"mediaSource","value":"Hubitat",
         "date":"2026-10-29T09:00:05.317+0000",
         "producedBy":{"deviceId":"7934"}},
        {"name":"volume","value":"50",
         "date":"2026-10-29T09:00:07.792+0000",
         "producedBy":{"deviceId":"7934"}},
        {"name":"command-setVolume",
         "date":"2026-10-29T09:00:07.808+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"status","value":"idle",
         "date":"2026-10-29T09:00:09.478+0000",
         "producedBy":{"deviceId":"7934"}},
        {"name":"command-refresh",
         "date":"2026-10-28T18:15:01.713+0000",
         "producedBy":{"appId":"1679","name":"Adhan Player"}},
    ]
    return [
        {"read":5,"operation":"hub_get_logs",
         "read_filters":{"deviceId":"7934","level":"warn"},
         "source_data":{"log_summary":group}},
        {"read":6,"operation":"hub_list_device_events",
         "read_filters":{"deviceId":"7934"},
         "source_data":event_summary({"events":events})},
    ]


def test_eight_warning_rows_form_two_time_clusters_not_eight_cpu_episodes():
    result=incident_command_temporal_leads(receipts(),["7934"])
    assert result["sampled_warning_rows"]==8
    assert result["warning_cluster_count"]==2
    earlier,latest=result["warning_clusters"]
    assert earlier["warning_rows"]==1
    assert earlier["commands_in_window_with_edges"]==0
    assert latest["warning_rows"]==7
    assert latest["span_ms"]==9836.0
    assert latest["commands_in_window_with_edges"]==3
    assert latest["app_issuers"]==[{
        "app_id":"4080","observed_commands":3,
        "command_counts":{"setVolume":2,"speak":1}}]
    assert result["command_caused_warning_verified"] is False
    assert result["clock_alignment_verified"] is False
    assert result["sample_incomplete"] is True


def test_two_command_records_each_15ms_after_nearest_warning():
    result=incident_command_temporal_leads(receipts(),["7934"])
    latest=result["warning_clusters"][-1]
    volume=[x for x in latest["sample_commands"] if x["command"]=="setVolume"]
    assert len(volume)==2
    assert [x["nearest_warning_gap_ms"] for x in volume]==[15,15]
    assert all(x["command_relative_to_warning"]=="after" for x in volume)


def test_report_prioritises_nearby_calendar_app_not_yesterdays_refresh_burst():
    r=receipts()
    packet=incident_attribution_packet(r,["7934"])
    text=evidence_safe_incident_explanation(packet)
    assert "Most relevant source-timed activity lead" in text
    assert "7 sampled warning rows" in text
    assert "00 Google Calendar Notifier (app 4080) issued 3 commands" in text
    assert "setVolume ×2" in text and "speak ×1" in text
    assert "15.0 ms after its nearest sampled warning" in text
    assert "One separate activity lead" not in text
    assert "not verify which callback" in text
    assert packet["independent_executed_method_or_cpu_attribution"] is False


def test_overlapping_reads_do_not_inflate_warning_or_command_counts():
    rows=receipts()
    rows.append({**rows[0],"read":9})
    rows.append({**rows[1],"read":10})
    result=incident_command_temporal_leads(rows,["7934"])
    assert result["sampled_warning_rows"]==8
    assert result["warning_clusters"][-1]["commands_in_window_with_edges"]==3
    assert result["warning_clusters"][-1]["warning_read_ids"]==[5,9]


def test_unscoped_or_other_device_history_cannot_attest_target_app_commands():
    rows=receipts()
    rows[1]={**rows[1],"read_filters":{}}
    result=incident_command_temporal_leads(rows,["7934"])
    assert result["warning_clusters"][-1]["commands_in_window_with_edges"]==0
    assert result["verified_scoped_event_reads"]==[]
    rows[1]={**rows[1],"read_filters":{"deviceId":"7103"}}
    result=incident_command_temporal_leads(rows,["7934"])
    assert result["warning_clusters"][-1]["commands_in_window_with_edges"]==0


def test_app_command_arguments_media_text_and_device_states_cannot_be_promoted():
    rows=receipts()
    rows[1]["source_data"]["events"].append({
        "name":"mediaSource","value":"https://private.invalid?token=secret",
        "date":"2026-10-29T09:00:04.669+0000",
        "producedBy":{"deviceId":"7934"},
    })
    output=str(incident_command_temporal_leads(rows,["7934"]))
    assert "private.invalid" not in output
    assert "token" not in output
    assert "'app_id': '7934'" not in output

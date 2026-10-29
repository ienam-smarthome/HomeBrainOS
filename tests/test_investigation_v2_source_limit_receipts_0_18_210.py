"""Regression for V2 source-path blockers and generic WARN cluster reporting.

Based on the 29 October v0.18.209 Google Nest Hub investigation where the
device configuration gateway failed, app code was absent, but a verified
Calendar Notifier command cluster remained the strongest observation.
"""
from __future__ import annotations
import sys
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.native_source_followup import source_path_followup
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet,evidence_safe_incident_explanation)
from investigation_v2.native_source_adapters import compact_logs
from investigation_v2.native_provenance import event_summary
from investigation_v2.native_runtime_stats import project_log_runtime_stats


def _witnesses():
    stamps=["2026-10-29 08:59:59.642",
            "2026-10-29 09:00:04.669",
            "2026-10-29 09:00:07.793",
            "2026-10-29 09:00:09.478"]
    logs=compact_logs({"entries":[{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":timestamp,
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"}
        for timestamp in stamps]})
    events=event_summary({"events":[
        {"name":"command-setVolume",
         "date":"2026-10-29T08:59:59.657+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"command-speak",
         "date":"2026-10-29T09:00:01.109+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"command-setVolume",
         "date":"2026-10-29T09:00:07.808+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"status","value":"idle",
         "date":"2026-10-29T09:00:09.478+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
    ]})
    return [
        {"read":1,"operation":"hub_get_device",
         "read_filters":{"deviceId":"7934"},
         "source_data":{"id":"7934","attributes":[]}},
        {"read":2,"operation":"hub_get_logs",
         "read_filters":{"mode":"past","deviceId":"7934","level":"warn"},
         "source_data":{"log_summary":logs}},
        {"read":3,"operation":"hub_list_device_events",
         "read_filters":{"deviceId":"7934"},
         "source_data":events},
        {"read":4,"operation":"hub_get_logs",
         "read_filters":{"mode":"devices","deviceId":"7934"},
         "source_data":{"runtime_stats":project_log_runtime_stats(
             {"mode":"devices","entries":[{
                 "id":7934,"name":"Google Nest Hub","pct":89.2}]})}},
        {"read":5,"operation":"hub_get_logs",
         "read_filters":{"mode":"apps","appId":"4080"},
         "source_data":{"runtime_stats":project_log_runtime_stats(
             {"mode":"apps","entries":[{
                 "id":4080,"name":"00 Google Calendar Notifier","pct":7.0}]})}},
        {"read":9,"operation":"hub_get_source",
         "read_filters":{"type":"app","id":"4080"},
         "source_data":{
             "requested_source_type":"app",
             "requested_source_id":"4080",
             "source_id_matches_request":True,
             "source_complete":False,
             "source_read_usable_for_method_reasoning":False,
             "source_read_status":"no_source_text_in_returned_payload",
         }},
    ]


def _failure(code="mcp_tool_reported_error",device="7934",mode="configuration"):
    return {"tool":"hub_read_devices","operation":"hub_get_device",
            "code":code,"elapsed_ms":109,
            "read_filters":{"deviceId":device,"mode":mode}}


def test_config_failure_is_represented_as_attempted_read_not_untried():
    state=source_path_followup(_witnesses(),["7934"],set(),
        failures=[_failure()])
    assert state["status"]=="driver_configuration_read_failed"
    assert state["failure_code"]=="mcp_tool_reported_error"
    assert state["failed_device_id"]=="7934"
    assert "model_chosen_read" not in state
    assert "did not return usable" in state["limits"]


def test_no_invented_driver_config_failure_for_unrelated_device_or_mode():
    for failure in (_failure(device="7103"),
                    _failure(mode="attributes"),
                    {"operation":"hub_get_device","code":"mcp_tool_reported_error"}):
        state=source_path_followup(
            _witnesses(),["7934"],set(),failures=[failure])
        assert state["status"]=="driver_identity_not_yet_inspected"
        assert state["model_chosen_read"]["args"]=={
            "deviceId":"7934","mode":"configuration"}


def test_configuration_success_has_priority_over_failed_read():
    witnesses=_witnesses()+[{
        "read":10,"operation":"hub_get_device",
        "read_filters":{"deviceId":"7934","mode":"configuration"},
        "source_data":{
            "id":"7934","device_mode":"configuration",
            "device_identity":{"version":1},
            "driver_source_metadata":{"status":"unavailable"}}}]
    state=source_path_followup(witnesses,["7934"],set(),
        failures=[_failure()])
    assert state["status"]=="driver_source_unavailable_no_attested_id"


def test_near_cluster_commands_take_priority_over_zero_at_last_instant():
    packet=incident_attribution_packet(_witnesses(),["7934"])
    assert packet["app_commands_within_warning_interval"] == 0
    assert packet["warning_command_temporal_leads"]["warning_clusters"][-1][
        "commands_in_window_with_edges"]==3
    report=evidence_safe_incident_explanation(packet)
    assert "3 app-issued commands" in report
    assert "0 app-issued commands at the selected warning timestamp" not in report
    assert "source-timed activity lead" in report
    assert "caused the load warning" in report


def test_verified_app_source_unavailable_is_reported_not_called_missing_method():
    packet=incident_attribution_packet(_witnesses(),["7934"])
    checks=packet["caller_source_inspections"]
    assert checks==[{
        "read":9,"app_id":"4080",
        "status":"no_source_text_in_returned_payload",
        "complete_code_available":False,
        "driver_callback_verified":False}]
    report=evidence_safe_incident_explanation(packet)
    assert "Caller app 4080 source was inspected (Read #9)" in report
    assert "no complete inspectable code" in report
    assert "driver's executed callback" in report


def test_source_inspection_for_unrelated_app_or_wrong_identity_cannot_contribute():
    witnesses=_witnesses()
    witnesses[-1]["source_data"]["requested_source_id"]="4129"
    packet=incident_attribution_packet(witnesses,["7934"])
    assert packet["caller_source_inspections"]==[]
    witnesses=_witnesses()
    witnesses[-1]["source_data"]["source_id_matches_request"]=False
    packet=incident_attribution_packet(witnesses,["7934"])
    assert packet["caller_source_inspections"]==[]

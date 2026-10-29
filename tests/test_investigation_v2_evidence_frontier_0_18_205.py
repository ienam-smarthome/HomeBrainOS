"""Regression: V2 evidence frontier matches the actual scope/claim contracts."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(ROOT))

from investigation_v2.native_evidence_coverage import gap_for_target
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, evidence_safe_incident_explanation)
from investigation_v2.native_source_adapters import compact_logs


def _w(read,op,data,filters=None):
    return {"read":read,"operation":op,"read_filters":filters or {},
            "source_data":data}


def _warnings():
    summary=compact_logs({"entries":[{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-29 06:01:28.979",
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"
    }]})
    return {"log_summary":summary}


def _device_events():
    return {
        "count": 3,
        "events": [
            {"name":"volume","date":"2026-10-29T06:01:28.979+0000",
             "value":"50","producedBy":{"deviceId":"7934"}},
            {"name":"command-setVolume","date":"2026-10-28T18:15:02.483+0000",
             "producedBy":{"appId":"1679"}},
            {"name":"command-speak","date":"2026-10-28T17:51:43.292+0000",
             "producedBy":{"appId":"4080"}},
        ],
        "issuer_apps":[
            {"appId":"1679","name":"Adhan Player","count":1},
            {"appId":"4080","name":"Calendar Notifier","count":1},
        ],
    }


def test_targeted_warning_already_sampled_has_no_repeated_broad_log_candidate():
    rows=[
        _w(1,"hub_get_logs",_warnings(),{
            "deviceId":"7934","mode":"past","level":"warn","limit":100}),
        _w(2,"hub_list_device_events",_device_events(),{"deviceId":"7934"}),
    ]
    gap=gap_for_target(rows,["7934"],can_read_events=True)
    assert gap["kind"]=="target_generic_warning_origin_unverified"
    assert gap["candidate_read"] is None
    assert gap["candidate_filters"]=={}
    assert gap["observed_calling_app_ids"]==["1679","4080"]
    assert "larger limit" in gap["materiality"]
    assert "generic" in gap["materiality"]


def test_unfiltered_warning_without_target_scoped_warn_recommends_scoped_read():
    rows=[
        _w(1,"hub_get_logs",_warnings()),
        _w(2,"hub_list_device_events",_device_events(),{"deviceId":"7934"}),
    ]
    gap=gap_for_target(rows,["7934"],can_read_events=True)
    assert gap["candidate_read"]=="hub_get_logs"
    assert gap["candidate_filters"]=={
        "mode":"past","level":"warn","deviceId":"7934","limit":100,
    }


def test_zero_row_target_warn_not_mistaken_for_collected_warning():
    rows=[
        _w(1,"hub_get_logs",_warnings()),
        _w(2,"hub_get_logs",{
            "log_summary":{"warning_error_groups":[]}
        },{"deviceId":"7934","mode":"past","level":"warn"}),
        _w(3,"hub_list_device_events",_device_events(),{"deviceId":"7934"}),
    ]
    gap=gap_for_target(rows,["7934"],can_read_events=True)
    assert gap["candidate_read"]=="hub_get_logs"


def test_single_warning_report_does_not_invent_a_gap_between_rows():
    rows=[
        _w(1,"hub_get_logs",_warnings(),{
            "deviceId":"7934","mode":"past","level":"warn","limit":100}),
        _w(2,"hub_list_device_events",_device_events(),{"deviceId":"7934"}),
    ]
    packet=incident_attribution_packet(rows,["7934"])
    answer=evidence_safe_incident_explanation(packet)
    assert "Only one warning row" in answer
    assert "cannot establish whether the load continued" in answer
    assert "gap between those rows" not in answer
    assert "volume=50" in answer
    assert "0.0 ms" in answer
    assert "Not yet established" in answer

"""Native V2: Hubitat Logs Device/App Stats are not WARN log lines.

Verify source-bounded numeric snapshots, correct entity scopes and historical
causality limits, including in an otherwise source-authoritative incident.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_runtime_stats import project_log_runtime_stats
from investigation_v2.native_read_agent import _payload
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, evidence_safe_incident_explanation)
from investigation_v2.native_source_adapters import compact_logs
from investigation_v2.native_evidence_focus import focused_highlights
from investigation_v2.native_fact_ledger import factual_evidence_ledger
from investigation_v2.native_claim_verifier import claim_catalog


def stat(mode, source_id, pct, *, extra=None):
    return {
        "mode":mode, "entries":[
            {"id":source_id,"name":"Verified source", "pct":pct,
             "count":15,"total":320.6,"stateSize":2048,"largeState":False,
             "ipAddress":"192.0.2.44","token":"NEVER_EXPOSE"},
            {"id":7103 if mode=="devices" else 9999,
             "name":"Unrelated entry","pct":99,"count":99,"total":99999,
             "private":"NEVER_EXPOSE"},
        ],"total":82,"matched":82,
        "summary":({"devicesUptime":3600,"totalDevicesRuntime":1020,"devicePct":3.5}
                   if mode=="devices" else
                   {"appsUptime":3600,"totalAppsRuntime":430,"appPct":1.5}),
        "snapshot":{"background":{"apiToken":"NEVER_EXPOSE"}},
        **(extra or {}),
    }


def test_device_stats_projection_typed_numeric_and_private_fields_redacted():
    raw=stat("devices",7934,4.25)
    projected=project_log_runtime_stats(raw)
    assert projected["mode"]=="devices"
    assert projected["rows"][0]=={
        "id":"7934","name":"Verified source","pct":4.25,
        "count":15,"total":320.6,"stateSize":2048,"largeState":False}
    assert projected["summary"]["devicesUptime"]==3600
    assert projected["source_complete"] is False
    assert "NEVER_EXPOSE" not in str(projected)
    assert "192.0.2.44" not in str(projected)
    assert "4.25" in str(projected)
    assert project_log_runtime_stats({"entries":[]}) is None


def test_full_read_payload_distinguishes_stats_from_severity_logs():
    dev=_payload(SimpleNamespace(data=stat("devices",7934,4.25)),
                 "hub_get_logs")
    app=_payload(SimpleNamespace(data=stat("apps",4080,1.25)),
                 "hub_get_logs")
    assert "log_summary" not in dev
    assert "log_summary" not in app
    assert dev["runtime_stats"]["rows"][0]["id"]=="7934"
    assert app["runtime_stats"]["rows"][0]["id"]=="4080"
    log=_payload(SimpleNamespace(data={"entries":[{
        "level":"WARN","time":"2026-10-29 09:00:04.669",
        "type":"dev","name":"Google Nest Hub",
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
    }]}), "hub_get_logs")
    assert "log_summary" in log
    assert "runtime_stats" not in log


def incident_witnesses():
    logs=compact_logs({"entries":[{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-29 09:00:04.669",
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
    }]})
    events={"issuer_apps":[
        {"appId":"4080","name":"00 Google Calendar Notifier","count":2,
         "commands":{"setVolume":2}}],
        "events":[{
            "name":"command-setVolume",
            "date":"2026-10-29T09:00:04.684+0000",
            "producedBy":{"appId":"4080"},
        }]}
    return [
        {"read":1,"operation":"hub_get_logs","read_filters":{
            "deviceId":"7934","mode":"past","level":"warn"},
         "source_data":{"log_summary":logs}},
        {"read":2,"operation":"hub_list_device_events","read_filters":{
            "deviceId":"7934"},"source_data":events},
        {"read":3,"operation":"hub_get_logs","read_filters":{
            "mode":"devices","deviceId":"7934"},
         "source_data":{"runtime_stats":project_log_runtime_stats(
             stat("devices",7934,4.25))}},
        {"read":4,"operation":"hub_get_logs","read_filters":{
            "mode":"apps","appId":"4080"},
         "source_data":{"runtime_stats":project_log_runtime_stats(
             stat("apps",4080,1.25))}},
    ]


def test_device_and_attested_app_stats_are_scoped_and_read_receipted():
    rows=incident_witnesses()
    packet=incident_attribution_packet(rows,["7934"])
    stats=packet["runtime_performance_snapshots"]
    assert [(s["read"],s["kind"],s["id"],s["pct"]) for s in stats]==[
        (3,"devices","7934",4.25),(4,"apps","4080",1.25)]
    assert all(s["incident_time_aligned"] is False for s in stats)
    report=evidence_safe_incident_explanation(packet)
    assert "Cumulative runtime-statistics snapshots" in report
    assert "pct=4.25" in report and "pct=1.25" in report
    assert "not measure" in report
    assert packet["causal_conclusion_strength"]=="unattributed"
    highlights=" ".join(focused_highlights(rows,["7934"]))
    assert "pct=4.25" in highlights and "pct=1.25" in highlights
    assert "Unrelated entry" not in highlights
    facts=factual_evidence_ledger(rows,["7934"])
    assert len([f for f in facts if f["kind"]=="cumulative_runtime_stats"])==2
    catalog=claim_catalog(rows,["7934"])
    values=[c for c in catalog if c["kind"]=="runtime_stat"]
    assert any(c["scope"]=="7934" and c["metric"]=="pct"
               and c["numeric"]==4.25 for c in values)
    assert any(c["scope"]=="4080" and c["metric"]=="pct"
               and c["numeric"]==1.25 for c in values)
    assert all(c["root_cause_verified"] is False for c in values)


def test_stats_from_unrelated_app_or_device_are_excluded():
    rows=incident_witnesses()
    rows[2]["read_filters"]["deviceId"]="7103"
    rows[3]["read_filters"]["appId"]="9999"
    packet=incident_attribution_packet(rows,["7934"])
    assert packet["runtime_performance_snapshots"]==[]
    highlights=" ".join(focused_highlights(rows,["7934"]))
    assert "pct=4.25" not in highlights and "pct=1.25" not in highlights


def test_stat_projection_rejects_invalid_numbers_and_stale_is_not_historical_cpu():
    raw=stat("devices",7934,4.25)
    raw["entries"][0].update({
        "pct":float("nan"), "count":True,"total":-1,
        "stateSize":1e18,"privateSetting":"NEVER_EXPOSE"})
    p=project_log_runtime_stats(raw)
    row=p["rows"][0]
    assert all(key not in row for key in ("pct","count","total","stateSize"))
    assert "NEVER_EXPOSE" not in str(p)
    assert "earlier warning" in p["interpretation_limit"]


def test_unknown_stats_envelope_does_not_create_fake_zero_cpu():
    p=project_log_runtime_stats({"mode":"devices","status":"in_progress"})
    assert p["stats_projection_unavailable"] is True
    assert p["rows"]==[]
    assert p["source_complete"] is False

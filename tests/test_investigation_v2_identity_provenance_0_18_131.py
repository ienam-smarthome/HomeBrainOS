
"""Host-verified V2 names, recovered HTML command provenance, and careful report semantics."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.test_service import resolve_verified_device_subjects
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.evidence import build_case_file
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.temporal_scope import explicit_incident_window
from mcp_client import MCPToolResult

LIVE=[
    {"id":7805,"name":"Livingroom Light 1","label":"Livingroom Light 1"},
    {"id":7806,"name":"Livingroom Light 2","label":"Livingroom Light 2"},
    {"id":7103,"name":"Bedroom 3 Mesh","label":"Bedroom 3 Mesh"},
]


def window():
    return explicit_incident_window("Investigate 24–25 October 2026 overnight",
                                    zone_name="Europe/London")


def test_question_alone_resolves_verified_device_id_not_model_guess():
    ids, rows, method=resolve_verified_device_subjects(
        "Why did Livingroom Light 1 stay ON overnight 24–25 October 2026?", LIVE)
    assert ids==("7805",) and rows==[{"id":"7805","label":"Livingroom Light 1"}]
    assert method=="question"
    ids2,_,_=resolve_verified_device_subjects(
        "Check bedroom-3 mesh signal",LIVE)
    assert ids2==("7103",)


def test_overlapping_name_prefers_full_phrase_and_multiple_distinct_targets():
    devices=LIVE + [{"id":"8001","label":"Livingroom Light","name":"Livingroom Light"}]
    ids,_,_=resolve_verified_device_subjects("Why did Livingroom Light 1 stay on?",devices)
    assert ids==("7805",)
    ids,_,_=resolve_verified_device_subjects(
        "Compare Livingroom Light 1 and Bedroom 3 Mesh",devices)
    assert ids==("7805","7103")


def test_ambiguous_names_and_no_identity_fail_closed():
    duplicated=LIVE+[{"id":"9999","label":"Livingroom Light 1"}]
    for devices,question in ((duplicated,"Why was Livingroom Light 1 on?"),
                             (LIVE,"Why was Unknown light 1 on?")):
        with pytest.raises(ValueError):
            resolve_verified_device_subjects(question,devices)
    with pytest.raises(ValueError,match="uniquely"):
        resolve_verified_device_subjects("Why?",duplicated,device_name="Livingroom Light 1")
    with pytest.raises(ValueError):
        resolve_verified_device_subjects("Why?",LIVE,device_ids=["9999"])


def test_advanced_name_and_unlabeled_numeric_id_remain_supported():
    ids,_,source=resolve_verified_device_subjects("Why?",LIVE,device_name="livingroom light 1")
    assert ids==("7805",) and source=="device_name"
    ids,_,source=resolve_verified_device_subjects(
        "Why?",LIVE+[{"id":54321}],device_ids=["54321"])
    assert ids==("54321",) and source=="manual_id"


def source(data):
    return MCPToolResult(
        name="hub_read_devices",arguments={},raw={},text="PRIVATE_TOKEN",
        data={"deviceId":"7805","events":data},is_error=False)


def event(name,date,producer):
    return {"name":name,"type":"command","date":date,
            "deviceId":"7805","producedBy":producer}


def parsed(events):
    return project_read_receipt(
        "hub_read_devices",
        {"tool":"hub_list_device_events","args":{"deviceId":"7805"}},
        source(events),source_request_id="v2-provenance",incident_window=window())


def test_html_link_command_sources_are_restored_without_html_label_or_credentials():
    events=[
        event("command-off","2026-10-25T00:41:40+0100",
              "<a href='/installedapp/configure/4246'>Night Idle - PRIVATE_TOKEN</a>"),
        event("command-setLevel","2026-10-25T00:49:52+0100",
              '<a href="/installedapp/configure/4019">LMC</a>'),
        event("command-off","2026-10-25T01:09:41+0100",
              {"appId":"1251","name":"PRIVATE_TOKEN"}),
    ]
    projected=parsed(events)
    assert [row["producedBy"]["id"] for row in projected["details"]["events"]]==[
        "4246","4019","1251"]
    assert "PRIVATE_TOKEN" not in json.dumps(projected)
    assert "<a" not in json.dumps(projected)
    case=build_case_file("Why was this on?",[projected])
    assert [e.producer_id for e in case.records]==["4246","4019","1251"]
    summary=format_investigation_report(case,[],"planning_timeout",window())
    assert "Possible competing controllers" in summary
    assert "#4246" in summary and "#4019" in summary
    assert "commonly turns it ON" in summary
    assert "does not prove" in summary
    assert "Another OFF was issued" in summary


@pytest.mark.parametrize("producer",[
  "<a href='https://evil.example/installedapp/configure/4246'>fake</a>",
  {"id":"4019","appId":"4246","type":"app"},
  {"id":"4019","type":"injected"},
  "<img src='/installedapp/configure/4246'>",
  {"label":"Fake app","id":None},
])
def test_untrusted_and_conflicting_producer_identity_never_asserted(producer):
    projected=parsed([event("command-off","2026-10-25T00:41:40+0100",producer)])
    assert "producedBy" not in projected["details"]["events"][0]


def test_report_compacts_missing_sources_and_marks_dst_shift_and_connectivity_recovery():
    rows=[
      event("command-off","2026-10-25T00:41:40+0100",None),
      event("command-setLevel","2026-10-25T00:49:52+0100",None),
      event("command-off","2026-10-25T01:09:41+0100",None),
      {"name":"networkStatus","value":"offline","date":"2026-10-25T00:20:16+0100"},
      {"name":"networkStatus","value":"online","date":"2026-10-25T00:23:09+0100"},
      {"name":"level","value":"30","date":"2026-10-25T03:40:05+0000"},
    ]
    c=build_case_file("Why?",[parsed(rows)])
    report=format_investigation_report(c,[],"planning_timeout",window())
    assert "| Local time | Observation |" in report
    assert "| Local time | Observation | Source |" not in report
    assert "Source note" in report
    assert "clocks went back from BST to GMT" in report
    assert "commonly turns it ON" in report
    assert "followed by an online report" in report
    assert "does not prove that a later command failed" in report
    assert "planning timeout" in report


"""Native V2 source call-path evidence is structural, read-only and private."""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_method_paths import static_method_paths
from investigation_v2.native_source_readiness import source_read_summary


SOURCE = """
def runQ() {
    // setVolume() here must not count as a call
    def speech = "speak() SECRET_VALUE https://private.invalid/path"
    refresh()
    httpGet("https://private.invalid/path") { resp -> }
}
def refresh() {
    sendEvent(name: "status", value: "idle")
}
def setVolume(level) {
    runQ()
}
"""


def payload(source=SOURCE, **overrides):
    return {
        "result": {
            "status": "success",
            "appId": "1679",
            "source": source,
            "offset": 0,
            "totalLength": len(source),
            **overrides,
        }
    }


def test_complete_typed_source_projects_bounded_static_call_paths():
    evidence = source_read_summary(
        payload(), requested_type="app", requested_id="1679",
        focus_methods=["runQ", "setVolume"],
    )
    assert evidence["source_complete"] is True
    assert evidence["source_read_usable_for_method_reasoning"] is True
    graph = evidence["static_method_paths"]
    assert graph["runtime_execution_verified"] is False
    assert graph["network_or_cpu_cause_verified"] is False
    assert graph["status"] == "lexical_methods_indexed"
    methods = {x["method"]: x for x in graph["method_paths"]}
    assert methods["runQ"]["body_boundary_verified"] is True
    assert methods["runQ"]["declared_method_calls"] == ["refresh"]
    assert "httpGet" in methods["runQ"]["platform_api_mentions"]
    assert "runQ" in methods["setVolume"]["declared_method_calls"]
    assert "sendEvent" in methods["refresh"]["platform_api_mentions"]
    report = json.dumps(evidence)
    assert "SECRET_VALUE" not in report
    assert "private.invalid" not in report
    assert "resp ->" not in report
    assert "speech" not in report


def test_app_id_does_not_authorise_driver_identity_even_when_number_equal():
    evidence = source_read_summary(
        payload(), requested_type="driver", requested_id="1679",
    )
    assert evidence["source_complete"] is False
    assert evidence["source_read_usable_for_method_reasoning"] is False
    assert "static_method_paths" not in evidence
    assert evidence["source_read_status"] == "source_fragment_or_identity_unverified"


def test_missing_source_is_not_inspected_despite_gateway_success():
    evidence = source_read_summary(
        {"status": "success", "appId": "1679"},
        requested_type="app", requested_id="1679",
    )
    assert evidence["source_content_available"] is False
    assert evidence["source_complete"] is False
    assert "static_method_paths" not in evidence


def test_request_requires_returned_id_not_just_a_success_status():
    evidence = source_read_summary(
        {"source": SOURCE, "totalLength": len(SOURCE), "offset": 0,
         "status": "success"},
        requested_type="app", requested_id="1679",
    )
    assert evidence["source_complete"] is False


def test_wrong_length_prevents_all_method_claims():
    evidence = source_read_summary(
        payload(totalLength=len(SOURCE) + 5),
        requested_type="app", requested_id="1679",
    )
    assert evidence["source_complete"] is False
    assert "static_method_paths" not in evidence


def test_unbalanced_method_never_exposes_causal_call_edges():
    code = "def runQ() {\n  refresh()\n" + "a" * 55
    result = static_method_paths(code)
    row = result["method_paths"][0]
    assert row["body_boundary_verified"] is False
    assert "declared_method_calls" not in row
    assert "platform_api_mentions" not in row


def test_unknown_focus_name_does_not_prove_absence():
    result = static_method_paths(SOURCE, focus_methods=["unknownCallback"])
    assert result["focused_method_names_not_recognized"] == ["unknownCallback"]
    assert "not resolved" in result["limits"]


def test_no_api_marker_from_comment_or_literal():
    src = """
def first() {
    // httpPost("payload")
    def s = "runIn(20) and sendHubCommand()"
    second()
}
def second() { }
"""
    result = static_method_paths(src)
    first = next(x for x in result["method_paths"] if x["method"] == "first")
    assert first["declared_method_calls"] == ["second"]
    assert first["platform_api_mentions"] == []

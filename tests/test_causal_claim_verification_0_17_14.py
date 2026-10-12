"""Source-scoped causal claim verification (no per-room or per-brand patches).

The live physical-event investigation correctly found a +51ms app-owned level
command but accidentally attributed it to a telemetry listener; it also used
an empty app log to declare that no logic ran and collapsed sensor events on
opposite sides of OFF into a single "before" event.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from causal_claim_verification import (  # noqa: E402
    guard_causal_action_ownership,
    guard_causal_empty_log_inference,
    guard_causal_sensor_event_order,
    verify_causal_claims,
)
from causal_evidence_graph import build_causal_evidence_graph  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402
from test_causal_physical_event_0_17_12 import _physical_evidence, QUESTION  # noqa: E402
from test_causal_evidence_graph_0_17_11 import _receipts, QUESTION as MOTION_QUESTION  # noqa: E402


def _evidence():
    rows = copy.deepcopy(_physical_evidence())
    # Use generic stand-in labels and IDs. The verifier must learn ownership
    # from these native receipts, not from a fixed list of automation names.
    triggered = rows[0]["details"]["boundaryEvents"][0]["triggered"]
    triggered[0]["name"] = "Example Lighting Mode Controller"
    triggered[1]["name"] = "Example Telemetry Reporter"
    rows[1]["details"]["requestedBoundary"] = (
        "2026-10-12T08:16:10.861+0100"
    )
    rows[1]["details"]["sensors"].append({
        "label": "Example Soft Sensor", "attribute": "motion",
        "relevantCorrelations": [],
        "oppositeCorrelations": [{
            "boundaryRole": "end",
            "subjectTransition": "2026-10-12T08:18:23.830+0100",
            "sensorEvent": "2026-10-12T08:18:24.779+0100",
            "signedDeltaSeconds": 0.949,
            "eventValue": "inactive",
            "attribute": "motion",
            "producedBy": {
                "type": "device", "label": "Example Matter Bridge", "id": "7718",
            },
        }],
    })
    return rows


WRONG_DRAFT = (
    "The most likely initiator was Example Hue dimmer 1.\n"
    "### 2. Automation Role\n"
    "For this physical state event, Example Telemetry Reporter is recorded "
    "as a downstream listener in triggered[]. It acted as a downstream handler:\n"
    "* The app was notified of the manual turn-on and immediately reacted "
    "by setting the brightness to 45%.\n"
    '* This is consistent with its configuration to "react to manual turn-on".\n'
    "* Execution logs for the app in this window were empty, confirming "
    "that no internal rule logic initiated the turn-on.\n"
    "### 4. Turn-Off Event\n"
    "The light turned off after 133 seconds. This is temporally consistent "
    "with Example FP300 and Example Soft Sensor reporting inactive motion "
    "at 08:18:23 (approx. 210ms before the OFF event). "
    "While the OFF source remains unknown, there is close timing correlation.\n"
)


def test_graph_preserves_listener_identity_independent_of_verified_action_owner():
    graph = build_causal_evidence_graph(_evidence(), QUESTION)
    assert graph["scope"] == "single-observed-event"
    listeners = graph["physicalStateBoundary"]["listenersNotified"]
    assert listeners[0]["appId"] == "4015"
    assert listeners[1]["appId"] == "4129"
    assert listeners[1]["label"] == "Example Telemetry Reporter"
    command = graph["postOnCommands"][0]
    assert command["producer"]["id"] == "4015"
    assert command["afterOnMs"] == 51.0
    assert graph["offAttribution"] == "unresolved-no-proven-off-command"
    orders = {
        row["sensor"]: row["signedDeltaMs"]
        for row in graph["offSensorCorrelations"]
    }
    assert orders["Example FP300"] == -210.0
    assert orders["Example Soft Sensor"] == 949.0


def test_verifier_repairs_live_semantic_contradictions_with_source_provenance():
    fixed, issues = verify_causal_claims(WRONG_DRAFT, _evidence(), QUESTION)
    assert issues == [
        "causal_action_ownership", "causal_empty_log_inference",
        "causal_sensor_event_order",
    ], (issues, fixed)
    assert "Example Lighting Mode Controller (app 4015) issued setLevel(45) 51 ms after ON" in fixed
    assert "Example Telemetry Reporter was notified" in fixed
    assert "the brightness to 45%" not in fixed
    assert "configuration belongs to Example Lighting Mode Controller" in fixed
    assert "confirming that no internal rule logic initiated" not in fixed
    assert "does not establish whether internal rule logic executed" in fixed
    assert "Example FP300 reported inactive 210 ms before OFF" in fixed
    assert "Example Soft Sensor reported inactive 949 ms after OFF" in fixed
    assert "OFF command" in fixed
    assert "The most likely initiator was Example Hue dimmer 1." in fixed
    assert "The light turned off after 133 seconds." in fixed


def test_order_guard_corrects_only_inverted_timing_not_already_correct_analysis():
    rows = _evidence()
    good = (
        "Example FP300 was inactive 210ms before OFF, while Example Soft "
        "Sensor was inactive 949ms after OFF; neither proves who switched it off."
    )
    unchanged, changed = guard_causal_sensor_event_order(good, rows, QUESTION)
    assert not changed
    assert unchanged == good
    bad = "Example Soft Sensor reported inactive 949ms before the OFF event."
    corrected, changed = guard_causal_sensor_event_order(bad, rows, QUESTION)
    assert changed
    assert "949 ms after OFF" in corrected


def test_logs_only_prove_bounded_empty_observation_not_no_execution():
    rows = _evidence()
    legitimate = (
        "The targeted app log window returned no entries, so the rule's "
        "internal decision cannot be reconstructed from it."
    )
    result, changed = guard_causal_empty_log_inference(legitimate, rows, QUESTION)
    assert result == legitimate and not changed
    unsafe = (
        "The app's execution logs returned zero entries, proving that "
        "no automation execution occurred."
    )
    result, changed = guard_causal_empty_log_inference(unsafe, rows, QUESTION)
    assert changed
    assert "proving that" not in result
    assert "does not establish whether internal rule logic executed" in result
    without_log = [
        row for row in rows
        if row.get("sub_tool") != "hub_get_logs"
    ]
    result, changed = guard_causal_empty_log_inference(unsafe, without_log, QUESTION)
    assert not changed and result == unsafe


def test_action_ownership_fails_closed_without_exact_single_app_command():
    rows = _evidence()
    for receipt in rows:
        if receipt.get("sub_tool") == "hub_list_device_events" and (
            (receipt.get("arguments") or {}).get("args") or {}
        ).get("attribute") == "command-setLevel":
            receipt["details"]["events"] = []
    text = "Example Telemetry Reporter set the brightness to 45%."
    fixed, changed = guard_causal_action_ownership(text, rows, QUESTION)
    assert fixed == text and not changed
    rows = _evidence()
    for receipt in rows:
        if receipt.get("sub_tool") == "hub_list_device_events" and (
            (receipt.get("arguments") or {}).get("args") or {}
        ).get("attribute") == "command-setLevel":
            receipt["details"]["events"].append({
                "name": "command-setLevel",
                "date": "2026-10-12T08:16:11.012+0100",
                "description": "Command called: setLevel(45)",
                "producedBy": {"id": "9999", "type": "app", "label": "Other Controller"},
            })
    fixed, changed = guard_causal_action_ownership(text, rows, QUESTION)
    assert fixed == text and not changed


def test_synthesis_and_final_api_share_same_source_bound_invariants():
    rows = _evidence()
    fixed, issues = validate_synthesis(
        WRONG_DRAFT, rows, original_user=QUESTION, causal=True,
    )
    assert "causal_action_ownership" in issues
    assert "causal_empty_log_inference" in issues
    assert "causal_sensor_event_order" in issues
    assert "Example Lighting Mode Controller (app 4015) issued setLevel(45)" in fixed

    outcome = SimpleNamespace(
        message=WRONG_DRAFT,
        evidence=rows,
        metrics={"outcome": "success", "counters": {"model_rounds": 1}},
        route="unified-mcp-agent",
        request_class="live-read",
    )
    response = build_agent_response(
        outcome, model="model", elapsed_ms=12300, version="0.17.14",
    )
    assert "Example Lighting Mode Controller (app 4015) issued setLevel(45)" in response["message"]
    assert "Example Soft Sensor reported inactive 949 ms after OFF" in response["message"]
    assert "confirming that no internal rule logic initiated" not in response["message"]


def test_confirmed_bathroom_motion_app_command_does_not_trigger_physical_rewrite():
    rows = _receipts()
    good = (
        "The Example Controller app issued setLevel(50) before switch=on. "
        "A configured occupancy sensor reported active shortly before it. "
        "The app logs returned zero entries; the internal decision is unverified."
    )
    fixed, issues = verify_causal_claims(good, rows, MOTION_QUESTION)
    assert not issues
    assert fixed == good


def test_no_focal_event_does_not_invent_claim_provenance():
    rows = _evidence()
    unresolved = "Why did Example Room Light turn on?"
    fixed, issues = verify_causal_claims(WRONG_DRAFT, rows, unresolved)
    assert not issues and fixed == WRONG_DRAFT

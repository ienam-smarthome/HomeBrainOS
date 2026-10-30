"""Release 0.18.241: actual Bathroom incident replay in ORIGINAL HomeBrain agent.

Source receipts mirror the 30 October user trace. This suite checks causal
order, independent sensor evidence, no auto-authorised IDs, source limits and
the real natural-language final answer coordinator boundary.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from unified_investigation_bridge import (
    collect_unified_evidence, unified_investigation_instruction,
    unified_investigation_followup,
)
from final_answer_coordinator import FinalAnswerCoordinator

QUESTION = (
    "Investigate why Bathroom Light 1, Bathroom Light 2 and Shower Light "
    "turned ON and OFF between 02:00 and 07:30 on 30 October 2026. "
    "Check occupancy, buttons, mode and possible external triggers. "
    "Read-only; do not change anything."
)
IDS = (("7818", "Bathroom Light 1"), ("7821", "Bathroom Light 2"),
       ("7807", "Shower Light"))


def reported(name, when, value, producer="7790"):
    return {"name": name, "date": "2026-10-30T" + when + "+0000",
            "value": value, "producedBy": {
                "deviceId": int(producer), "name": "Matter Hue Bridge Pro"}}


def command(name, when, app, label):
    return {"name": "command-" + name,
            "date": "2026-10-30T" + when + "+0000",
            "producedBy": {"appId": int(app), "name": label}}


def read_device(ident, events):
    return {"tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events",
            "success": True, "mutates": False, "effect": "read",
            "supports_live_claim": True,
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": ident,
                                   "since": "2026-10-30T02:00:00Z",
                                   "until": "2026-10-30T07:30:00Z"}},
            "details": {"observedEvents": events, "observedEventsTruncated": False}}


def lookup(ident, label):
    return {"tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False, "effect": "read",
            "supports_live_claim": True,
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": label}},
            "details": {"reportedDeviceState": {
                "deviceId": ident, "label": label, "reportedAttributes": {
                    "switch": "off"}}}}


def bathroom(*, sensors=True):
    receipts = [lookup(i, label) for i, label in IDS]
    receipts.extend([
        read_device("7818", [
            reported("switch", "03:40:21.668", "on"),
            command("off", "03:46:05.251", "1569", "button 4 pushed"),
            reported("switch", "03:46:05.928", "off"),
            reported("switch", "07:12:33.514", "on"),
            command("setLevel", "07:12:33.560", "4013", "Bathroom"),
            reported("level", "07:12:34.528", "30"),
            command("setLevel", "07:15:02.678", "4013", "Bathroom"),
            reported("level", "07:15:03.071", "50"),
        ]),
        read_device("7821", [
            reported("switch", "03:40:22.678", "on"),
            command("off", "03:46:05.313", "1569", "button 4 pushed"),
            reported("switch", "03:46:06.059", "off"),
            reported("switch", "07:12:34.589", "on"),
            command("setLevel", "07:12:34.622", "4013", "Bathroom"),
            reported("level", "07:12:35.546", "30"),
        ]),
        read_device("7807", [
            reported("switch", "02:13:30.399", "on"),
            command("setLevel", "02:13:30.481", "4014", "Shower"),
            reported("level", "02:13:31.416", "40"),
            reported("switch", "02:15:13.073", "off"),
            reported("switch", "03:03:31.727", "on"),
            command("off", "03:04:17.010", "1568", "button 3 pushed"),
            reported("switch", "03:04:17.212", "off"),
            reported("switch", "07:27:48.079", "on"),
            command("setLevel", "07:27:48.148", "4014", "Shower"),
            reported("level", "07:27:49.070", "70"),
        ]),
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "mutates": False, "effect": "read",
         "supports_live_claim": True,
         "arguments": {"tool": "hub_list_device_events", "args": {}},
         "details": {"observedEvents": [
             {"name": "mode", "date": "2026-10-30T07:15:01.259+0000",
              "value": "School Run"},
             {"name": "mode", "date": "2026-10-30T08:30:01.537+0000",
              "value": "Morning"},
         ]}},
    ])
    if sensors:
        receipts.extend([
            read_device("7895", [
                reported("occupancy", "03:40:21.513", "active", "7895"),
                reported("occupancy", "07:12:33.262", "active", "7895"),
            ]),
            read_device("7908", [
                reported("motion", "02:13:30.639", "active", "7908"),
                reported("motion", "07:27:47.990", "active", "7908"),
            ]),
        ])
    return receipts


def test_source_order_prevents_brightness_being_mislabeled_activation():
    evidence = collect_unified_evidence(bathroom(), QUESTION)
    assert evidence is not None
    assert evidence["target_device_ids"] == ["7807", "7818", "7821"]
    assert evidence["source_attested"] is True
    turn_on = next(e for e in evidence["transition_relationships"]
                   if e["device_id"] == "7818" and e["reported_state"] == "on"
                   and "T07:12:" in e["time"])
    assert turn_on["preceding_hubitat_command_in_sample"] == []
    assert turn_on["subsequent_level_commands"][0]["app_id"] == "4013"
    assert turn_on["subsequent_level_commands"][0]["lag_ms"] == 46
    assert turn_on["preceding_input_correlations"][0]["lead_ms"] == 252
    assert turn_on["preceding_input_correlations"][0]["device_id"] == "7895"
    off = next(e for e in evidence["transition_relationships"]
               if e["device_id"] == "7821" and e["reported_state"] == "off"
               and "T03:46:" in e["time"])
    assert off["preceding_hubitat_command_in_sample"][0]["app_id"] == "1569"
    assert off["preceding_hubitat_command_in_sample"][0]["lead_ms"] == 746
    assert evidence["hub_mode_observations"][0]["value"] == "School Run"
    assert not any(e["value"] == "Morning" for e in evidence["hub_mode_observations"])


def test_sensor_after_on_is_not_reversed_into_proven_cause():
    evidence = collect_unified_evidence(bathroom(), QUESTION)
    shower = next(e for e in evidence["transition_relationships"]
                  if e["device_id"] == "7807" and "T02:13:" in e["time"])
    assert shower["preceding_input_correlations"] == []
    assert shower["subsequent_level_commands"][0]["app_id"] == "4014"
    later = next(e for e in evidence["transition_relationships"]
                 if e["device_id"] == "7807" and "T07:27:" in e["time"])
    assert later["preceding_input_correlations"][0]["lead_ms"] == 89
    assert later["subsequent_level_commands"][0]["lag_ms"] == 69
    assert "correlation only" in evidence["limitations"]


def test_source_coverage_checks_are_not_historical_trigger_proof():
    receipts = bathroom(sensors=False)
    receipts.append({
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True, "mutates": False, "effect": "read",
        "arguments": {"tool": "hub_get_logs",
                      "args": {"mode": "past", "limit": 100}},
        "details": {"observedLogRows": [{"date": "2026-10-30T10:00:40Z"}]},
    })
    result = collect_unified_evidence(receipts, QUESTION)
    assert result["missing_independent_input_history"] is True
    assert result["log_query_count"] == 1
    assert result["incident_log_coverage_verified"] is False
    assert "10:00" not in str(result["transition_relationships"])
    followup = unified_investigation_followup(receipts, QUESTION)
    assert followup is not None
    assert "independent input" in followup
    assert "Choose a live-advertised read" in followup
    assert "No writes" not in followup  # reads are model selected


def test_unverified_or_unrelated_reads_do_not_create_source_authority():
    receipts = bathroom(sensors=False)
    receipts = [r for r in receipts if r.get("sub_tool") != "hub_list_devices"]
    assert collect_unified_evidence(receipts, QUESTION) is None
    receipts = bathroom(sensors=False)
    for item in receipts:
        if item.get("sub_tool") == "hub_list_device_events":
            item["supports_live_claim"] = False
    assert collect_unified_evidence(receipts, QUESTION) is None


@pytest.mark.asyncio
async def test_original_final_answer_receives_verified_context_without_v2_json():
    seen = []

    async def chat(messages, tools):
        seen.append((messages, tools))
        return {"role": "assistant", "content": (
            "The strongest observation is that the bathroom occupancy event "
            "preceded two reported ON transitions; Hubitat's brightness "
            "commands followed those state reports. Button 4 commands "
            "preceded the OFF reports. The activating external controller "
            "is not independently verified."
        )}

    coordinator = FinalAnswerCoordinator(
        chat, evidence_supplier=lambda: bathroom(),
    )
    await coordinator.answer([{"role": "user", "content": QUESTION}])
    assert len(seen) >= 1
    messages, tools = seen[0]
    assert tools == []
    source_messages = [
        m["content"] for m in messages
        if m["role"] == "user" and
        "HOST ORIGINAL-HOMEBRAIN INVESTIGATION EVIDENCE" in m["content"]
    ]
    assert len(source_messages) == 1
    text = source_messages[0]
    assert "transition_relationships" in text
    assert "subsequent_level_commands" in text
    assert "preceding_input_correlations" in text
    assert "Answer WHY first" in text
    assert "not a V2 JSON answer" in text
    assert "incident_log_coverage_verified" in text

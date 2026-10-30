"""Original unified-agent evidence intake and follow-up regression checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from unified_investigation_bridge import collect_unified_evidence, unified_investigation_followup

QUESTION = "Investigate Zone Alpha Light and Zone Beta Light on 30 October 2026 between 14:50 and 15:30 GMT"

def _lookup(device_id, label):
    return {"success": True, "mutates": False, "effect": "read",
            "sub_tool": "hub_list_devices", "evidence_kind": "targeted_device_lookup",
            "details": {"reportedDeviceState": {"deviceId": str(device_id), "label": label}}}

def _history(label, name="switch", value="on", timestamp="2026-10-30T14:50:37.871+00:00"):
    return {"success": True, "mutates": False, "effect": "read",
            "tool": "homebrain_device_history", "supports_live_claim": True,
            "details": {"label": label, "observedEvents": [
                {"name": name, "value": value, "date": timestamp,
                 "producedBy": {"deviceId": "900", "name": "Matter Bridge"}}]}}

def _base():
    return [_lookup(101, "Zone Alpha Light"), _lookup(102, "Zone Beta Light"),
            _history("Zone Alpha Light"), _history("Zone Beta Light", timestamp="2026-10-30T14:50:38.901+00:00")]

def test_deterministic_history_used_when_native_gateway_receipt_has_only_summary():
    receipts = _base()
    receipts.append({"success": True, "mutates": False, "effect": "read",
                     "sub_tool": "hub_list_device_events",
                     "arguments": {"tool": "hub_list_device_events", "args": {"deviceId": "101"}},
                     "summary": "1 switch event (details not projected)"})
    facts = collect_unified_evidence(receipts, QUESTION)
    assert facts is not None
    assert facts["transition_count"] == 2
    assert facts["target_device_ids"] == ["101", "102"]
    assert facts["missing_independent_input_history"] is True
    prompt = unified_investigation_followup(receipts, QUESTION)
    assert prompt and "independent input" in prompt

def test_sensor_discovered_after_question_is_consumed_and_next_step_is_controller():
    receipts = _base() + [_lookup(201, "Occupancy Sensor"),
            _history("Occupancy Sensor", name="motion", value="active",
                     timestamp="2026-10-30T14:50:37.550+00:00")]
    facts = collect_unified_evidence(receipts, QUESTION)
    assert facts is not None
    assert facts["independently_read_input_ids"] == ["201"]
    assert facts["missing_independent_input_history"] is False
    assert facts["transition_relationships"][0]["preceding_input_correlations"]
    prompt = unified_investigation_followup(receipts, QUESTION)
    assert prompt and "CAUSAL CHAIN INCOMPLETE" in prompt
    assert "proof of external control" in prompt

def test_deduplicate_gateway_and_derived_copy_of_same_state():
    receipts = _base()
    same_event = receipts[2]["details"]["observedEvents"][0]
    receipts.append({"success": True, "mutates": False, "effect": "read",
                     "sub_tool": "hub_list_device_events",
                     "supports_live_claim": True,
                     "arguments": {"tool": "hub_list_device_events", "args": {"deviceId": "101"}},
                     "details": {"observedEvents": [same_event]}})
    facts = collect_unified_evidence(receipts, QUESTION)
    assert facts is not None
    assert facts["transition_count"] == 2

def test_unknown_or_ambiguous_history_label_never_gains_device_identity():
    receipts = _base()
    receipts.append(_history("Another Sensor", name="motion"))
    receipts.append(_lookup(201, "Ambiguous Sensor"))
    receipts.append(_lookup(202, "Ambiguous Sensor"))
    receipts.append(_history("Ambiguous Sensor", name="motion"))
    facts = collect_unified_evidence(receipts, QUESTION)
    assert facts is not None
    assert facts["independently_read_input_ids"] == []

def test_failed_or_mutating_history_not_admitted():
    receipts = [_lookup(101, "Zone Alpha Light"), _lookup(102, "Zone Beta Light"),
                _history("Zone Alpha Light"), _history("Zone Beta Light")]
    receipts[2]["success"] = False
    receipts[3]["mutates"] = True
    assert collect_unified_evidence(receipts, QUESTION) is None

def test_no_external_initiator_deduced_from_missing_bounded_command():
    facts = collect_unified_evidence(_base(), QUESTION)
    assert facts is not None
    assert "No returned command is not proof none" in facts["limitations"]
    assert facts["transition_relationships"][0]["preceding_hubitat_command_in_sample"] == []

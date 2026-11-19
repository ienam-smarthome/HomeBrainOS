"""Generic source-role and app-identity evidence regressions, all fictional."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from claim_receipt_contract import build_claim_receipt_contract
from investigation_review import (
    is_app_execution_question, review_kind, review_prompt,
)


def receipt(tool, args, native):
    return {"name": tool, "arguments": args, "success": True,
            "response": json.dumps({"content": [
                {"type": "text", "text": json.dumps(native)},
            ]})}


class TypedProvenanceTests(unittest.TestCase):
    def test_device_last_activity_is_separate_from_stored_energy_and_dated_event(self):
        current = receipt("hub_list_devices", {"labelFilter": "Fixture Freezer"}, {
            "count": 1, "total": 1,
            "devices": [{
                "id": 7105, "label": "Fixture Freezer",
                "lastActivity": "2030-11-19T12:02:54+0000",
                "currentStates": {"energy": 42.502, "switch": "on"},
            }],
        })
        history = receipt(
            "hub_list_device_events", {"deviceId": 7105, "attribute": "energy"},
            {"source": "device", "deviceId": 7105, "events": [
                {"name": "energy", "value": 42.502,
                 "date": "2030-11-19T11:57:34.721+0000"},
            ]},
        )
        packets = build_claim_receipt_contract("compare energy", "answer",
                                               [current, history])["typed_receipts"]
        snapshot = [f for f in packets[0]["facts"]
                    if f["fact_type"] == "reported_current_state"]
        activity = [f for f in packets[0]["facts"]
                    if f["fact_type"] == "reported_device_activity_marker"]
        dated = packets[1]["facts"][0]
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0]["source_timestamp"],
                         "2030-11-19T12:02:54+0000")
        self.assertFalse(activity[0]["attribute_specific_event_timestamp_proven"])
        self.assertFalse(snapshot[0]["attribute_specific_event_timestamp_proven"])
        self.assertEqual(dated["source_role"], "native_device_reported_attribute_event")
        self.assertEqual(dated["source_timestamp"],
                         "2030-11-19T11:57:34.721+0000")
        self.assertFalse(dated["independent_physical_actuation_proven"])

    def test_command_issuer_and_notified_listener_are_not_app_history_or_actor(self):
        history = receipt("hub_list_device_events", {
            "deviceId": 7850, "hoursBack": 4,
        }, {"source": "device", "deviceId": 7850, "events": [
            {"name": "command-off", "type": "command",
             "date": "2030-11-19T08:21:35.089+0000",
             "producedBy": {"appId": 3995}},
            {"name": "switch", "value": "off", "type": "physical",
             "date": "2030-11-19T08:21:35.440+0000",
             "producedBy": {"deviceId": 7842},
             "triggered": [{"appId": 3995}, {"appId": 4209}]},
        ]})
        facts = build_claim_receipt_contract("what happened", "answer",
                                             [history])["typed_receipts"][0]["facts"]
        self.assertEqual(facts[0]["source_role"], "native_device_command_row")
        self.assertEqual(facts[0]["recorded_issuer_app_id"], "3995")
        self.assertFalse(facts[0]["app_self_reported_history_proven"])
        self.assertEqual(facts[1]["reporter_device_id"], "7842")
        self.assertEqual(facts[1]["notified_listener_app_ids"], ["3995", "4209"])
        self.assertFalse(facts[1]["notified_listener_is_command_issuer_proven"])

    def test_app_config_and_app_inventory_never_become_device_event_rows(self):
        app_list = receipt("hub_list_apps", {}, {
            "apps": [{"id": 3995, "name": "Fixture Humidity App"}],
        })
        app_config = receipt("hub_get_app_config", {"appId": 3995}, {
            "appId": 3995, "events": [{
                "name": "command-off", "type": "command",
                "date": "2030-11-19T08:21:35+0000",
            }],
        })
        packets = build_claim_receipt_contract(
            "check app execution", "answer", [app_list, app_config],
        )["typed_receipts"]
        self.assertEqual(packets[0]["facts"][0]["fact_type"],
                         "reported_installed_app_identity")
        self.assertEqual(packets[1]["facts"][0]["fact_type"],
                         "reported_app_configuration")
        self.assertFalse(packets[1]["facts"][0]["historical_app_execution_proven"])
        self.assertFalse(any(x["fact_type"] == "recorded_command"
                             for p in packets for x in p["facts"]))


class AppReviewEligibilityTests(unittest.TestCase):
    def test_app_execution_gets_app_identity_source_review(self):
        question = (
            "For Fixture Ventilation Controller, identify the newest dated "
            "evidence of execution or decision for the app. "
            "Distinguish app history from device commands. Do not change anything."
        )
        self.assertTrue(is_app_execution_question(question))
        self.assertEqual(review_kind(question), "app_execution")
        prompt = review_prompt("app_execution")
        self.assertIn("APP and a native DEVICE", prompt)
        self.assertIn("exact", prompt)
        self.assertIn("Do not change anything", prompt)
        self.assertIsNone(review_kind(
            "Turn on the Fixture Fan Boost, please."
        ))
        self.assertFalse(is_app_execution_question(
            "Which device has the latest switch event?"
        ))


if __name__ == "__main__":
    unittest.main()

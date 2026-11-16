"""V2 alpha.128: a state-event app producer is not a recorded command.

Fictional cross-domain source rows only; no real device or app IDs.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_decision_frontier import causal_controller_frontier
from causal_claim_publication import causal_publication_floor
from investigation_review import should_prompt_controller_decision_gap


def native(name, args, payload, *, success=True):
    return {
        "name": name, "arguments": args,
        "success": success, "result_kind": "tool_result",
        "response": json.dumps({"content": [{
            "type": "text", "text": json.dumps(payload)
        }]}),
    }


report = native(
    "hub_list_device_events",
    {"deviceId": "FX-RELAY", "attribute": "switch", "hoursBack": 4},
    {"source": "device", "deviceId": "FX-RELAY",
     "attributeFilter": "switch", "events": [{
         "name": "switch", "value": "on", "type": "digital",
         "date": "2030-09-01T08:00:00Z",
         "producedBy": {"name": "Fixture Controller", "appId": 731},
         "triggered": [{"name": "Fixture Listener", "appId": 732}],
     }]},
)
runtime = native(
    "hub_get_logs",
    {"mode": "past", "appId": 731,
     "since": "2030-09-01T07:59:00Z", "until": "2030-09-01T08:01:00Z"},
    {"mode": "past", "entries": [{
        "timestamp": "2030-09-01T08:00:00Z",
        "message": "Fixture trigger evaluated"
    }]},
)
emitted = native(
    "hub_list_device_events",
    {"appId": 731, "since": "2030-09-01T00:00:00Z"},
    {"source": "app", "appId": 731, "events": []},
)


class AppProducerFrontierTests(unittest.TestCase):
    def test_reporter_source_only_is_an_unverified_controller_lead(self):
        f = causal_controller_frontier([report])
        self.assertEqual(f["original_device_command_rows_indexed"], 0)
        self.assertEqual(f["recorded_issuer_app_ids"], [])
        self.assertEqual(f["noncommand_state_producer_app_ids"], ["731"])
        self.assertEqual(f["recent_app_produced_state_rows"][0]["reported_field"],
                         "switch")
        self.assertTrue(f["producer_app_is_not_a_command_issuer"])
        self.assertTrue(f["controller_decision_source_unchecked_for_model_review"])
        self.assertTrue(should_prompt_controller_decision_gap(
            "Why did the fixture relay turn on?",
            review_kind_name="causal", source_frontier=f))

    def test_app_emitted_event_query_is_not_a_runtime_log(self):
        f = causal_controller_frontier([report, emitted])
        self.assertEqual(f["app_logs_attempted_for_state_producers"], 0)
        self.assertTrue(f["controller_decision_source_unchecked_for_model_review"])
        score = causal_publication_floor(
            "Why did output activate?",
            "The output turned on because its controller decided to activate.",
            [report, emitted])
        self.assertEqual(score["reason"], "controller_decision_unverified")

    def test_scoped_native_runtime_log_is_different_source_category(self):
        f = causal_controller_frontier([report, runtime])
        self.assertEqual(f["app_logs_attempted_for_state_producers"], 1)
        self.assertEqual(f["app_logs_successes_for_state_producers"], 1)
        self.assertFalse(f["controller_decision_source_unchecked_for_model_review"])
        # The guard only verifies a necessary SOURCE TYPE floor; it does not
        # independently judge whether the fictional log really proved why.
        self.assertEqual(causal_publication_floor(
            "Why did output turn on?",
            "The output turned on because the controller evaluated its trigger.",
            [report, runtime])["status"], "passed")

    def test_other_app_log_does_not_close_issuer_frontier(self):
        wrong = native("hub_get_logs", {"mode": "past", "appId": 732},
                       {"mode": "past", "entries": [{"message": "Other app"}]})
        f = causal_controller_frontier([report, wrong])
        self.assertEqual(f["app_logs_successes_for_state_producers"], 0)
        self.assertTrue(f["controller_decision_source_unchecked_for_model_review"])

    def test_failed_or_empty_runtime_log_does_not_prove_execution(self):
        for candidate in (
            native("hub_get_logs", {"mode": "past", "appId": 731},
                   {"mode": "past", "entries": []}),
            native("hub_get_logs", {"mode": "past", "appId": 731},
                   {"mode": "past", "entries": [{"message": "error"}]}, success=False),
        ):
            with self.subTest(candidate=candidate["success"]):
                score = causal_publication_floor(
                    "Why was the relay switched?",
                    "The output turned on because a controller condition was satisfied.",
                    [report, candidate])
                self.assertEqual(score["reason"], "controller_decision_unverified")


if __name__ == "__main__":
    unittest.main()

"""Synthetic regressions for bounded temporal source projections."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from bounded_temporal_projection import (
    memory_window_statistics_answer,
    bounded_newest_two_event_answer,
    bounded_contact_event_sequence_answer,
)


def wrapped(payload):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(payload)}]})


def receipt(name, args, payload, *, headline=None, success=True):
    outer = json.loads(wrapped(payload))
    if headline is not None:
        outer["client_claim_evidence_headline"] = headline
    return {"name": name, "arguments": args, "success": success,
            "operation_executed": True, "response": json.dumps(outer)}


class MemoryProjectionTests(unittest.TestCase):
    def make_receipts(self):
        return [
            {"name": "homebrain_read_clock", "arguments": {}, "success": True,
             "response": json.dumps({"local_clock": {
                 "client_now_utc": "2026-11-23T10:20:00+00:00"}})},
            receipt("hub_get_memory_history", {}, {"entries": [
                {"timestamp": "11-23 09:55:00", "freeMemoryKB": 1000},
                {"timestamp": "11-23 10:01:00", "freeMemoryKB": 900},
                {"timestamp": "11-23 10:06:00", "freeMemoryKB": 800},
                {"timestamp": "11-23 10:19:00", "freeMemoryKB": 700},
            ]}),
        ]

    def test_exact_mean_range_delta_and_gap_scope(self):
        question = ("Compare the hub free memory with returned samples for the "
                    "preceding 20 minutes; show mean, minimum, maximum and range.")
        result = memory_window_statistics_answer(question, self.make_receipts(), "Europe/London")
        self.assertEqual(result["status"], "source_derived_statistics")
        answer = result["answer"]
        self.assertIn("3 samples inside", answer)
        self.assertIn("1 parsed sample outside", answer)
        self.assertIn("Arithmetic mean (not time-weighted): **800 KB**", answer)
        self.assertIn("Range (maximum − minimum): **200 KB**", answer)
        self.assertIn("100 KB below the mean", answer)
        self.assertIn("1m 0.000s", answer)
        self.assertIn("13m 0.000s", answer)
        self.assertIn("not a live memory read", answer)

    def test_memory_projection_requires_comparison_and_clock(self):
        receipts = self.make_receipts()
        self.assertIsNone(memory_window_statistics_answer(
            "What is the current free memory?", receipts, "Europe/London"))
        self.assertIsNone(memory_window_statistics_answer(
            "Compare free memory for the preceding 20 minutes.", receipts[:1],
            "Europe/London"))


class EventPairProjectionTests(unittest.TestCase):
    def make_receipt(self):
        events = [
            {"name": "thermostatOperatingState", "value": "idle",
             "date": "2026-11-23T09:29:41.156+0000", "isStateChange": True,
             "producedBy": {"name": "Private Actor Must Not Leak"}},
            {"name": "thermostatOperatingState", "value": "idle",
             "date": "2026-11-23T09:10:00.000+0000", "isStateChange": True},
        ]
        return receipt(
            "hub_list_device_events", {"deviceId": 4718,
            "attribute": "thermostatOperatingState", "limit": 2},
            {"source": "device", "device": "Livingroom TRV", "deviceId": "4718",
             "events": events, "count": 2},
            headline={"returned_row_count": 2, "requested_row_limit": 2,
                      "row_limit_reached": True,
                      "source_scope": "returned rows only"},
        )

    def test_two_newest_rows_sorted_and_elapsed_exactly(self):
        question = ("For Livingroom TRV, find the newest two recorded thermostat "
                    "operating-state samples and calculate exact elapsed seconds. "
                    "Explain what remains unobserved between these records.")
        result = bounded_newest_two_event_answer(question, [self.make_receipt()])
        self.assertEqual(result["status"], "bounded_newest_two_event_rows")
        self.assertIn("1,181.156 seconds", result["answer"])
        self.assertIn("09:10:00", result["answer"])
        self.assertIn("09:29:41.156", result["answer"])
        self.assertIn("row limit was reached", result["answer"])
        self.assertIn("does not identify the preceding value", result["answer"])
        self.assertNotIn("Private Actor", result["answer"])
        self.assertFalse(result["trajectory_verified"])

    def test_event_pair_fails_closed_on_wrong_target_or_limit(self):
        question = ("For Livingroom TRV, find the newest two recorded thermostat "
                    "operating-state samples and calculate exact elapsed seconds.")
        self.assertIsNone(bounded_newest_two_event_answer(
            question.replace("Livingroom", "Bedroom"), [self.make_receipt()]))
        bad = self.make_receipt()
        bad["arguments"]["limit"] = 3
        self.assertIsNone(bounded_newest_two_event_answer(question, [bad]))


class ContactSequenceProjectionTests(unittest.TestCase):
    def make_receipt(self):
        events = [
            {"name": "contact", "value": "closed", "date": "2026-11-23T20:00:04.000+0000"},
            {"name": "contact", "value": "open", "date": "2026-11-23T20:00:00.000+0000"},
            {"name": "contact", "value": "open", "date": "2026-11-23T18:30:00.000+0000"},
            {"name": "contact", "value": "closed", "date": "2026-11-23T17:00:00.000+0000"},
        ]
        return receipt(
            "hub_list_device_events", {"deviceId": 7852, "attribute": "contact",
            "hoursBack": 7, "limit": 100},
            {"source": "device", "device": "Front Door Contact", "deviceId": "7852",
             "attributeFilter": "contact", "hoursBack": 7,
             "sinceTimestamp": "2026-11-23T15:00:00.000+0000",
             "events": events, "count": 4},
            headline={"returned_row_count": 4, "requested_row_limit": 100,
                      "row_limit_reached": False,
                      "unseen_rows_or_commands_proven_absent": False},
        )

    def test_contact_gaps_are_chronological_and_not_continuity(self):
        question = ("For Front Door contact, give newest OPEN and CLOSED reports "
                    "from the preceding seven hours, earliest/latest returned "
                    "timestamps, and significant unobserved intervals.")
        result = bounded_contact_event_sequence_answer(question, [self.make_receipt()])
        answer = result["answer"]
        self.assertIn("Latest OPEN report among returned rows: **2026-11-23T20:00:00.000Z**", answer)
        self.assertIn("Latest CLOSED report among returned rows: **2026-11-23T20:00:04.000Z**", answer)
        self.assertIn("17:00:00.000Z", answer)
        self.assertIn("18:30:00.000Z", answer)
        self.assertLess(answer.index("17:00:00.000Z"), answer.index("18:30:00.000Z"))
        self.assertNotIn("remained closed", answer.lower())
        self.assertIn("not proof that the contact stayed", answer)
        self.assertFalse(result["continuous_state_verified"])

    def test_contact_rejects_metadata_count_mismatch(self):
        question = ("For Front Door contact, give newest OPEN and CLOSED reports "
                    "from the preceding seven hours, earliest/latest returned "
                    "timestamps, and significant unobserved intervals.")
        bad = self.make_receipt()
        outer = json.loads(bad["response"])
        native = json.loads(outer["content"][0]["text"])
        native["count"] = 9
        outer["content"][0]["text"] = json.dumps(native)
        bad["response"] = json.dumps(outer)
        self.assertIsNone(bounded_contact_event_sequence_answer(question, [bad]))


if __name__ == "__main__":
    unittest.main()

"""General, fictional temporal provenance and source-usage regressions.

Never reaches a real hub or an LLM endpoint. No actual device IDs or secrets.
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_review import (
    FINAL_CLAIM_AUDIT_PROMPT, final_claim_receipt_scope_index,
)
from temporal_receipt_fidelity import temporal_receipt_fidelity_index


def event_receipt(events, *, tool="hub_list_device_events"):
    return {
        "name": tool,
        "arguments": {"deviceId": 101, "hoursBack": 24},
        "success": True,
        "response": json.dumps({"content": [{
            "type": "text", "text": json.dumps({
                "events": events, "deviceId": 101,
            })
        }]}),
    }


class TemporalReceiptFidelityTests(unittest.TestCase):
    def test_clock_spliced_from_later_observation_is_not_verified(self):
        rows = [
            {"name": "thermostatOperatingState", "value": "idle",
             "date": "2026-01-02T08:36:05.014+0000"},
            {"name": "temperature", "value": "22.7",
             "date": "2026-01-02T08:37:32.815+0000"},
            {"name": "temperature", "value": "21.8",
             "date": "2026-01-02T20:30:55.387+0000"},
        ]
        receipt = event_receipt(rows)
        original = json.dumps(receipt, sort_keys=True)
        answer = ("Valve went idle at 08:36:05.014. "
                  "Temperature was 21.8 C at 08:36:05.387.")
        result = temporal_receipt_fidelity_index([receipt], answer)
        by_clock = {x["draft_cited_clock"]: x for x in result["draft_clock_anchors"]}
        self.assertTrue(by_clock["08:36:05.014"]["exact_returned_event_clock_found"])
        self.assertEqual(by_clock["08:36:05.014"]["matching_returned_event_rows"][0]
                         ["event_value"], "idle")
        self.assertFalse(by_clock["08:36:05.387"]["exact_returned_event_clock_found"])
        nearby = by_clock["08:36:05.387"]["nearby_returned_event_rows_not_a_match"]
        self.assertEqual(nearby[0]["event_name"], "thermostatOperatingState")
        self.assertTrue(any(row["event_value"] == "22.7" for row in nearby))
        self.assertNotIn("21.8", json.dumps(nearby))
        self.assertEqual(json.dumps(receipt, sort_keys=True), original)
        nav = json.loads(final_claim_receipt_scope_index([receipt], draft_answer=answer))
        self.assertEqual(len(nav["temporal_event_anchors"]["draft_clock_anchors"]), 2)

    def test_nearby_does_not_prove_causal_delay(self):
        receipt = event_receipt([
            {"name": "motion", "value": "inactive",
             "date": "2026-01-02T20:07:28.876+0000"},
            {"name": "switch", "value": "off",
             "date": "2026-01-02T20:07:29.954+0000"},
            {"name": "command-setLevel", "value": "45",
             "date": "2026-01-02T20:06:45.130+0000"},
        ])
        result = temporal_receipt_fidelity_index(
            [receipt], "Motion inactive at 20:07:28.876; off at 20:07:29.954.")
        self.assertEqual(len(result["draft_clock_anchors"]), 2)
        self.assertTrue(all(x["exact_returned_event_clock_found"]
                            for x in result["draft_clock_anchors"]))
        self.assertIn("shorter elapsed period contradicts", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("Do not invent an earlier countdown start", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("chronological order", FINAL_CLAIM_AUDIT_PROMPT)

    def test_clock_without_returned_events_does_not_invent_empty_history(self):
        receipt = event_receipt([{
            "name": "motion", "value": "active",
            "date": "2026-01-02T12:15:09+0000",
        }])
        self.assertIsNone(temporal_receipt_fidelity_index(
            [{"name": "hub_list_devices", **receipt}], "At 12:15:09 active"))
        index = temporal_receipt_fidelity_index([receipt], "At 12:00:01 absent")
        self.assertFalse(index["draft_clock_anchors"][0]
                         ["exact_returned_event_clock_found"])
        self.assertIn("does NOT prove", index["warning"])

    def test_credential_fields_and_failures_are_not_replayed(self):
        receipt = event_receipt([
            {"name": "accessToken", "value": "FAKE-DO-NOT-DISCLOSE",
             "date": "2026-01-02T09:00:01+0000"},
            {"name": "temperature", "value": "secret bearer 123",
             "date": "2026-01-02T09:00:02+0000"},
            {"name": "temperature", "value": "20.0",
             "date": "2026-01-02T09:00:03+0000"},
        ])
        failed = dict(receipt, success=False, response="FAKE-SECRET")
        result = temporal_receipt_fidelity_index(
            [receipt, failed], "Read at 09:00:01 then 09:00:03")
        output = json.dumps(result)
        self.assertNotIn("FAKE", output)
        self.assertNotIn("secret bearer", output)
        self.assertIn("20.0", output)
        self.assertNotIn("accessToken", output)

    def test_index_bounded_by_draft_clocks_and_event_count(self):
        many = [{
            "name": "power", "value": str(i),
            "date": f"2026-01-02T11:{i//60:02d}:{i%60:02d}+0000"
        } for i in range(360)]
        receipt = event_receipt(many)
        draft = " ".join(f"11:{i//60:02d}:{i%60:02d}" for i in range(36))
        index = temporal_receipt_fidelity_index([receipt], draft)
        self.assertEqual(len(index["draft_clock_anchors"]), 18)
        self.assertEqual(index["draft_clocks_not_indexed_due_to_cap"], 18)


class MonitorProvenanceTests(unittest.TestCase):
    def test_monitor_configured_does_not_mean_monitor_historical_data_was_used(self):
        class FakeMCP:
            async def list_tools(self, refresh=False):
                return []
        class FakeMonitor:
            async def query(self, args):
                return {"source": "synthetic", "mode": args["mode"]}
        class FakeAgent(Agent):
            async def round(self, messages, tools, remaining):
                return {"content": "Synthetic: source not queried."}

        async def run():
            agent = FakeAgent("http://localhost:11434", "mock", "", 20)
            try:
                reply = await agent.answer(
                    "Report the current fictional sensor reading", [],
                    FakeMCP(), 60, device_monitor=FakeMonitor(),
                    enable_source_review=False,
                )
                self.assertTrue(reply["available_read_sources"]["hub_device_monitor"]["configured"])
                self.assertEqual(reply["read_source_usage"]["hub_device_monitor_tool_attempts"], 0)
                self.assertFalse(reply["read_source_usage"]["hub_device_monitor_history_used"])
            finally:
                await agent.close()
        asyncio.run(run())

    def test_one_history_tool_call_is_marked_only_when_successful(self):
        class FakeMCP:
            async def list_tools(self, refresh=False):
                return []
        class FakeMonitor:
            async def query(self, args):
                return {"source": "synthetic monitor archive",
                        "mode": args["mode"], "values": [1, 2]}
        class FakeAgent(Agent):
            def __init__(self):
                super().__init__("http://localhost:11434", "mock", "", 20)
                self.turns = 0
            async def round(self, messages, tools, remaining):
                self.turns += 1
                if self.turns == 1:
                    return {"tool_calls": [{"function": {
                        "name": "homebrain_read_device_monitor",
                        "arguments": {"mode": "history",
                                      "device_id": "101", "range": "1h"},
                    }}]}
                return {"content": "Synthetic historic bins read, not continuous samples."}
        async def run():
            agent = FakeAgent()
            try:
                answer = await agent.answer(
                    "Read historical measurement for a fictional device", [],
                    FakeMCP(), 60, device_monitor=FakeMonitor(),
                    enable_source_review=False,
                )
                self.assertTrue(answer["success"])
                self.assertEqual(answer["read_source_usage"]["native_device_event_reads"], 0)
                self.assertEqual(answer["read_source_usage"]["hub_device_monitor_tool_attempts"], 1)
                self.assertEqual(answer["read_source_usage"]["hub_device_monitor_historical_reads"], 1)
                self.assertTrue(answer["read_source_usage"]["hub_device_monitor_history_used"])
            finally:
                await agent.close()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

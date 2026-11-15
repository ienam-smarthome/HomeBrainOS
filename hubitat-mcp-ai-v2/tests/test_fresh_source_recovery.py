"""Offline v2 fresh-source recovery lifecycle: no hardcoded reads or new rounds."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_review import (
    FRESH_SOURCE_RECOVERY_PROMPT, should_offer_fresh_source_recovery,
)


QUESTION = (
    "For Fictional Kitchen Light, list every returned ON/OFF switch event "
    "over the past six hours, including timestamps and command issuers "
    "where supported. Do not change anything."
)
PRIOR_CONTEXT = "Earlier receipts for an unrelated fictional office light; not a current read."


def tool(name, args):
    return {"function": {"name": name, "arguments": args}}


class SafeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_devices", "description": "Read-only targeted inventory",
             "inputSchema": {"type": "object", "properties": {
                 "labelFilter": {"type": "string"}, "format": {"type": "string"}}}},
            {"name": "hub_list_device_events", "description": "Read-only device history",
             "inputSchema": {"type": "object", "properties": {
                 "deviceId": {"type": "integer"}, "hoursBack": {"type": "integer"},
                 "limit": {"type": "integer"}, "attribute": {"type": "string"}}}},
            {"name": "hub_manage_fake_settings", "description": "Unsafe write",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_list_devices":
            return {"content": [{"type": "text", "text": json.dumps({
                "devices": [{"id": "101", "label": "Fictional Kitchen Light"}],
                "count": 1, "total": 1
            })}]}
        if name == "hub_list_device_events":
            if args.get("deviceId") != 101:
                raise AssertionError("Wrong device")
            return {"content": [{"type": "text", "text": json.dumps({
                "source": "device", "deviceId": "101",
                "hoursBack": 6, "attributeFilter": "switch",
                "sinceTimestamp": "2030-04-02T17:00:00.000+0000",
                "events": [{"name": "switch", "value": "off",
                            "date": "2030-04-02T20:01:02.123+0000",
                            "isStateChange": True,
                            "producedBy": {"deviceId": "777", "name": "Fixture Bridge"}}],
                "count": 1,
            })}]}
        raise AssertionError("Unexpected write or tool call: " + name)


class RecoveryEligibilityTests(unittest.TestCase):
    def eligible(self, question=QUESTION, **kwargs):
        return should_offer_fresh_source_recovery(
            question, kind=kwargs.get("kind", "historical_measurement"),
            has_current_read_attempt=kwargs.get("has_current_read_attempt", False),
            available_read_tools=kwargs.get("available_read_tools", True),
            has_action_receipt=kwargs.get("has_action_receipt", False),
        )

    def test_writes_prohibited_is_not_read_prohibition(self):
        self.assertTrue(self.eligible())
        self.assertIn("DOES NOT forbid", FRESH_SOURCE_RECOVERY_PROMPT)
        self.assertIn("READ-ONLY", FRESH_SOURCE_RECOVERY_PROMPT)
        for kind in ("causal", "source_verification"):
            self.assertTrue(self.eligible(kind=kind))
        self.assertFalse(self.eligible(kind=None))
        self.assertFalse(self.eligible(has_current_read_attempt=True))
        self.assertFalse(self.eligible(has_action_receipt=True))
        self.assertFalse(self.eligible(available_read_tools=False))
        self.assertFalse(self.eligible("Turn the lamp on during past six hours."))

    def test_explicit_refusal_of_new_reads_is_respected(self):
        for instruction in (
            "Do not query the hub.",
            "No new tool calls.",
            "Don't use any tools.",
            "Use only previous receipts.",
            "Do not access the hub.",
        ):
            with self.subTest(instruction=instruction):
                self.assertFalse(self.eligible(QUESTION + " " + instruction))
        self.assertTrue(self.eligible(QUESTION + " Do not change anything."))


class FreshReadLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_prior_only_refusal_then_model_chooses_new_read(self):
        hub = SafeMCP()

        class Model(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
                self.round_count = 0
                self.audit_tools = None
                self.recovery_tools = None
                self.recovery_prompt = ""

            async def round(self, messages, tools, remaining):
                self.round_count += 1
                i = self.round_count
                if i == 1:
                    return {"content": "Only older office-device receipts exist; do not change anything prohibits reads."}
                if i == 2:
                    self.recovery_prompt = messages[-1]["content"]
                    self.recovery_tools = [x["function"]["name"] for x in tools]
                    return {"tool_calls": [tool("hub_list_devices", {
                        "labelFilter": "Fictional Kitchen Light", "format": "summary"
                    })]}
                if i == 3:
                    return {"tool_calls": [tool("hub_list_device_events", {
                        "deviceId": 101, "hoursBack": 6, "attribute": "switch", "limit": 30
                    })]}
                if i == 4:
                    return {"content": "Every switch event was ON; there were no commands."}
                if i == 5:
                    self.audit_tools = [x["function"]["name"] for x in tools]
                    return {"content": "There were no switch events or commands."}
                raise AssertionError("Unexpected extra model round")

        model = Model()
        try:
            result = await model.answer(
                QUESTION, [], hub, 90, prior_evidence=PRIOR_CONTEXT,
                prior_receipts=2, enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertEqual(result["rounds"], 5)
        self.assertEqual(result["prior_receipts_used"], 2)
        self.assertEqual(result["fresh_source_recovery_status"], "read_succeeded")
        self.assertTrue(result["fresh_source_recovery_invoked"])
        self.assertEqual(result["source_review_kind"], "historical_measurement")
        self.assertEqual(hub.calls, [
            ("hub_list_devices", {"labelFilter": "Fictional Kitchen Light", "format": "summary"}),
            ("hub_list_device_events", {"deviceId": 101, "hoursBack": 6,
                                        "attribute": "switch", "limit": 30}),
        ])
        self.assertIn("Missing fresh source", model.recovery_prompt)
        self.assertIn("READ-ONLY", model.recovery_prompt)
        self.assertIn("hub_list_device_events", model.recovery_tools)
        self.assertNotIn("hub_manage_fake_settings", model.recovery_tools)
        self.assertEqual(model.audit_tools, [])
        self.assertTrue(result["final_claim_audit_invoked"])
        self.assertEqual(result["structured_history_verification"]["status"], "source_ledger_used")
        self.assertEqual(result["structured_history_verification"]["source_event_rows"], 1)
        self.assertIn("2030-04-02T20:01:02.123+0000", result["answer"])
        self.assertIn("command coverage not verified", result["answer"].lower())
        self.assertNotIn("no switch events or commands", result["answer"].lower())

    async def test_uncooperative_model_skips_source_free_final_audit(self):
        hub = SafeMCP()

        class Model(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
                self.round_count = 0
            async def round(self, messages, tools, remaining):
                self.round_count += 1
                if self.round_count == 1:
                    return {"content": "I cannot inspect the target without permission."}
                if self.round_count == 2:
                    self.assert_condition = "Missing fresh source" in messages[-1]["content"]
                    return {"content": "No fresh read was made; history remains unknown."}
                raise AssertionError("Wasted final-audit cloud model round")

        model = Model()
        try:
            result = await model.answer(
                QUESTION, [], hub, 90, prior_evidence=PRIOR_CONTEXT,
                prior_receipts=2, enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertEqual(model.round_count, 2)
        self.assertTrue(model.assert_condition)
        self.assertEqual(hub.calls, [])
        self.assertTrue(result["fresh_source_recovery_invoked"])
        self.assertEqual(result["fresh_source_recovery_status"], "no_current_read_attempt")
        self.assertFalse(result["final_claim_audit_invoked"])
        self.assertEqual(result["final_claim_audit_status"], "skipped_no_fresh_read")
        self.assertEqual(result["structured_history_verification"]["status"], "unverified")
        self.assertIsNone(result["structured_history_verification"]["source_event_rows"])
        self.assertNotIn("No switch transitions occurred", result["answer"])


if __name__ == "__main__":
    unittest.main()

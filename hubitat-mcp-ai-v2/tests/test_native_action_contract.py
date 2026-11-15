"""Fictional, source-only V2 action contract tests.

No real Hubitat, router, model API, devices or timer are contacted.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from interaction import Interaction, action_preview
from mcp import MCPError
from native_action_contract import (
    numeric_minutes, requested_timing, source_derived_timing_answer,
    timing_kind, verified_device_details,
)


def envelope(source):
    return json.dumps({"content": [{
        "type": "text", "text": json.dumps(source)
    }]})


def detail(device_id="301", label="Fictional Timed Relay",
           commands=("deferDisconnectInMinutes", "allowForMinutes")):
    return {
        "name": "hub_get_device",
        "arguments": {"deviceId": device_id, "mode": "summary"},
        "success": True,
        "result_kind": "tool_result",
        "response": envelope({
            "id": device_id, "label": label,
            "commands": [{"name": item, "arguments": [
                {"name": "Minutes", "type": "NUMBER"}
            ]} for item in commands],
        }),
    }


def accepted(command="deferDisconnectInMinutes", minutes="5",
             device_id=301, *, native_success=True):
    return {
        "name": "hub_call_device_command",
        "arguments": {
            "deviceId": device_id, "command": command,
            "parameters": [minutes],
        },
        "success": True, "possible_native_action": True,
        "result_kind": "tool_result",
        "response": json.dumps({
            "client_action_receipt_scope": {
                "client_metadata_is_not_independent_outcome_evidence": True
            },
            "content": [{"type": "text", "text": json.dumps({
                "success": native_success,
                "device": "Fictional Timed Relay",
                "command": command,
                "parameters": [int(minutes)],
                "state": {
                    "pendingActionAt": {
                        "value": "2026-11-15 16:05:00",
                        "timestamp": "2026-11-15 16:00:00"
                    },
                    "switch": {
                        "value": "on",
                        "timestamp": "2026-11-15 15:55:00"
                    },
                },
            })}],
            "client_write_snapshot_scope": {
                "snapshot_in_write_response_is_independent_readback": False
            },
        }),
    }


class SourceOnlyActionTests(unittest.TestCase):
    def test_five_minute_delay_corrects_false_duration_and_future_claim(self):
        text = ("I have blocked the relay for 5 minutes. "
                "It will automatically restore access after the window.")
        before = [detail(), accepted()]
        original = json.dumps(before, sort_keys=True)
        result = source_derived_timing_answer(
            "Disconnect the fictional relay after 5 minutes", text, before)
        self.assertEqual(result["status"], "source_derived_native_acceptance")
        self.assertIn("**after 5 minutes**", result["answer"])
        self.assertIn("**not** an action duration", result["answer"])
        self.assertIn("pendingActionAt = 2026-11-15 16:05:00", result["answer"])
        self.assertIn("not an independent post-write readback", result["answer"])
        self.assertIn("has not been observed", result["answer"])
        self.assertNotIn("automatically restore", result["answer"])
        self.assertEqual(result["verified_device_id"], "301")
        self.assertEqual(json.dumps(before, sort_keys=True), original,
                         "Source-derived answer must not mutate original receipts")

    def test_native_for_minutes_is_duration_and_never_delay(self):
        receipts = [detail(), accepted("allowForMinutes", "7")]
        result = source_derived_timing_answer(
            "Allow Fictional Timed Relay for 7 minutes",
            "I will allow it in seven minutes.", receipts)
        self.assertEqual(result["status"], "source_derived_native_acceptance")
        self.assertIn("**for 7 minutes**", result["answer"])
        self.assertIn("**not** a delayed start", result["answer"])
        self.assertNotIn("allow it in seven", result["answer"])

    def test_wrong_timing_kind_yields_caution_not_success(self):
        sources = [detail(), accepted("allowForMinutes", "5")]
        res = source_derived_timing_answer(
            "Allow the fictional relay after 5 minutes",
            "Done! Scheduled for five minutes.", sources)
        self.assertEqual(res["status"], "native_timing_mismatch")
        self.assertIn("different timing semantics", res["answer"])
        self.assertNotIn("Done!", res["answer"])

    def test_no_native_acceptance_or_matching_source_does_not_project(self):
        base = [detail(), accepted(native_success=False)]
        for sources in (
            base, [accepted()], [detail(device_id="302"), accepted()],
            [dict(detail(), success=False), accepted()],
            [dict(detail(), response="{invalid"), accepted()],
            [detail(commands=("off",)), accepted()],
            [detail(), dict(accepted(), possible_native_action=False)],
            [detail(), dict(accepted(), success=False)],
        ):
            with self.subTest(sources=sources):
                res = source_derived_timing_answer(
                    "Disconnect the fictional relay after 5 minutes",
                    "No verified completion", sources)
                self.assertEqual(res["status"], "not_projected")
                self.assertEqual(res["answer"], "No verified completion")

    def test_ambiguous_relative_request_fails_closed(self):
        sources = [detail(), accepted()]
        for question in (
            "How do native timers work?",
            "Disconnect the relay for 5 and after 7 minutes",
            "Disconnect the relay in 5 minutes for 10 minutes",
            "Disconnect the relay after five minutes",
        ):
            with self.subTest(question=question):
                res = source_derived_timing_answer(
                    question, "Original answer", sources)
                self.assertEqual(res["status"], "not_applicable")

    def test_source_label_matching_and_parameter_sanitization(self):
        valid = detail()
        bad = [
            dict(valid, arguments={"deviceId": "999"}),
            dict(valid, success=False),
            dict(valid, result_kind="prior_evidence_read"),
            dict(valid, response="{broken"),
        ]
        self.assertEqual(verified_device_details([valid])["301"]["label"],
                         "Fictional Timed Relay")
        for source in bad:
            self.assertNotIn("301", verified_device_details([source]))
        self.assertEqual(numeric_minutes("5"), "5")
        self.assertEqual(numeric_minutes(5), "5")
        self.assertIsNone(numeric_minutes("5;blockInternet"))
        self.assertIsNone(numeric_minutes("five"))
        self.assertIsNone(numeric_minutes(True))
        self.assertEqual(timing_kind("deferDisconnectInMinutes"), "delay")
        self.assertEqual(timing_kind("allowForMinutes"), "duration")
        self.assertIsNone(timing_kind("off"))
        self.assertEqual(requested_timing("Disconnect relay in 5 mins"),
                         ("delay", "5"))

    def test_approval_preview_name_exact_id_and_string_number(self):
        devices = verified_device_details([detail()])
        proposal = {"deviceId": 301, "command": "deferDisconnectInMinutes",
                    "parameters": ["5"], "token": "FAKE_SECRET"}
        preview = action_preview(
            "hub_call_device_command", proposal, "routine_write",
            verified_devices=devices)
        self.assertEqual(preview["fields"]["device"], "Fictional Timed Relay")
        self.assertEqual(preview["fields"]["device_id"], "301")
        self.assertEqual(preview["fields"]["parameters"], "5")
        self.assertIn("After 5 minutes", preview["fields"]["timing"])
        self.assertNotIn("FAKE_SECRET", str(preview))
        # No authoritative source? Leave ID visible and never guess the label.
        unknown = action_preview(
            "hub_call_device_command", proposal, "routine_write")
        self.assertEqual(unknown["fields"]["device"], "301")
        self.assertNotIn("device_id", unknown["fields"])

    def test_interaction_rejects_edited_source_display_as_authority(self):
        # The label is used for display only. Only original action args reach
        # the native call if the user explicitly approves.
        interaction = Interaction(require_native_write_approval=True)
        interaction.register_current_native_device_details([detail()])
        async def exercise():
            task = asyncio.create_task(interaction.before_call(
                "hub_call_device_command",
                {"deviceId": "301", "command": "deferDisconnectInMinutes",
                 "parameters": ["5"]}, "Fictional delay"))
            await asyncio.sleep(0)
            self.assertEqual(
                interaction.pending["preview"]["fields"]["device"],
                "Fictional Timed Relay")
            self.assertEqual(
                interaction.pending["preview"]["fields"]["device_id"], "301")
            interaction.decide(interaction.pending["id"], False)
            with self.assertRaises(MCPError):
                await task
        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()

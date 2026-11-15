"""V2 native approval lifecycle: fictional user, device and MCP receipts.

No live Hubitat devices, cloud model, networking, router or automation.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from action_lifecycle import (
    inspect_action_lifecycle, unprepared_action_choices, unprepared_answer,
)


PROMPT = "Disconnect the fictional relay after ten minutes"


class NativeLifecycleTests(unittest.TestCase):
    def state(self, *, text=PROMPT, receipts=None, selected=False,
              submitted=False, web=True):
        return inspect_action_lifecycle(
            text, receipts or [], native_write_selected=selected,
            native_write_submitted=submitted, ui_approval_available=web,
        )

    def test_silent_model_json_plan_still_has_no_real_approval(self):
        state = self.state()
        choices = unprepared_action_choices(state, ui_approval_available=True)
        self.assertEqual(state["status"], "not_prepared")
        self.assertFalse(state["native_write_submitted"])
        self.assertFalse(state["approval_pending"])
        self.assertEqual(choices["status"], "unprepared_confirmation")
        self.assertEqual(choices["reason"], "no_native_write_selected")
        self.assertFalse(choices["native_write_queued"])
        self.assertEqual(choices["options"],
                         ["prepare_action", "edit_request", "dismiss"])
        draft = ('{"name":"hub_call_device_command",'
                 '"arguments":{"deviceId":"101","command":"disconnectInMinutes"}}'
                 ' This will be sent after UI approval.')
        answer = unprepared_answer(state, draft)
        self.assertIn("**No action queued.**", answer)
        self.assertIn("there is nothing to approve", answer)
        self.assertNotIn('"name":"hub_call_device_command"', answer)
        self.assertNotIn("will be sent after UI approval", answer)

    def test_nonimperative_and_read_only_have_no_action_choice(self):
        for question in (
            "Why did the fictional relay switch off?",
            "Check fictional relay status. Do not change anything.",
            "Disconnect the relay after 10 minutes. Do not change anything.",
        ):
            with self.subTest(question=question):
                state = self.state(text=question)
                self.assertEqual(state["status"], "not_applicable")
                self.assertIsNone(unprepared_action_choices(
                    state, ui_approval_available=True))

    def test_no_web_approval_does_not_invent_card(self):
        state = self.state(web=False)
        self.assertEqual(state["status"], "not_prepared")
        self.assertIsNone(unprepared_action_choices(
            state, ui_approval_available=False))
        self.assertEqual(
            unprepared_answer({"status": "not_applicable"}, "Original answer"),
            "Original answer")

    def test_selected_but_not_submitted_prevents_silent_retry(self):
        state = self.state(selected=True, submitted=False)
        self.assertEqual(state["status"], "native_write_not_submitted")
        self.assertFalse(state["native_write_submitted"])
        self.assertIsNone(unprepared_action_choices(
            state, ui_approval_available=True))

    def test_submitted_acceptance_is_native_only_not_future_result(self):
        records = [{
            "name": "hub_call_device_command",
            "result_kind": "tool_result",
            "possible_native_action": True,
            "success": True,
            "response": ('{"content":[{"type":"text","text":'
                         '"{\\"success\\":true,\\"command\\":'
                         '\\"disconnectInMinutes\\"}"}]}'),
        }]
        state = self.state(receipts=records, selected=True, submitted=True)
        self.assertEqual(state["status"], "native_accepted")
        self.assertTrue(state["native_write_submitted"])
        self.assertTrue(state["native_write_accepted"])
        self.assertFalse(state["independent_future_outcome_verified"])
        self.assertIsNone(unprepared_action_choices(
            state, ui_approval_available=True))

    def test_native_rejected_not_confused_with_successful_model_reply(self):
        records = [{
            "name": "hub_call_device_command",
            "result_kind": "tool_result",
            "possible_native_action": True,
            "success": True,
            "response": ('{"content":[{"type":"text","text":'
                         '"{\\"success\\":false}"}]}'),
        }]
        state = self.state(receipts=records, selected=True, submitted=True)
        self.assertEqual(state["status"], "native_rejected")
        self.assertFalse(state["native_write_accepted"])
        self.assertIsNone(unprepared_action_choices(
            state, ui_approval_available=True))

    def test_uncertain_original_result_cannot_claim_acceptance(self):
        state = self.state(receipts=[], selected=True, submitted=True)
        self.assertEqual(state["status"], "native_result_unverified")
        self.assertIsNone(state["native_write_accepted"])
        self.assertIsNone(unprepared_action_choices(
            state, ui_approval_available=True))


if __name__ == "__main__":
    unittest.main()

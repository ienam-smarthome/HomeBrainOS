"""Native verification fidelity, using only fictional MCP responses and scripted models.

No real hubs, house identifiers, network calls, or autonomous future operations.
The tests prove a review mechanism is available, not that the LLM always chooses
correctly. Original native receipts are not mutated or upgraded to independent proof.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL, native_wait_for_scope
from investigation_review import ACTION_OUTCOME_REVIEW_PROMPT


def rpc(body):
    return {"content": [{"type": "text", "text": json.dumps(body)}]}


def tc(name, **args):
    return {"function": {"name": name, "arguments": args}}


class FakeHub:
    def __init__(self, body):
        self.body = body
        self.calls = []
        self.catalog = [
            {"name": "hub_call_device_command", "inputSchema": {"type": "object"}},
            {"name": "hub_get_device", "inputSchema": {"type": "object"}},
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, args.copy()))
        if name == "hub_call_device_command":
            return rpc(self.body)
        if name == "hub_get_device":
            return rpc({"id": "LAB-11", "label": "Fictional Deferred Valve",
                        "attributes": [{"name": "pendingOpenAt", "value": "none"}]})
        raise AssertionError("Unexpected synthetic MCP tool")


class FakeModel(Agent):
    def __init__(self, responses):
        super().__init__("http://localhost:11434", "fixture", "", 10)
        self.script = list(responses)
        self.messages_seen = []
        self.tools_seen = []

    async def round(self, messages, tools, remaining):
        self.messages_seen.append([dict(x) for x in messages])
        self.tools_seen.append([x["function"]["name"] for x in tools])
        if not self.script:
            raise AssertionError("Unexpected model round")
        return self.script.pop(0)


class NativeWaitScopeTests(unittest.TestCase):
    def test_accepted_command_failed_secondary_wait_has_both_outcomes(self):
        args = {"deviceId": "LAB-11", "command": "deferOpen",
                "parameters": ["3"],
                "waitFor": {"attribute": "timeRemaining",
                            "comparator": "lt", "expectedValue": "9999"}}
        original = rpc({
            "success": True,
            "command": "deferOpen",
            "waitFor": {"attribute": "timeRemaining", "expected": "9999",
                        "converged": False, "finalValue": 9999,
                        "timedOut": True, "elapsedMs": 5100,
                        "transitioning": False},
            "state": {"pendingOpenAt": {"value": "2026-02-03T10:03:00Z"}},
        })
        before = json.dumps(original, sort_keys=True)
        scope = native_wait_for_scope(original, args)
        self.assertEqual(scope["verification_outcome"], "timed_out")
        self.assertEqual(scope["reported_operation_success"], True)
        self.assertEqual(scope["reported_waitFor"]["finalValue"], 9999)
        self.assertEqual(scope["requested_postcondition"]["attribute"], "timeRemaining")
        self.assertEqual(json.dumps(original, sort_keys=True), before)
        self.assertFalse(scope["independent_outcome_evidence"])

    def test_converged_and_uncertain_outcomes_are_not_confused(self):
        args = {"waitFor": {"attribute": "position", "expectedValue": "open"}}
        good = rpc({"success": True, "waitFor": {"attribute": "position",
                    "converged": True, "timedOut": False,
                    "finalValue": "open"}})
        self.assertEqual(native_wait_for_scope(good, args)["verification_outcome"],
                         "converged")
        uncertain = rpc({"success": False, "waitFor": {"attribute": "position",
                        "converged": False, "timedOut": False,
                        "finalValue": "closed"}})
        self.assertEqual(native_wait_for_scope(uncertain, args)["verification_outcome"],
                         "not_converged")
        self.assertEqual(native_wait_for_scope(uncertain, args)[
                         "reported_operation_success"], False)
        no_wait = rpc({"success": True, "state": {"position": "open"}})
        self.assertIsNone(native_wait_for_scope(no_wait, args))
        self.assertIsNone(native_wait_for_scope(
            {"content": [{"type": "text", "text": "not json"}]}, args))
        self.assertIsNone(native_wait_for_scope(good, {"deviceId": "LAB-11"}))

    def test_nested_gateway_form_is_supported_without_tool_execution(self):
        args = {"tool": "hub_call_device_command",
                "args": {"deviceId": "LAB-11",
                         "waitFor": {"attribute": "position",
                                     "expectedValue": "open"}}}
        source = rpc({"success": True, "waitFor": {
            "converged": False, "timedOut": True, "finalValue": "closed"}})
        self.assertEqual(native_wait_for_scope(source, args)[
                         "verification_outcome"], "timed_out")

    def test_semantic_guidance_is_general_and_source_bounded(self):
        self.assertIn("after/in N minutes", _SKILL)
        self.assertIn("temporary-action command is NOT a replacement", _SKILL)
        self.assertIn("timedOut/non-converged", _SKILL)
        self.assertIn("DISCLOSE", ACTION_OUTCOME_REVIEW_PROMPT)
        self.assertIn("DELAYED onset", ACTION_OUTCOME_REVIEW_PROMPT)
        self.assertNotIn("Google TV", _SKILL)
        self.assertNotIn("6923", ACTION_OUTCOME_REVIEW_PROMPT)


class PostconditionLiveLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_native_timer_and_failed_wait_are_both_visible(self):
        hub = FakeHub({
            "success": True,
            "device": "Fictional Deferred Valve",
            "command": "deferOpen",
            "parameters": [3],
            "waitFor": {"attribute": "timeRemaining", "expected": "9999",
                        "converged": False, "finalValue": 9999,
                        "timedOut": True, "elapsedMs": 5000},
            "state": {"pendingOpenAt": {
                "value": "2026-02-03T10:03:00Z",
                "timestamp": "2026-02-03T10:00:00Z"}},
        })
        model = FakeModel([
            {"content": "Issue native deferred command.",
             "tool_calls": [tc("hub_call_device_command", deviceId="LAB-11",
                               command="deferOpen", parameters=["3"],
                               waitFor={"attribute": "timeRemaining",
                                        "comparator": "lt",
                                        "expectedValue": "9999"})]},
            {"content": "The timer is set."},
            {"content": ("The source reports a stored target deadline, but "
                         "the optional timeRemaining verification timed out "
                         "(final value 9999). Future valve opening is unobserved.")},
        ])
        try:
            reply = await model.answer("Open Fictional Deferred Valve after 3 minutes",
                                       [], hub, 60)
        finally:
            await model.close()
        self.assertTrue(reply["success"])
        self.assertEqual(reply["source_review_kind"], "action_outcome")
        self.assertEqual(reply["rounds"], 3)
        self.assertEqual(reply["tool_calls"][0]["native_wait_for_outcome"], "timed_out")
        original = json.loads(reply["tool_calls"][0]["response"])
        self.assertIn("client_native_wait_for_scope", original)
        self.assertEqual(original["client_native_wait_for_scope"][
                         "verification_outcome"], "timed_out")
        self.assertTrue(json.loads(original["content"][0]["text"])["success"])
        self.assertTrue(json.loads(original["content"][0]["text"])["waitFor"]["timedOut"])
        self.assertIn("timeRemaining verification timed out", reply["answer"])
        self.assertEqual([name for name, _ in hub.calls],
                         ["hub_call_device_command"])
        self.assertNotIn("hub_call_device_command", model.tools_seen[2])

    async def test_temporary_action_does_not_satisfy_delayed_start(self):
        hub = FakeHub({
            "success": True,
            "command": "allowTemporarily",
            "state": {"access": {"value": "allowed",
                                 "timestamp": "2026-02-03T10:00:00Z"}},
        })
        model = FakeModel([
            {"content": "Allow the fictional valve temporarily.",
             "tool_calls": [tc("hub_call_device_command", deviceId="LAB-11",
                               command="allowTemporarily", parameters=["3"])]},
            {"content": "The delayed opening has been scheduled."},
            {"content": ("Correction: access changed immediately for a "
                         "temporary period; the user's delayed start was NOT "
                         "scheduled. No additional command was sent.")},
        ])
        try:
            reply = await model.answer("Allow Fictional Valve to open after 3 minutes",
                                       [], hub, 60)
        finally:
            await model.close()
        self.assertTrue(reply["success"])
        self.assertEqual(reply["source_review_kind"], "action_outcome")
        self.assertEqual(reply["rounds"], 3)
        self.assertIn("changed immediately", reply["answer"])
        self.assertIn("NOT scheduled", reply["answer"])
        self.assertEqual(len(hub.calls), 1)
        self.assertNotIn("hub_call_device_command", model.tools_seen[2])
        self.assertNotIn("client_native_wait_for_scope",
                         json.loads(reply["tool_calls"][0]["response"]))


if __name__ == "__main__":
    unittest.main()

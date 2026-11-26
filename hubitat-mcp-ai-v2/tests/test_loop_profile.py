"""loop_profile "plain": a tool loop plus the hard gates, with no review layers or rewrites."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import Agent, DEFAULT_LOOP_PROFILE, LOOP_PROFILES, PLAIN_NO_COMMAND_NOTE  # noqa: E402
from interaction import Interaction  # noqa: E402
from test_already_in_state_guard import Hub, ON, READ, call  # noqa: E402
from test_routine_auto_approval import BlockHub, LightHub  # noqa: E402


class Script(Agent):
    loop_profile = "plain"

    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 15)
        self.script = list(script)
        self.rounds_seen = 0

    async def round(self, messages, tools, remaining):
        if not self.script:
            raise AssertionError("Unexpected extra model round")
        self.rounds_seen += 1
        return self.script.pop(0)


def say(text):
    return {"content": text, "tool_calls": []}


def use(*calls):
    return {"content": "", "tool_calls": list(calls)}


def command(**args):
    return call("hub_call_device_command", args)


async def run(model, question, hub, gate=None, decide=None, **kwargs):
    """Drive one request; when a card appears record it and answer with ``decide``."""
    cards = []
    task = asyncio.create_task(model.answer(
        question, [], hub, 60, before_call=gate.before_call if gate else None, **kwargs))
    try:
        for _ in range(3000):
            if task.done():
                break
            if gate is not None and gate.pending:
                cards.append(gate.pending)
                gate.decide(gate.pending["id"], bool(decide))
            await asyncio.sleep(0.002)
        result = await asyncio.wait_for(task, 5)
    finally:
        if not task.done():
            task.cancel()
        await model.close()
    return result, cards


def writes(hub):
    return [(n, a) for n, a in hub.calls
            if n == "hub_call_device_command"
            or (isinstance(a, dict) and a.get("tool") == "hub_call_device_command")]


class Selection(unittest.IsolatedAsyncioTestCase):
    def test_full_stays_the_default(self):
        self.assertEqual(DEFAULT_LOOP_PROFILE, "full")
        self.assertEqual(Agent.loop_profile, "full")
        self.assertEqual(LOOP_PROFILES, ("full", "plain"))

    async def test_request_value_beats_the_option_and_unknown_means_full(self):
        for option, requested, expected in (
                ("full", "plain", "plain"), ("plain", "full", "full"),
                ("plain", None, "plain"), ("typo", None, "full")):
            model = Script([say("Hello.")] * 3)
            model.loop_profile = option
            result, _ = await run(model, "hello", Hub("off"), loop_profile=requested)
            self.assertEqual(result["loop_profile"], expected, (option, requested))


class NoLayers(unittest.IsolatedAsyncioTestCase):
    QUESTION = "Why did the fictional lamp come on at 14:08?"
    ANSWER = "The fictional lamp was definitely switched on by the fictional app."

    async def test_the_first_prose_answer_is_published_unchanged(self):
        model = Script([use(READ), say(self.ANSWER)])
        result, _ = await run(model, self.QUESTION, Hub("on"), Interaction(require_native_write_approval=True))
        self.assertEqual(model.rounds_seen, 2)
        self.assertEqual(result["answer"], self.ANSWER)
        for flag in ("source_review_invoked", "final_claim_audit_invoked",
                     "prewrite_model_review_invoked", "causal_follow_through_invoked",
                     "deadline_finalization_invoked", "action_approval_handoff_invoked",
                     "inventory_recovery_invoked", "action_follow_through_invoked"):
            self.assertFalse(result[flag], flag)
        self.assertEqual(result["answer_fallback_status"], "not_used")

    async def test_full_spends_more_rounds_on_the_same_script(self):
        model = Script([use(READ)] + [say(self.ANSWER)] * 5)
        result, _ = await run(model, self.QUESTION, Hub("on"), loop_profile="full")
        self.assertGreater(model.rounds_seen, 2)
        self.assertTrue(result["source_review_invoked"])

    async def test_an_empty_reply_gets_no_retry(self):
        model = Script([use(READ), say("")])
        result, _ = await run(model, "Which fictional lights are on?", Hub("on"))
        self.assertEqual(model.rounds_seen, 2)
        self.assertFalse(result["success"])


class WriteGates(unittest.IsolatedAsyncioTestCase):
    async def test_a_write_waits_for_a_card_and_a_decline_sends_nothing(self):
        hub = Hub("off")
        model = Script([use(READ), use(ON), say("You declined, so nothing was sent.")])
        result, cards = await run(model, "Turn on fictional lamp", hub,
                                  Interaction(require_native_write_approval=True), decide=False)
        self.assertEqual(len(cards), 1)
        self.assertNotIn("hub_manage_devices", [n for n, _ in hub.calls])
        self.assertIn("declined", result["answer"])

    async def test_an_approved_write_gets_a_model_answer_and_the_outcome_note(self):
        hub = Hub("off")
        model = Script([use(READ), use(ON), say("Hubitat accepted the on command.")])
        result, cards = await run(model, "Turn on fictional lamp", hub,
                                  Interaction(require_native_write_approval=True), decide=True)
        self.assertEqual(len(cards), 1)
        self.assertEqual([n for n, _ in hub.calls].count("hub_manage_devices"), 1)
        self.assertTrue(result["answer"].startswith("Hubitat accepted the on command."))
        self.assertIn("not independently verified", result["answer"])
        self.assertFalse(result["routine_action_fastpath"]["terminal_native_acceptance_used"])

    async def test_an_accepted_write_is_not_sent_twice(self):
        hub = Hub("off")
        model = Script([use(READ), use(ON), use(ON), say("Accepted once.")])
        result, cards = await run(model, "Turn on fictional lamp", hub,
                                  Interaction(require_native_write_approval=True), decide=True)
        self.assertEqual(len(cards), 1)
        self.assertEqual([n for n, _ in hub.calls].count("hub_manage_devices"), 1)
        self.assertIn("already accepted", result["tool_calls"][-1]["error"])

    async def test_already_in_state_sends_nothing(self):
        hub = Hub("on")
        model = Script([use(READ), use(ON), say("It is already on.")])
        result, cards = await run(model, "Turn on fictional lamp", hub,
                                  Interaction(require_native_write_approval=True), decide=True)
        self.assertEqual(cards, [])
        self.assertNotIn("hub_manage_devices", [n for n, _ in hub.calls])
        self.assertEqual(result["answer"], "It is already on.")

    async def test_with_no_approval_gate_no_native_write_is_sent(self):
        hub = Hub("off")
        model = Script([use(READ), use(ON), say("Not sent.")])
        result, _ = await run(model, "Turn on fictional lamp", hub)
        self.assertNotIn("hub_manage_devices", [n for n, _ in hub.calls])
        self.assertIn("confirmation is required", result["tool_calls"][-1]["error"])

    async def test_a_new_automation_without_a_current_read_is_refused(self):
        hub = Hub("off")
        rule = call("hub_manage_devices", {"tool": "hub_set_visual_rule",
                                           "args": {"name": "Fictional", "definition": {}}})
        model = Script([use(rule), say("I need to read the device first.")])
        result, cards = await run(model, "Make a rule for the fictional lamp", hub,
                                  Interaction(require_native_write_approval=True), decide=True)
        self.assertEqual(cards, [])
        self.assertEqual(hub.calls, [])
        self.assertEqual(result["tool_calls"][0]["result_kind"],
                         "persistent_write_missing_current_evidence")

    async def test_prose_without_a_command_is_kept_and_labelled(self):
        text = "I have turned on the fictional lamp."
        result, _ = await run(Script([say(text)]), "Turn on fictional lamp", Hub("off"),
                              Interaction(require_native_write_approval=True))
        self.assertEqual(result["answer"], text + "\n\n" + PLAIN_NO_COMMAND_NOTE)
        self.assertEqual(result["action_lifecycle"]["status"], "not_prepared")
        self.assertIsNone(result["unprepared_replaced_text"])


class ApprovalPolicy(unittest.IsolatedAsyncioTestCase):
    BATCH = {"commands": [{"command": "on", "deviceId": "5001"},
                          {"command": "on", "deviceId": "5002"}]}

    def script(self, write):
        return Script([use(call("hub_list_devices", {"format": "summary"})),
                       use(write), say("Hubitat accepted it.")])

    async def test_verified_lights_still_skip_the_card_when_the_option_is_on(self):
        for write in (command(**self.BATCH), command(deviceId="5001", command="on")):
            hub, gate = LightHub(), Interaction(require_native_write_approval=True,
                                                auto_approve_lights=True)
            _, cards = await run(self.script(write), "turn on the fictional lamps", hub, gate)
            self.assertEqual(cards, [])
            self.assertEqual(gate.routine_auto_approval_class, "verified_light_batch")
            self.assertEqual(len(writes(hub)), 1)

    async def test_lights_need_a_card_when_the_option_is_off(self):
        hub, gate = LightHub(), Interaction(require_native_write_approval=True)
        _, cards = await run(self.script(command(**self.BATCH)),
                             "turn on the fictional lamps", hub, gate, decide=False)
        self.assertEqual(len(cards), 1)
        self.assertEqual(writes(hub), [])

    async def test_a_second_light_write_needs_a_card(self):
        hub, gate = LightHub(), Interaction(require_native_write_approval=True,
                                            auto_approve_lights=True)
        model = Script([use(call("hub_list_devices", {"format": "summary"})),
                        use(command(deviceId="5001", command="on")),
                        use(command(deviceId="5002", command="on")), say("One sent.")])
        _, cards = await run(model, "turn on the hall lamp", hub, gate, decide=False)
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(writes(hub)), 1)

    async def test_internet_block_policy_follows_its_option(self):
        for enabled, expected_cards in ((True, 0), (False, 1)):
            hub = BlockHub()
            gate = Interaction(require_native_write_approval=True,
                               auto_approve_internet_block=enabled)
            model = Script([use(command(deviceId="7001", command="blockInternet")), say("Done.")])
            _, cards = await run(model, "block Fictional Gadget", hub, gate, decide=False)
            self.assertEqual(len(cards), expected_cards)
            self.assertEqual(len(writes(hub)), 1 - expected_cards)


class AskEndpoint(unittest.TestCase):
    def test_request_options_reach_the_agent_and_only_tighten_approval(self):
        import httpx
        import app as runtime

        seen = []

        class FakeModel:
            async def answer(self, question, history, mcp, seconds, before_call=None, **kwargs):
                gate = before_call.__self__
                seen.append((gate.auto_approve_lights, gate.auto_approve_internet_block,
                             gate.trusted_safe_switch_ids, gate.require_native_write_approval,
                             kwargs.get("loop_profile")))
                return {"success": True, "answer": "ok", "tool_calls": []}

        async def drive():
            runtime.app.state.options = {**runtime.DEFAULTS,
                                         "routine_auto_approve_safe_switch_ids": "12"}
            runtime.app.state.configuration_error = None
            runtime.app.state.mcp = object()
            runtime.app.state.model = FakeModel()
            runtime.app.state.ask_lock = asyncio.Lock()
            runtime.app.state.interactions = {}
            runtime.app.state.ask_tasks = {}
            runtime.app.state.device_monitor = None
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.app),
                                         base_url="http://test") as client:
                for extra in ({}, {"disable_auto_approval": True, "loop_profile": "plain"}):
                    reply = await client.post(
                        "/api/ask", headers={"X-Homebrain-Request": "1"},
                        json={"request_id": str(uuid4()), "question": "hi", **extra})
                    self.assertEqual(reply.status_code, 200, reply.text)
                bad = await client.post(
                    "/api/ask", headers={"X-Homebrain-Request": "1"},
                    json={"request_id": str(uuid4()), "question": "hi", "loop_profile": "none"})
                self.assertEqual(bad.status_code, 422)

        saved = dict(runtime.app.state._state)
        try:
            asyncio.run(drive())
        finally:
            runtime.app.state._state.clear()
            runtime.app.state._state.update(saved)
        self.assertEqual(seen, [(True, True, frozenset({"12"}), True, None),
                                (False, False, frozenset(), True, "plain")])


if __name__ == "__main__":
    unittest.main()

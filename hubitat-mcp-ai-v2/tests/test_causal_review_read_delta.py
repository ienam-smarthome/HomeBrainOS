"""Alpha.140: a contextual read must not consume causal follow-through.

Fictional cross-domain source receipts only; this test suite makes no
Hubitat/cloud calls, executes no writes, and never infers a controller cause.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_review import (
    causal_review_read_delta, should_recheck_causal_evidence,
)


def envelope(native):
    return {"content": [{"type": "text", "text": json.dumps(native)}]}


def original(name, arguments, native=None, success=True):
    return {"name": name, "arguments": arguments, "success": success,
            "response": json.dumps(envelope(native or {})),
            "result_kind": "tool_result"}


HISTORY = {
    "source": "device", "deviceId": "FICT-OUTPUT",
    "device": "Fictional controlled output",
    "events": [
        {"name": "switch", "value": "off", "type": "event",
         "date": "2030-11-17T09:10:02+0000",
         "producedBy": {"deviceId": "FICT-BRIDGE"},
         "triggered": [{"appId": 401}]},
        {"name": "switch", "value": "on", "type": "event",
         "date": "2030-11-17T09:05:00+0000",
         "producedBy": {"deviceId": "FICT-BRIDGE"}},
    ],
}
LOG = {"mode": "past", "entries": [
    {"time": "2030-11-17 09:10:00.000", "type": "app",
     "message": "app|401|Fictional Controller|Execution decision observed"}
]}
ARGS = {"deviceId": "FICT-OUTPUT", "attribute": "switch", "limit": 20}
LOGARGS = {"appId": "401", "mode": "past",
           "since": "2030-11-17T09:00:00+0000",
           "until": "2030-11-17T09:15:00+0000"}


class DeltaClassifierTests(unittest.TestCase):
    def test_one_successful_generic_metadata_read_is_not_discriminating(self):
        baseline = [original("hub_list_device_events", ARGS, HISTORY)]
        for name in ("hub_get_info", "hub_list_modes", "hub_list_devices",
                     "hub_get_device", "hub_get_app_config"):
            with self.subTest(name=name):
                x = causal_review_read_delta(
                    baseline + [original(name, {}, {"success": True})], 1)
                self.assertTrue(x["only_contextual_or_unsuccessful_reads"])
                self.assertEqual(x["contextual_read_names"], [name])
                self.assertEqual(x["potential_event_time_read_count"], 0)

    def test_successful_history_and_original_past_log_are_potential_sources(self):
        baseline = [original("hub_list_device_events", ARGS, HISTORY)]
        for item in (
            original("hub_list_device_events", ARGS, HISTORY),
            original("hub_get_logs", LOGARGS, LOG),
        ):
            with self.subTest(name=item["name"]):
                x = causal_review_read_delta(baseline + [item], 1)
                self.assertFalse(x["only_contextual_or_unsuccessful_reads"])
                self.assertEqual(x["potential_event_time_read_count"], 1)
                self.assertTrue(x["potential_source_type_is_not_causal_proof"])

    def test_empty_log_or_failed_read_does_not_count_as_evidence(self):
        baseline = [original("hub_list_device_events", ARGS, HISTORY)]
        for item in (
            original("hub_get_logs", LOGARGS, {"mode": "past", "entries": []}),
            original("hub_get_logs", {**LOGARGS, "mode": "live"}, LOG),
            original("hub_list_device_events", ARGS, {**HISTORY, "events": []}),
            original("hub_get_logs", LOGARGS, LOG, success=False),
        ):
            with self.subTest(item=item):
                x = causal_review_read_delta(baseline + [item], 1)
                self.assertTrue(x["only_contextual_or_unsuccessful_reads"])
                self.assertEqual(x["potential_event_time_read_count"], 0)

    def test_unknown_future_tool_is_conservatively_not_assumed_useless(self):
        x = causal_review_read_delta(
            [original("hub_future_native_input_history", {"id": "X"},
                      {"payload": "anything"})], 0)
        self.assertEqual(x["unclassified_read_count"], 1)
        self.assertFalse(x["only_contextual_or_unsuccessful_reads"])

    def test_bounds_malformed_arguments_and_identity(self):
        self.assertEqual(causal_review_read_delta([], 2)["status"], "unavailable")
        self.assertFalse(causal_review_read_delta([], 2)[
            "only_contextual_or_unsuccessful_reads"])
        x = causal_review_read_delta(
            [original("hub_list_device_events",
                      {**ARGS, "deviceId": "OTHER"}, HISTORY)], 0)
        self.assertEqual(x["potential_event_time_read_count"], 0)
        self.assertTrue(x["only_contextual_or_unsuccessful_reads"])
        many = [original("hub_get_info", {}, {})] * 33
        self.assertEqual(causal_review_read_delta(many, 0)["status"], "too_many_reads")

    def test_follow_through_changes_only_when_review_delta_is_context_only(self):
        opts = dict(
            question="Why did the fictional output turn off?",
            review_kind_name="causal",
            first_review_receipt_count=1, receipt_count=2,
            already_rechecked=False,
            candidate_answer="The internal initiating decision remains unknown.",
            remaining_seconds=80, has_action_receipt=False,
            available_read_tools=True,
        )
        self.assertFalse(should_recheck_causal_evidence(**opts))
        context = causal_review_read_delta(
            [original("hub_list_device_events", ARGS, HISTORY),
             original("hub_get_info", {}, {"status": "ok"})], 1)
        self.assertTrue(should_recheck_causal_evidence(
            **opts, review_read_delta=context))
        for override in (
            {"remaining_seconds": 25},
            {"already_rechecked": True},
            {"candidate_answer": "A command issuer and cause were independently verified."},
            {"question": "Why did this happen? Do not make any further reads."},
            {"available_read_tools": False},
            {"has_action_receipt": True},
        ):
            with self.subTest(override=override):
                self.assertFalse(should_recheck_causal_evidence(
                    **{**opts, **override}, review_read_delta=context))
        verified = causal_review_read_delta(
            [original("hub_list_device_events", ARGS, HISTORY),
             original("hub_get_logs", LOGARGS, LOG)], 1)
        self.assertFalse(should_recheck_causal_evidence(
            **opts, review_read_delta=verified))


class FictionalHub:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_device_events", "inputSchema": {
                "type": "object", "properties": {
                    "deviceId": {"type": "string"}, "attribute": {"type": "string"},
                    "limit": {"type": "integer"}}}},
            {"name": "hub_get_info", "inputSchema": {
                "type": "object", "properties": {}}},
            {"name": "hub_get_logs", "inputSchema": {
                "type": "object", "properties": {
                    "appId": {"type": "string"}, "mode": {"type": "string"},
                    "since": {"type": "string"}, "until": {"type": "string"}}}},
            {"name": "hub_manage_apps", "inputSchema": {
                "type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_device_events":
            return envelope(HISTORY)
        if name == "hub_get_info":
            return envelope({"hubName": "Fixture Hub"})
        if name == "hub_get_logs":
            return envelope(LOG)
        raise AssertionError("Unexpected write/unknown tool call")


def tool(name, args):
    return {"content": "", "tool_calls": [
        {"function": {"name": name, "arguments": args}}]}


class ScriptedAgent(Agent):
    def __init__(self, *replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.replies = list(replies)
        self.seen = []
        self.offered = []

    async def round(self, messages, tools, remaining):
        self.seen.append([dict(m) for m in messages])
        self.offered.append([t["function"]["name"] for t in tools])
        if not self.replies:
            raise AssertionError("Unexpected extra model round")
        return self.replies.pop(0)


class ModelLedIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_after_hub_metadata_only_model_may_read_execution_source(self):
        hub = FictionalHub()
        agent = ScriptedAgent(
            tool("hub_list_device_events", ARGS),
            {"content": "Fictional output reported off."},
            tool("hub_get_info", {}),
            {"content": "Output off reported, but the cause remains unknown."},
            tool("hub_get_logs", LOGARGS),
            {"content": "The output reported off. The fixture controller "
                        "logged a decision near that report. Which input "
                        "prompted it remains unverified."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional output switch off? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["causal_follow_through_invoked"])
        self.assertEqual(result["rounds"], 6)
        self.assertEqual([c[0] for c in hub.calls],
                         ["hub_list_device_events", "hub_get_info", "hub_get_logs"])
        self.assertEqual(result["causal_review_source_delta_at_follow_through"][
            "contextual_read_names"], ["hub_get_info"])
        self.assertIn("Original review-read source-category delta",
                      agent.seen[4][-1]["content"])
        self.assertNotIn("hub_manage_apps", agent.offered[4])
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])

    async def test_model_can_decline_follow_through_after_context_read(self):
        hub = FictionalHub()
        agent = ScriptedAgent(
            tool("hub_list_device_events", ARGS),
            {"content": "The output reported off."},
            tool("hub_get_info", {}),
            {"content": "The initiator is unknown."},
            {"content": "The output reported off; the initiating cause "
                        "remains unverified."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional output turn off? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertEqual(result["rounds"], 5)
        self.assertTrue(result["causal_follow_through_invoked"])
        self.assertEqual(len(hub.calls), 2)
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])

    async def test_a_relevant_event_time_read_does_not_force_follow_through(self):
        hub = FictionalHub()
        agent = ScriptedAgent(
            tool("hub_list_device_events", ARGS),
            {"content": "The output reported off."},
            tool("hub_get_logs", LOGARGS),
            {"content": "An app execution was reported; the exact cause "
                        "remains unverified."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional output turn off? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertFalse(result["causal_follow_through_invoked"])
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(len(hub.calls), 2)
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])


if __name__ == "__main__":
    unittest.main()

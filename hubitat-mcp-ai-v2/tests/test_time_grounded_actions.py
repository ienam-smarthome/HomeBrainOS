"""Alpha.80: entirely fictional time-source, action and error regressions.

No real Hubitat, router, model API, timers or device writes are used.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from action_proposal_review import PREWRITE_PROPOSAL_PROMPT
from investigation_review import ACTION_OUTCOME_REVIEW_PROMPT, is_read_only_review_tool
from time_evidence import (
    TOOL_NAME, clock_facts, deadline_facts, hub_clock_source, reported_hub_skew,
    write_hub_clock_skew,
)
from write_receipt_evidence import (
    model_error_kind, write_failure_evidence, matches_prior_written_target,
)


def at(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def native(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class ClockEvidenceTests(unittest.TestCase):
    def test_london_gmt_short_target(self):
        now = at("2026-11-13T00:46:00Z")
        result = clock_facts({"time_of_day": "01:00"}, now=now)
        self.assertEqual(result["hub_timezone"], "Europe/London")
        self.assertEqual(result["source"], "client clock")
        self.assertFalse(result["hub_clock_independently_read"])
        self.assertEqual(result["utc_offset_seconds"], 0)
        self.assertFalse(result["dst_active"])
        self.assertEqual(result["target"]["whole_minutes_ahead"], 14)
        self.assertFalse(result["target"]["today_occurrence_passed"])

    def test_london_bst(self):
        now = at("2026-07-01T22:46:00Z")  # 23:46 BST
        result = clock_facts({"time_of_day": "00:10"}, now=now)
        self.assertEqual(result["utc_offset_seconds"], 3600)
        self.assertTrue(result["dst_active"])
        self.assertEqual(result["target"]["whole_minutes_ahead"], 24)
        self.assertTrue(result["target"]["today_occurrence_passed"])
        self.assertEqual(result["target"]["target_local"][:10], "2026-07-02")

    def test_spring_forward_nonexistent_and_post_transition(self):
        now = at("2026-03-29T00:45:00Z")
        with self.assertRaisesRegex(ValueError, "does not exist"):
            clock_facts({"local_datetime": "2026-03-29T01:30"}, now=now)
        result = clock_facts({"local_datetime": "2026-03-29T02:30"}, now=now)
        self.assertEqual(result["target"]["whole_minutes_ahead"], 45)
        self.assertIn("+01:00", result["target"]["target_local"])

    def test_autumn_ambiguous_needs_fold(self):
        now = at("2026-10-25T00:45:00Z")  # 01:45 BST
        target = {"local_datetime": "2026-10-25T01:50"}
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            clock_facts(target, now=now)
        early = clock_facts({**target, "fold": 0}, now=now)
        late = clock_facts({**target, "fold": 1}, now=now)
        self.assertEqual(early["target"]["whole_minutes_ahead"], 5)
        self.assertEqual(late["target"]["whole_minutes_ahead"], 65)
        self.assertNotEqual(early["target"]["target_utc"], late["target"]["target_utc"])

    def test_fixed_past_target_and_imminent(self):
        now = at("2026-11-13T00:46:00Z")
        past = clock_facts({"local_datetime": "2026-11-13T00:10"}, now=now)
        self.assertTrue(past["target"]["past"])
        self.assertEqual(past["target"]["whole_minutes_ahead"], -36)
        imminent = clock_facts({"local_datetime": "2026-11-13T00:46:30"}, now=now)
        self.assertEqual(imminent["target"]["whole_minutes_ahead"], 0)
        self.assertTrue(imminent["target"]["too_imminent_under_60s"])

    def test_timezone_aware_target(self):
        now = at("2026-06-30T22:00:00Z")
        result = clock_facts({"instant": "2026-07-01T00:10:00+01:00"}, now=now)
        self.assertEqual(result["target"]["whole_minutes_ahead"], 70)
        self.assertEqual(result["target"]["target_utc"], "2026-06-30T23:10:00+00:00")

    def test_structured_contract_does_not_parse_user_prompt(self):
        self.assertTrue(is_read_only_review_tool(TOOL_NAME))
        with self.assertRaisesRegex(ValueError, "Unexpected clock"):
            clock_facts({"question": "Switch Fictional Relay off at 1am"})
        self.assertNotIn("question", clock_facts({}, now=at("2026-11-13T00:00:00Z")))
        self.assertIn("source", clock_facts({}, now=at("2026-11-13T00:00:00Z")))

    def test_hub_source_requires_explicit_info_and_reports_skew(self):
        doc = native({"hub": {"timeZone": "Europe/London",
                              "serverTime": "2026-11-13T01:03:00Z"}})
        self.assertIsNone(hub_clock_source("hub_list_apps", doc))
        src = hub_clock_source("hub_get_info", doc)
        self.assertEqual(src["timezone"], "Europe/London")
        skew = reported_hub_skew(src, now=at("2026-11-13T01:00:00Z"))
        self.assertEqual(skew["hub_minus_client_seconds"], 180)
        self.assertIsNone(reported_hub_skew(src, now=at("2026-11-13T01:02:55Z")))

    def test_write_receipt_skew_requires_explicit_server_clock(self):
        now = at("2026-11-13T00:46:00Z")
        self.assertEqual(write_hub_clock_skew(native({
            "success": True, "serverTime": "2026-11-13T00:49:00Z",
        }), now=now)["hub_minus_client_seconds"], 180)
        self.assertIsNone(write_hub_clock_skew(native({
            "success": True, "lastEventAt": "2026-11-13T00:49:00Z",
        }), now=now))

    def test_deadline_future_only_and_not_a_readback(self):
        now = at("2026-11-13T00:46:00Z")
        good = deadline_facts(native({
            "success": True, "state": {"pendingBlockUntil": "2026-11-13T03:16:00Z"},
            "generatedAt": "2026-11-13T00:46:00Z",
        }), now=now)
        self.assertEqual(good["offset_from_client_now_minutes"], 150)
        self.assertFalse(good["independent_post_write_readback"])
        self.assertIsNone(deadline_facts(native({
            "success": True, "generatedAt": "2026-11-13T03:16:00Z",
        }), now=now))
        self.assertIsNone(deadline_facts(native({
            "success": True, "state": {"pendingBlockUntil": "not a timestamp"},
        }), now=now))
        self.assertEqual(deadline_facts(native({
            "attribute": "pendingUntil", "value": "2026-11-13T01:00:00Z",
        }), now=now)["offset_from_client_now_minutes"], 14)

    def test_gateway_read_after_write_is_a_separate_read(self):
        write = {
            "name": "hub_call_device_command",
            "arguments": {"deviceId": "FICTIONAL-RELAY", "command": "deferCutoff",
                          "parameters": ["2"]},
            "success": True, "possible_native_action": True,
            "result_kind": "tool_result",
            "response": json.dumps(native({"success": True, "accepted": True})),
        }
        read = {
            "name": "hub_read_devices",
            "arguments": {"tool": "hub_get_device_attribute", "args": {
                "deviceId": "FICTIONAL-RELAY", "attribute": "pendingUntil"}},
            "success": True, "result_kind": "tool_result",
            "response": json.dumps(native({
                "attribute": "pendingUntil", "value": "2026-11-13T03:16:00Z",
            })),
        }
        report = write_failure_evidence([write, read])
        self.assertEqual(len(report["executed_writes"]), 1)
        self.assertEqual(len(report["post_write_reads"]), 1)
        self.assertTrue(report["post_write_reads"][0]["same_explicit_target_id_as_prior_write"])
        self.assertFalse(matches_prior_written_target(
            [write], {"deviceId": "FICTIONAL-DIFFERENT"}))
        self.assertEqual(report["post_write_reads"][0]["reported_values"]["pendingUntil"],
                         "2026-11-13T03:16:00Z")

    def test_error_kind(self):
        self.assertEqual(model_error_kind("Model API returned HTTP 402"),
                         "quota_or_billing")
        self.assertEqual(model_error_kind("Model API returned HTTP 429"), "rate_limit")
        self.assertEqual(model_error_kind("Model API returned HTTP 503"), "other")
        self.assertIn("requested", ACTION_OUTCOME_REVIEW_PROMPT.lower())
        self.assertIn("read-only CLIENT clock", PREWRITE_PROPOSAL_PROMPT)


class FakeNative:
    def __init__(self):
        self.calls = []
        self.deadline = (datetime.now(UTC) + timedelta(minutes=150)).isoformat()
        self.catalog = [
            {"name": "hub_call_device_command", "inputSchema": {"type": "object"}},
            {"name": "hub_get_device_attribute", "inputSchema": {"type": "object"}},
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "hub_call_device_command":
            return native({"success": True, "accepted": True,
                           "deviceId": arguments.get("deviceId"),
                           "command": arguments.get("command"),
                           "state": {"pendingUntil": self.deadline}})
        if name == "hub_get_device_attribute":
            return native({"deviceId": arguments.get("deviceId"),
                           "attribute": "pendingUntil", "value": self.deadline})
        raise AssertionError("Unexpected native tool")


def command(minutes):
    return {"function": {"name": "hub_call_device_command", "arguments": {
        "deviceId": "FICTIONAL-RELAY", "command": "deferCutoff",
        "parameters": [str(minutes)],
    }}}


def msg(*, calls=None, content=""):
    return {"content": content, "tool_calls": calls or []}


class ScriptedAgent(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fake", "", 10)
        self.script = list(script)
        self.offered = []
        self.messages_seen = []

    async def round(self, messages, tools, remaining):
        self.offered.append([item["function"]["name"] for item in tools])
        self.messages_seen.append([dict(x) for x in messages])
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TimeActionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_clock_offered_and_prewrite_argument_delta_traced(self):
        hub = FakeNative()
        assistant = ScriptedAgent([
            msg(calls=[command(120)]),
            msg(calls=[{"function": {"name": TOOL_NAME,
                                    "arguments": {"time_of_day": "01:00"}}}]),
            msg(calls=[command(150)]),
            msg(content="Driver accepted an unverified 150-minute delay."),
        ])
        async def permit(name, arguments, explanation):
            return None
        try:
            result = await assistant.answer(
                "Disconnect my fictional relay at 01:00 tonight", [], hub, 90,
                before_call=permit, enable_source_review=False,
            )
        finally:
            await assistant.close()
        self.assertTrue(result["prewrite_model_review_invoked"])
        self.assertTrue(result["prewrite_dispatch_changed"])
        evidence = result["prewrite_dispatch_comparison"]
        self.assertEqual(evidence["reviewed_unexecuted_proposal"]["arguments"]
                         ["parameters"], ["120"])
        self.assertEqual(evidence["selected_for_native_dispatch"]["arguments"]
                         ["parameters"], ["150"])
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(hub.calls[0][1]["parameters"], ["150"])
        self.assertEqual(result["tool_calls"][0]["result_kind"], "local_clock_read")
        self.assertEqual(result["tool_calls"][1]["deadline_facts"]
                         ["independent_post_write_readback"], False)
        self.assertIn("client_write_snapshot_scope", result["tool_calls"][1]["response"])

    async def test_identical_review_and_dispatch_not_marked_changed(self):
        hub = FakeNative()
        assistant = ScriptedAgent([
            msg(calls=[command(120)]),
            msg(calls=[command(120)]),
            msg(content="Native operation returned; later cutoff remains unknown."),
        ])
        async def permit(name, arguments, explanation):
            return None
        try:
            result = await assistant.answer(
                "Disconnect the fictional relay in two hours", [], hub, 90,
                before_call=permit, enable_source_review=False,
            )
        finally:
            await assistant.close()
        self.assertFalse(result["prewrite_dispatch_changed"])
        self.assertEqual(len(hub.calls), 1)

    async def test_402_after_write_and_separate_read_preserves_both(self):
        hub = FakeNative()
        assistant = ScriptedAgent([
            msg(calls=[command(150)]),
            msg(calls=[{"function": {"name": "hub_get_device_attribute",
                                    "arguments": {"deviceId": "FICTIONAL-RELAY",
                                                  "attribute": "pendingUntil"}}}]),
            RuntimeError("Model API returned HTTP 402"),
        ])
        try:
            result = await assistant.answer("Set the fictional timer", [], hub,
                                            90, enable_source_review=False)
        finally:
            await assistant.close()
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "model")
        self.assertEqual(result["model_error_kind"], "quota_or_billing")
        self.assertEqual(len(result["executed_writes"]), 1)
        self.assertEqual(result["executed_writes"][0]["command"], "deferCutoff")
        self.assertIs(result["executed_writes"][0]["accepted"], True)
        self.assertEqual(len(result["post_write_reads"]), 1)
        self.assertIn("pendingUntil", result["post_write_reads"][0]["reported_values"])
        self.assertTrue(result["tool_calls"][1]["deadline_facts"]
                        ["independent_post_write_readback"])
        self.assertTrue(result["tool_calls"][1]["deadline_facts"]
                        ["target_identity_match_verified"])
        self.assertIn("NOT written by the model", result["answer"])
        self.assertIn("pendingUntil", result["answer"])
        self.assertIn("must not be automatically retried", result["answer"])
        self.assertEqual([x[0] for x in hub.calls],
                         ["hub_call_device_command", "hub_get_device_attribute"])

    async def test_402_before_write_keeps_old_error_shape(self):
        hub = FakeNative()
        assistant = ScriptedAgent([RuntimeError("Model API returned HTTP 402")])
        try:
            result = await assistant.answer("Read a device", [], hub, 90,
                                            enable_source_review=False)
        finally:
            await assistant.close()
        self.assertFalse(result["success"])
        self.assertEqual(result["model_error_kind"], "quota_or_billing")
        self.assertNotIn("executed_writes", result)
        self.assertNotIn("Client-generated", result["answer"])
        self.assertEqual(hub.calls, [])

    async def test_429_after_write_maps_rate_limit_without_retry(self):
        hub = FakeNative()
        assistant = ScriptedAgent([
            msg(calls=[command(2)]),
            RuntimeError("Model API returned HTTP 429"),
        ])
        try:
            result = await assistant.answer("Send fictional command", [], hub, 90,
                                            enable_source_review=False)
        finally:
            await assistant.close()
        self.assertEqual(result["model_error_kind"], "rate_limit")
        self.assertEqual(len(result["executed_writes"]), 1)
        self.assertEqual(len(hub.calls), 1)


if __name__ == "__main__":
    unittest.main()

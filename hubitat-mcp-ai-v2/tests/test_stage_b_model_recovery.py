"""V2 Stage B end-to-end scripted model-choice and capped read recovery.

All identities are fictional; no live MCP, cloud provider or device writes.
The test checks model-owned tool selection, not correctness of a real cause.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from test_stage_b_ranked_frontier import (
    EVENTS, LOGS, WRITER, inventory, receipt, output_history, zero_broad,
)


INVENTORY = {
    "type": "function", "function": {
        "name": "hub_list_devices",
        "parameters": {"type": "object", "properties": {
            "format": {"type": "string"},
            "labelFilter": {"type": "string"},
        }},
    },
}


APP_CONFIG = {
    "type": "function", "function": {
        "name": "hub_get_app_config",
        "parameters": {"type": "object", "properties": {
            "appId": {"type": "integer"},
        }, "required": ["appId"]},
    },
}


def tool(name, args):
    return {"content": "", "tool_calls": [
        {"function": {"name": name, "arguments": args}}]}


class FakeHub:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        tools = []
        for tooldef in (INVENTORY, EVENTS, LOGS, APP_CONFIG, WRITER):
            f = tooldef["function"]
            tools.append({"name": f["name"], "inputSchema": f["parameters"]})
        return tools

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_devices":
            wrapper = json.loads(inventory()["response"])
            if args.get("labelFilter"):
                data = json.loads(wrapper["content"][0]["text"])
                data["devices"] = [
                    device for device in data["devices"]
                    if device["label"].startswith("Fixture sensor")
                ]
                data["count"] = len(data["devices"])
                wrapper["content"][0]["text"] = json.dumps(data)
            return wrapper
        if name == "hub_list_device_events":
            original = output_history()
            if "attribute" not in args:
                wrapper = json.loads(original["response"])
                data = json.loads(wrapper["content"][0]["text"])
                data["events"].append({
                    "name":"command-setHeatingSetpoint", "type":"command",
                    "date":"2030-11-17T07:58:30.000+00:00",
                    "producedBy":{"appId":613},
                })
                wrapper["content"][0]["text"] = json.dumps(data)
                return wrapper
            return json.loads(original["response"])
        if name == "hub_get_app_config":
            return json.loads(receipt(name, args, {
                "app": {"id": args["appId"], "label": "Fixture demand coordinator"},
            })["response"])
        if name == "hub_get_logs":
            if args.get("appId") is None:
                return json.loads(zero_broad()["response"])
            if str(args["appId"]) == "613":
                return json.loads(receipt(
                    "hub_get_logs", args,
                    {"mode":"past","matched":1,"entries":[{
                        "type":"app",
                        "time":"2030-11-17 07:58:29.000",
                        "message":"app|613|Fixture demand coordinator|Input A requested output"
                    }]}
                )["response"])
            return json.loads(receipt(
                "hub_get_logs", args,
                {"mode":"past","matched":0,"entries":[]}
            )["response"])
        raise AssertionError("A writer was selected")


class FakeAgent(Agent):
    def __init__(self, *responses):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.responses = list(responses)
        self.messages_seen = []
        self.tool_choices_seen = []

    async def round(self, messages, tools, remaining):
        self.messages_seen.append([dict(m) for m in messages])
        self.tool_choices_seen.append(
            [tool["function"]["name"] for tool in tools])
        if not self.responses:
            raise AssertionError("unexpected model round")
        return self.responses.pop(0)


FILTERED = {"deviceId":"4382","attribute":"thermostatOperatingState",
            "limit":10}
UNFILTERED = {"deviceId":"4382","limit":30,
              "since":"2030-11-17T07:48:47.423+00:00",
              "until":"2030-11-17T08:02:49.222+00:00"}
SCOPED = {"appId":613,"mode":"past",
          "since":"2030-11-17T07:48:47.423+00:00",
          "until":"2030-11-17T08:02:49.222+00:00",
          "limit":60}


class ModelSelectedRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_scoped_recovery_after_empty_broad_log(self):
        hub = FakeHub()
        model = FakeAgent(
            tool("hub_list_device_events", FILTERED),
            tool("hub_get_logs", {"mode":"past",
                                  "since":"2030-11-17T07:50:00+00:00",
                                  "until":"2030-11-17T08:10:00+00:00"}),
            {"content":"The device room initiated demand."},
            {"content":"The source room was the device grouping."},
            {"content":"The grouping was the cause."},
            tool("hub_list_device_events", UNFILTERED),
            tool("hub_get_logs", SCOPED),
            {"content": "The fixture thermostat reported heating. An "
                        "original command row named application 613 as a "
                        "proximal issuer. Its historical application log "
                        "mentioned Input A. The physical boiler outcome "
                        "remains unverified."},
        )
        try:
            answer = await model.answer(
                "Why did the fixture thermostat report heating, and which "
                "input requested it? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertTrue(answer["stage_b_scoped_recovery"]["invoked"])
        self.assertEqual(answer["stage_b_scoped_recovery"]["read_attempts"],2)
        self.assertEqual(answer["stage_b_scoped_recovery"][
            "app_scoped_read_attempts"],1)
        self.assertEqual([name for name, _ in hub.calls], [
            "hub_list_device_events", "hub_get_logs",
            "hub_list_device_events", "hub_get_logs"])
        self.assertNotIn("hub_call_device_command", model.tool_choices_seen[-3])
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])
        self.assertIn("application 613", answer["answer"])
        self.assertEqual(answer["causal_claim_verification"]["status"],"passed")
        self.assertTrue(any(
            "Stage B last scoped read opportunity" in m.get("content","")
            for round_messages in model.messages_seen
            for m in round_messages
        ))

    async def test_alpha142_inventory_history_inventory_replay(self):
        hub = FakeHub()
        initial_inventory = {"format": "summary"}
        focused_inventory = {"labelFilter": "Fixture sensor", "format": "summary"}
        model = FakeAgent(
            tool("hub_list_devices", initial_inventory),
            tool("hub_list_device_events", FILTERED),
            tool("hub_list_devices", focused_inventory),
            {"content": "The grouping initiated the request."},
            {"content": "The grouping was the input."},
            {"content": "The thermostat reported heating; the input is unknown."},
            tool("hub_list_device_events", UNFILTERED),
            {"content": "The latest thermostat heating report was at 07:58:47 UTC. "
                        "The initiating input remains unknown."},
        )
        try:
            answer = await model.answer(
                "Why did the fixture thermostat report heating, and which "
                "input requested it? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
                enable_compute_nudge=False,
            )
        finally:
            await model.close()

        self.assertEqual(hub.calls, [
            ("hub_list_devices", initial_inventory),
            ("hub_list_device_events", FILTERED),
            ("hub_list_devices", focused_inventory),
            ("hub_list_device_events", UNFILTERED),
        ])
        recovery = answer["stage_b_scoped_recovery"]
        self.assertTrue(recovery["invoked"])
        self.assertEqual(recovery["read_attempts"], 1)
        self.assertEqual(recovery["app_scoped_read_attempts"], 0)
        self.assertEqual(recovery["candidates"][0], {
            "rank": 1,
            "category": "same_output_unfiltered_command_and_state_history",
            "leaf": "hub_list_device_events",
            "status": "selected",
        })
        self.assertTrue(all(candidate["status"] == "not_selected"
                            for candidate in recovery["candidates"][1:]))
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])

    async def test_alpha144_issuer_known_but_upstream_demand_unresolved(self):
        hub = FakeHub()
        initial_inventory = {"format": "summary"}
        config_args = {"appId": 613}
        model = FakeAgent(
            tool("hub_list_devices", initial_inventory),
            tool("hub_list_device_events", FILTERED),
            {"content": "The fixture thermostat reported heating."},
            {"content": "The demand source remains unknown."},
            tool("hub_list_device_events", UNFILTERED),
            tool("hub_get_app_config", config_args),
            {"content": "Application 613 triggered heating because Input A demanded it."},
            tool("hub_get_logs", SCOPED),
            {"content": "The fixture thermostat reported heating. App 613 issued a "
                        "setpoint command. Its past log recorded a request by Input A."},
        )
        try:
            answer = await model.answer(
                "Why did the fixture thermostat report heating, and which input "
                "requested it? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await model.close()

        self.assertEqual(hub.calls, [
            ("hub_list_devices", initial_inventory),
            ("hub_list_device_events", FILTERED),
            ("hub_list_device_events", UNFILTERED),
            ("hub_get_app_config", config_args),
            ("hub_get_logs", SCOPED),
        ])
        recovery = answer["stage_b_scoped_recovery"]
        self.assertTrue(recovery["invoked"])
        self.assertIsNone(recovery["suppression_reason"])
        self.assertEqual(recovery["read_attempts"], 1)
        self.assertEqual(recovery["app_scoped_read_attempts"], 1)
        self.assertEqual(recovery["candidates"][0], {
            "rank": 1,
            "category": "recorded_command_issuer_app_log",
            "leaf": "hub_get_logs",
            "status": "selected",
        })
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])

    async def test_model_can_decline_recovery_without_fabricating_cause(self):
        hub = FakeHub()
        model = FakeAgent(
            tool("hub_list_device_events", FILTERED),
            tool("hub_get_logs", {"mode":"past",
                                  "since":"2030-11-17T07:50:00+00:00",
                                  "until":"2030-11-17T08:10:00+00:00"}),
            {"content":"The device grouping is the initiating input."},
            {"content":"The current device grouping is the input."},
            {"content":"The input is definitely the room label."},
            {"content":"The device reported heating. The input remains unknown."},
        )
        try:
            answer = await model.answer(
                "Why did the fixture heater turn on, and which input "
                "requested it? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertTrue(answer["stage_b_scoped_recovery"]["invoked"])
        self.assertEqual(answer["stage_b_scoped_recovery"]["read_attempts"],0)
        self.assertEqual(len(hub.calls),2)
        self.assertEqual(answer["stage_b_scoped_recovery"]["result"], "model_declined")
        self.assertEqual(answer["stage_b_scoped_recovery"]["candidates"][0]["status"],
                         "declined")
        self.assertEqual(answer["causal_claim_verification"]["reason"],
                         "original_event_time_causal_sources_insufficient")
        self.assertEqual(answer["answer_fallback_status"],
                         "causal_claim_publication_floor")
        self.assertNotIn("definitely", answer["answer"])
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])

    async def test_no_recovery_when_user_forbids_further_native_reads(self):
        hub = FakeHub()
        model = FakeAgent(
            tool("hub_list_device_events", FILTERED),
            tool("hub_get_logs", {"mode":"past",
                                  "since":"2030-11-17T07:50:00+00:00",
                                  "until":"2030-11-17T08:10:00+00:00"}),
            {"content":"Unknown initiating input."},
            {"content":"Still unknown; current source has no issuer."},
        )
        try:
            answer = await model.answer(
                "Why did the fixture heater start, and which source? "
                "Do not make further reads.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        recovery = answer["stage_b_scoped_recovery"]
        self.assertFalse(recovery["invoked"])
        self.assertEqual(recovery["suppression_reason"], "user_disallowed_fresh_reads")
        self.assertEqual(recovery["candidates"][0]["status"], "suppressed")
        self.assertEqual(len(hub.calls),2)
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])


if __name__ == "__main__":
    unittest.main()

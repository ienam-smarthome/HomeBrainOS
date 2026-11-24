"""End-to-end: the model calls homebrain_compute_receipt inside the agent loop."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent  # noqa: E402


DEVICES = ([{"id": str(i), "label": f"S{i}", "battery": b}
            for i, b in enumerate([80, 85, 90, 94, 94, 80, 79, 95])]
           + [{"id": f"n{i}", "label": f"N{i}"} for i in range(5)])


class Hub:
    def __init__(self):
        self.calls = []
        self.catalog = [{"name": "hub_list_devices",
                         "inputSchema": {"type": "object", "properties": {}}}]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, args))
        assert name == "hub_list_devices", "compute must never reach the hub"
        return {"content": [{"type": "text", "text": json.dumps({"devices": DEVICES})}]}


class Scripted(Agent):
    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 15)
        self.script = list(script)
        self.tool_messages = []

    async def round(self, messages, tools, remaining):
        self.tool_messages.append([m for m in messages if m.get("role") == "tool"])
        return self.script.pop(0)


def call(name, args):
    return {"function": {"name": name, "arguments": args}}


class ComputeInsideAgentLoop(unittest.IsolatedAsyncioTestCase):
    async def test_model_computes_instead_of_counting(self):
        hub = Hub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "operation": "count",
                "where": [{"field": "battery", "op": "gte", "value": 80},
                          {"field": "battery", "op": "lte", "value": 94}]})]},
            {"content": "Exactly 6 returned devices have battery 80-94.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("which devices have battery between 80 and 94?", [], hub, 60)
        finally:
            await agent.close()
        self.assertTrue(reply["success"])
        self.assertEqual(hub.calls, [("hub_list_devices", {})])
        names = [c["name"] for c in reply["tool_calls"]]
        self.assertEqual(names, ["hub_list_devices", "homebrain_compute_receipt"])
        compute_rec = reply["tool_calls"][1]
        self.assertTrue(compute_rec["success"])
        self.assertEqual(compute_rec["result_kind"], "local_compute")
        self.assertFalse(compute_rec["operation_executed"])
        # the model was actually handed the exact computed count
        last_tool_msg = agent.tool_messages[-1][-1]["content"]
        self.assertEqual(json.loads(last_tool_msg)["local_computation"]["count"], 6)

    async def test_large_result_carries_structural_hint_with_true_receipt_index(self):
        hub = Hub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "done", "tool_calls": []},
        ])
        try:
            await agent.answer("list my devices", [], hub, 60, enable_compute_nudge=False)
        finally:
            await agent.close()
        tool_msg = agent.tool_messages[-1][-1]["content"]
        hint = json.loads(tool_msg)["client_row_compute_hint"]
        self.assertEqual(hint["receipt_index"], 1)
        self.assertEqual(hint["rows_returned"], len(DEVICES))
        self.assertIn("battery", hint["field_names_seen"])

    async def test_bad_receipt_is_a_contract_error_not_a_hub_call(self):
        hub = Hub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {"operation": "count"})]},
            {"content": "No data has been read yet.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("count my batteries", [], hub, 60)
        finally:
            await agent.close()
        self.assertEqual(hub.calls, [])
        rec = reply["tool_calls"][0]
        self.assertFalse(rec["success"])
        self.assertIn("No successful native data read", rec["error"])


if __name__ == "__main__":
    unittest.main()


class ComputeNudge(unittest.IsolatedAsyncioTestCase):
    async def run_script(self, script):
        agent = Scripted(script)
        try:
            reply = await agent.answer("how many devices have a battery?", [], Hub(), 90)
        finally:
            await agent.close()
        return agent, reply

    async def test_inspected_answer_gets_one_compute_chance(self):
        agent, reply = await self.run_script([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "About 3 devices.", "tool_calls": []},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "operation": "count", "receipt_index": 1,
                "where": [{"field": "currentStates.battery", "op": "exists"}]})]},
            {"content": "Exact count from the computation.", "tool_calls": []},
        ])
        self.assertEqual(agent.script, [])
        self.assertTrue(any(c["name"] == "homebrain_compute_receipt" for c in reply["tool_calls"]))

    async def test_nudge_is_sent_only_once(self):
        agent, reply = await self.run_script([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "A draft with no figures.", "tool_calls": []},
            {"content": "A draft with no figures.", "tool_calls": []},
        ])
        self.assertEqual(agent.script, [])
        self.assertIn("draft", reply["answer"])


class FieldMeaningRule(unittest.TestCase):
    def test_prompt_forbids_relabelling_source_fields(self):
        from agent import _SKILL as SYSTEM_PROMPT  # noqa: WPS433
        for phrase in ("never relabel it", "requested quantity is unavailable", "state the mix"):
            self.assertIn(phrase, SYSTEM_PROMPT)

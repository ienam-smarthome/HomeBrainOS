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


class RepeatedReadGuard(unittest.IsolatedAsyncioTestCase):
    async def test_identical_read_is_not_repeated(self):
        hub = Hub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "Done.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("list my devices", [], hub, 60, enable_compute_nudge=False)
        finally:
            await agent.close()
        self.assertEqual(hub.calls, [("hub_list_devices", {})])
        second = reply["tool_calls"][1]
        self.assertFalse(second["success"])
        self.assertIn("already succeeded as receipt 1", second["error"])


class FieldMeaningNote(unittest.TestCase):
    def logs_result(self):
        rows = [{"id": i, "name": f"d{i}", "pct": 1.5, "pctTotal": 0.1, "total": 100 + i,
                 "grandTotal": 5000, "stateSize": 900, "average": 3.0, "count": 5}
                for i in range(12)]
        payload = {"modes": {"devices": {"entries": rows, "count": 12}}}
        return {"content": [{"type": "text", "text": json.dumps(payload)}]}

    def test_runtime_table_fields_are_explained_as_not_memory(self):
        from receipt_compute import field_meaning_note
        note = field_meaning_note("hub_get_logs", self.logs_result())
        self.assertIsNotNone(note)
        self.assertIn("not memory", note["meanings"]["total"])
        self.assertIn("share of that total device runtime", note["meanings"]["pct"])
        self.assertIn("bytes", note["meanings"]["stateSize"])

    def test_other_tools_and_shapes_get_no_note(self):
        from receipt_compute import field_meaning_note
        self.assertIsNone(field_meaning_note("hub_list_devices", self.logs_result()))
        self.assertIsNone(field_meaning_note("hub_get_logs", {"content": []}))


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


class FieldNoteForbidsMemoryColumn(unittest.TestCase):
    def test_note_names_decimal_kb_and_forbids_memory_title(self):
        rows = [{"name": str(i), "pct": 1, "total": 2, "stateSize": 3} for i in range(12)]
        from receipt_compute import field_meaning_note
        use = field_meaning_note("hub_get_logs", {"entries": rows})["use"]
        self.assertIn("do not title a column Memory or RAM", use)
        self.assertIn("client_*_KB_decimal", use)


class FootnotesThroughAgentLoop(unittest.IsolatedAsyncioTestCase):
    async def test_unrun_tool_and_partial_coverage_footnotes_are_appended(self):
        rows = [{"id": str(i), "name": f"d{i}", "stateSize": 100 + i} for i in range(12)]

        class PagedHub(Hub):
            def __init__(self):
                super().__init__()
                self.catalog = [
                    {"name": "hub_list_devices", "inputSchema": {"type": "object", "properties": {}}},
                    {"name": "hub_list_device_events", "inputSchema": {"type": "object", "properties": {}}},
                ]

            async def call(self, name, args):
                self.calls.append((name, args))
                body = {"devices": rows, "count": 12, "total": 181, "hasMore": True, "nextCursor": "12"}
                return {"content": [{"type": "text", "text": json.dumps(body)}]}

        hub = PagedHub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "receipt_index": 1, "operation": "max", "field": "stateSize"})]},
            {"content": "Counts came from hub_list_device_events for each id. Largest is 111.",
             "tool_calls": []},
        ])
        try:
            reply = await agent.answer("which is biggest?", [], hub, 60)
        finally:
            await agent.close()
        answer = reply["answer"]
        self.assertIn("Coverage: figures above come from 12 of 181 rows", answer)
        self.assertIn("Not run in this request: hub_list_device_events", answer)
        self.assertNotIn("hub_list_devices.", answer.split("Not run in this request:")[-1])

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
        self.assertIn("share of that total runtime", note["meanings"]["pct"])
        self.assertIn("bytes", note["meanings"]["stateSize"])

    def test_other_tools_and_shapes_get_no_note(self):
        from receipt_compute import field_meaning_note
        self.assertIsNone(field_meaning_note("hub_list_devices", self.logs_result()))
        self.assertIsNone(field_meaning_note("hub_get_logs", {"content": []}))


class PartialRankingWarningThroughAgentLoop(unittest.IsolatedAsyncioTestCase):
    async def test_compute_over_unsorted_partial_page_tells_model_to_use_sortby(self):
        rows = [{"id": str(i), "name": f"a{i}", "stateSize": 100 - i} for i in range(12)]

        class LogsHub(Hub):
            def __init__(self):
                super().__init__()
                self.catalog = [{"name": "hub_get_logs", "inputSchema": {
                    "type": "object", "properties": {"mode": {}, "limit": {}, "sortBy": {}}}}]

            async def call(self, name, args):
                self.calls.append((name, args))
                body = {"modes": {"apps": {"total": 40, "entries": rows, "nextCursor": "12"}}}
                return {"content": [{"type": "text", "text": json.dumps(body)}]}

        hub = LogsHub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": ["apps"], "limit": 0})]},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "operation": "sort", "receipt_index": 1, "field": "stateSize",
                "rows_path": "content.0.text.modes.apps.entries", "descending": True, "limit": 3})]},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "operation": "sort", "receipt_index": 1, "field": "stateSize",
                "rows_path": "content.0.text.modes.apps.entries", "descending": True, "limit": 3})]},
            {"content": "Done.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("rank the apps", [], hub, 60)
        finally:
            await agent.close()
        held = [m for batch in agent.tool_messages for m in batch if "ranking_computed" in m["content"]]
        first = json.loads(held[0]["content"])
        self.assertFalse(first["ranking_computed"])
        warning = first["client_partial_ranking_warning"]
        self.assertEqual(warning["sort_parameter_offered"], "sortBy")
        self.assertIn("first 12 rows of 40", warning["use"])
        self.assertTrue(reply["tool_calls"][1].get("ranking_held_back"))
        # A second attempt on the same receipt is not held back again (no loop) and keeps the warning.
        second = json.loads(agent.tool_messages[-1][-1]["content"])
        self.assertIn("client_partial_ranking_warning", second)
        self.assertNotIn("ranking_computed", second)
        self.assertFalse(reply["tool_calls"][2].get("ranking_held_back"))


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
            {"content": "A draft: the total is 12 devices.", "tool_calls": []},
            {"content": "A draft: the total is 12 devices.", "tool_calls": []},
        ])
        self.assertEqual(agent.script, [])
        self.assertIn("draft", reply["answer"])

    async def test_plain_list_draft_skips_the_nudge_round(self):
        agent, reply = await self.run_script([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "Front door: closed. Fridge door: closed.", "tool_calls": []},
        ])
        self.assertEqual(agent.script, [])
        self.assertIn("Front door", reply["answer"])


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


class PagingGuardsThroughAgentLoop(unittest.IsolatedAsyncioTestCase):
    def _hub(self, pages):
        class PagedHub(Hub):
            def __init__(self):
                super().__init__()
                self.catalog = [{"name": "hub_get_logs",
                                 "inputSchema": {"type": "object", "properties": {}}}]

            async def call(self, name, args):
                self.calls.append((name, args))
                body = pages[str(args.get("cursor", ""))]
                return {"content": [{"type": "text", "text": json.dumps(body)}]}
        return PagedHub()

    async def test_unissued_cursor_is_not_sent_to_the_hub(self):
        pages = {"": {"devices": [{"id": "1", "stateSize": 5}], "total": 3,
                      "nextCursor": "50"}}
        hub = self._hub(pages)
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": "devices"})]},
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": "devices", "cursor": "99"})]},
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": "devices", "cursor": "50"})]},
            {"content": "done", "tool_calls": []},
        ])
        pages["50"] = {"devices": [{"id": "2", "stateSize": 9}], "total": 3}
        try:
            reply = await agent.answer("page it", [], hub, 60)
        finally:
            await agent.close()
        sent = [args.get("cursor") for _, args in hub.calls]
        self.assertEqual(sent, [None, "50"])
        blocked = [r for r in reply["tool_calls"] if r.get("hub_called") is False]
        self.assertEqual(len(blocked), 1)
        self.assertIn("cursor '99'", blocked[0]["error"] + json.dumps(blocked[0]))

    async def test_skipped_page_and_source_table_are_footnoted(self):
        first = [{"id": str(i), "stateSize": 5 + i} for i in range(12)]
        second = [{"id": str(100 + i), "stateSize": 99 + i} for i in range(12)]
        pages = {
            "": {"devices": first, "total": 24, "nextCursor": "50"},
            "50": {"devices": second, "total": 24},
        }
        hub = self._hub(pages)
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": "devices"})]},
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": "devices", "cursor": "50"})]},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "receipt_index": 1, "operation": "max", "field": "stateSize"})]},
            {"content": "Largest is 16.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("largest?", [], hub, 60)
        finally:
            await agent.close()
        answer = reply["answer"]
        self.assertIn("did not include 1 further page(s) of the same read", answer)
        self.assertIn("Source table: `devices` of hub_get_logs (mode devices).", answer)


class CursorContinuationThroughAgentLoop(unittest.IsolatedAsyncioTestCase):
    """Reproduces the alpha.170 live capture: the hub rejects a cursor unless the
    read repeats the issuing call (single-value mode, same page size)."""

    def _hub(self):
        first = [{"id": str(i), "stateSize": 10 + i} for i in range(12)]
        second = [{"id": str(100 + i), "stateSize": 500 + i} for i in range(12)]

        class StrictHub(Hub):
            def __init__(self):
                super().__init__()
                self.catalog = [{"name": "hub_get_logs",
                                 "inputSchema": {"type": "object", "properties": {}}}]

            async def call(self, name, args):
                self.calls.append((name, dict(args)))
                if "cursor" in args and isinstance(args.get("mode"), list):
                    body = {"success": False, "isError": True,
                            "error": "cursor pages one mode"}
                    return {"isError": True, "content": [{"type": "text", "text": json.dumps(body)}]}
                if args.get("cursor") == "50" and args.get("limit") != 0:
                    body = {"success": False, "isError": True,
                            "error": "cursor 50 is out of range (size=20)"}
                    return {"isError": True, "content": [{"type": "text", "text": json.dumps(body)}]}
                if args.get("cursor") == "50":
                    body = {"entries": second, "total": 24, "count": 12}
                else:
                    body = {"entries": first, "total": 24, "count": 12, "nextCursor": "50"}
                return {"content": [{"type": "text", "text": json.dumps(body)}]}
        return StrictHub()

    async def test_cursor_read_reuses_issuing_arguments(self):
        hub = self._hub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": ["devices"], "limit": 0})]},
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": "devices", "cursor": "50"})]},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "receipt_indexes": [1, 2], "operation": "max", "field": "stateSize"})]},
            {"content": "Largest is 511.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("largest?", [], hub, 60)
        finally:
            await agent.close()
        self.assertEqual(hub.calls[1][1], {"mode": "devices", "limit": 0, "cursor": "50"})
        second = reply["tool_calls"][1]
        self.assertTrue(second["success"])
        self.assertIn("receipt 1", second["client_cursor_note"])
        self.assertNotIn("Coverage: figures above come from 12 of 24", reply["answer"])
        self.assertNotIn("Paging:", reply["answer"])

    async def test_empty_cursor_is_dropped_and_failed_paging_is_footnoted(self):
        hub = self._hub()
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": ["devices"], "limit": 0})]},
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": ["devices"], "cursor": ""})]},
            {"content": "", "tool_calls": [call("hub_get_logs", {"mode": "devices", "cursor": "7"})]},
            {"content": "", "tool_calls": [call("homebrain_compute_receipt", {
                "receipt_index": 1, "operation": "max", "field": "stateSize"})]},
            {"content": "Largest is 21.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("largest?", [], hub, 60)
        finally:
            await agent.close()
        self.assertNotIn("cursor", hub.calls[1][1])
        self.assertEqual(len(hub.calls), 2)  # cursor '7' was never issued: refused locally
        self.assertIn("Paging: 1 attempt(s) to read further pages of hub_get_logs", reply["answer"])
        self.assertIn("(mode devices)", reply["answer"])


class NudgeAcknowledgementKeepsDraft(unittest.IsolatedAsyncioTestCase):
    async def test_acknowledgement_does_not_replace_the_draft(self):
        agent = Scripted([
            {"content": "", "tool_calls": [call("hub_list_devices", {})]},
            {"content": "The top device is Alpha with 12 MB in total.", "tool_calls": []},
            {"content": "My draft stands as written; no change needed.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("what is biggest?", [], Hub(), 90)
        finally:
            await agent.close()
        self.assertIn("Alpha", reply["answer"])
        self.assertNotIn("stands as written", reply["answer"])

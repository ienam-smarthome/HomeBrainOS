"""Regression tests for generic app configuration source coverage.

Only fictional app pages are used. No tool or device is ever modified.
These assertions test evidence delivery, not whether a cloud model obeys.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from config_evidence import config_source_map
from agent import Agent, _SKILL


def config_reply(page: dict, **extras) -> dict:
    payload = {
        "success": True,
        "app": {"id": 123, "name": "Fictional Controller"},
        "page": page,
        **extras,
    }
    return {"content": [{"type": "text", "text": json.dumps(payload)}],
            "_meta": {"serverInfo": {"version": "test-only"}}}


class ConfigSourceMapTests(unittest.TestCase):
    def test_root_page_links_are_not_a_complete_configuration(self):
        original = config_reply({
            "name": "mainPage",
            "sections": [{"title": "Options", "inputs": [
                {"name": "active", "type": "bool", "title": "Enabled", "value": "true"},
            ]}],
            "hrefs": [
                {"page": "controllerPageA", "title": "Controller A"},
                {"page": "controllerPageB", "title": "Controller B"},
            ],
        }, settingsNote="Raw settings omitted")
        before = json.dumps(original, sort_keys=True)
        index = config_source_map(original)
        self.assertEqual(index["source_scope"], "one returned current installed-app configuration page")
        self.assertEqual(index["page_name"], "mainPage")
        self.assertEqual(len(index["linked_pages"]), 2)
        self.assertEqual(index["linked_pages"][0]["page"], "controllerPageA")
        self.assertFalse(index["raw_settings_included_in_source"])
        self.assertFalse(index["historical_configuration_proven_by_this_page"])
        self.assertFalse(index["event_specific_callback_or_timer_proven_by_this_page"])
        self.assertIn("one returned configuration page", index["note"])
        self.assertEqual(json.dumps(original, sort_keys=True), before)

    def test_multiple_selected_inputs_and_competing_settings_are_source_only(self):
        source = config_reply({
            "name": "controllerPageA",
            "sections": [
                {"title": "Inputs", "inputs": [
                    {"name": "sources", "title": "Participating probes",
                     "type": "capability.relativeHumidityMeasurement",
                     "value": ["SYN-A", "SYN-B", "SYN-C"],
                     "selected": [
                         {"value": "SYN-A", "label": "Probe A"},
                         {"value": "SYN-B", "label": "Probe B"},
                         {"value": "SYN-C", "label": "Probe C"},
                     ]},
                    {"name": "backupSwitch", "type": "capability.switch",
                     "title": "Backup mode switch", "value": ["SW-8"]},
                ]},
                {"title": "Control", "inputs": [
                    {"name": "threshold", "title": "Setpoint", "type": "number", "value": "71"},
                    {"name": "scheduled", "title": "Enable calendar routine",
                     "type": "bool", "value": "true"},
                    {"name": "manualMinutes", "title": "Manual run minutes",
                     "type": "number", "value": "40"},
                    {"name": "routineMinutes", "title": "Calendar run minutes",
                     "type": "number", "value": "40"},
                    {"name": "irrelevantHtml", "title": "Custom script",
                     "type": "html", "value": "<script>not a config instruction</script>"},
                ]},
            ],
        })
        index = config_source_map(source)
        self.assertEqual(index["page_name"], "controllerPageA")
        group = index["selected_input_groups"][0]
        self.assertEqual([x["value"] for x in group["selected"]],
                         ["SYN-A", "SYN-B", "SYN-C"])
        self.assertEqual(index["selected_input_groups"][1]["selected_values"], ["SW-8"])
        controls = {x["name"]: x["value"] for x in index["returned_scalar_control_values"]}
        self.assertEqual(controls, {
            "threshold": "71",
            "scheduled": "true",
            "manualMinutes": "40",
            "routineMinutes": "40",
        })
        self.assertNotIn("irrelevantHtml", controls)
        self.assertNotIn("verified", json.dumps(controls).lower())
        self.assertFalse(index["event_specific_callback_or_timer_proven_by_this_page"])

    def test_unknown_nonconfig_and_failed_responses_are_unchanged(self):
        self.assertIsNone(config_source_map({"content": [
            {"type": "text", "text": '{"events":[]}'}]}))
        self.assertIsNone(config_source_map({"content": [
            {"type": "text", "text": '{"success":false,"app":{},"page":{}}'}]}))
        self.assertIsNone(config_source_map({"isError": True, "content": [
            {"type": "text", "text": '{"success":true,"app":{},"page":{}}'}]}))
        self.assertIsNone(config_source_map({"content": [
            {"type": "text", "text": "<html>not JSON</html>"}]}))

    def test_bounded_map_and_sensitive_fields_are_not_repeated(self):
        huge = [{"name": "option" + str(i), "title": "Option " + str(i),
                 "type": "number", "value": i} for i in range(75)]
        huge.append({"name": "api_token", "title": "API token", "type": "enum",
                     "value": "never-echo-this"})
        page = {"name": "many", "sections": [{"inputs": huge}],
                "hrefs": [{"page": "p" + str(i), "title": "Page"} for i in range(28)]}
        index = config_source_map(config_reply(page))
        self.assertEqual(index["inputs_on_returned_page"], 76)
        self.assertEqual(len(index["returned_scalar_control_values"]), 64)
        self.assertEqual(index["scalar_control_values_omitted"], 11)
        self.assertEqual(len(index["linked_pages"]), 24)
        self.assertEqual(index["linked_pages_omitted"], 4)
        self.assertNotIn("never-echo-this", json.dumps(index))
        self.assertNotIn("api_token", json.dumps(index))

    def test_model_gets_original_config_plus_coverage_map_with_no_forced_reads(self):
        root = config_reply({
            "name": "mainPage",
            "sections": [],
            "hrefs": [{"page": "subPage", "title": "Conditions"}],
        })
        child = config_reply({
            "name": "subPage",
            "sections": [{"inputs": [
                {"name": "inA", "type": "capability.motionSensor",
                 "title": "Input sensors", "value": ["S1", "S2"]},
                {"name": "delay", "type": "number", "title": "Wait", "value": "30"},
                {"name": "backup", "type": "bool", "title": "Backup enabled",
                 "value": "true"},
            ]}],
        })
        event = {"content": [{"type": "text", "text": json.dumps({
            "events": [{"name": "command-off",
                       "date": "2026-08-01T14:20:31Z",
                       "producedBy": {"name": "Fictional Controller"}}],
            "count": 1,
        })}]}

        class Native:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [
                    {"name": "config_read", "inputSchema": {
                        "type": "object", "properties": {"page": {"type": "string"}}}},
                    {"name": "event_read", "inputSchema": {
                        "type": "object", "properties": {"limit": {"type": "number"}}}},
                ]
            async def call(self, tool, args):
                self.calls.append((tool, args.copy()))
                if tool == "event_read":
                    return event
                return child if args.get("page") == "subPage" else root

        class Model(Agent):
            def __init__(self):
                self.prompts = []
            async def round(self, messages, tools, remaining):
                self.prompts.append(messages)
                index = len(self.prompts)
                if index == 1:
                    return {"tool_calls": [{"function": {"name": "config_read",
                                                         "arguments": {}}}]}
                if index == 2:
                    reply = json.loads(messages[-1]["content"])
                    assert reply["content"] == root["content"]
                    assert reply["client_config_source_map"]["linked_pages"][0]["page"] == "subPage"
                    return {"tool_calls": [{"function": {"name": "config_read",
                                                         "arguments": {"page": "subPage"}}}]}
                if index == 3:
                    reply = json.loads(messages[-1]["content"])
                    assert reply["content"] == child["content"]
                    assert reply["client_config_source_map"]["selected_input_groups"][0]["selected_values"] == ["S1", "S2"]
                    assert reply["client_config_source_map"]["event_specific_callback_or_timer_proven_by_this_page"] is False
                    return {"tool_calls": [{"function": {"name": "event_read",
                                                         "arguments": {"limit": 5}}}]}
                return {"content": (
                    "The fictional controller issued the command. The callback "
                    "is not established: both configured paths remain plausible."
                )}

        async def scenario():
            mcp, model = Native(), Model()
            result = await model.answer("Explain the fictional off event", [], mcp, 30)
            self.assertTrue(result["success"])
            self.assertEqual(result["rounds"], 4)
            self.assertEqual(len(result["tool_calls"]), 3)
            self.assertEqual([x[0] for x in mcp.calls],
                             ["config_read", "config_read", "event_read"])
            self.assertIn("both configured paths", result["answer"])
            self.assertIn("Compare competing paths", model.prompts[0][0]["content"])
            self.assertTrue(all(x["success"] for x in result["tool_calls"]))
        asyncio.run(scenario())

    def test_positive_control_remains_confident_and_no_tools_are_called(self):
        class NoTools:
            async def list_tools(self, refresh=False):
                return []
            async def call(self, name, args):
                raise AssertionError("Unexpected read/action")
        class Direct(Agent):
            async def round(self, messages, tools, remaining):
                return {"content": ("The fictional execution trace records the "
                        "trigger callback and command, so that recorded cause is verified.")}
        async def run():
            r = await Direct().answer("Explain the provided imaginary trace", [], NoTools(), 30)
            self.assertEqual(r["rounds"], 1)
            self.assertEqual(r["tool_calls"], [])
            self.assertIn("recorded cause is verified", r["answer"])
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

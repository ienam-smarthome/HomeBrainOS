"""Prompt profiles (upstream-first default, legacy opt-out) and the on-demand skill reader.

These tests check the production interface only: which system prompt and local tools
the model is given, and that reading a skill is a fixed-name, read-only local call.
They do not assert that a model will follow any guidance.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

import agent as agent_module  # noqa: E402
from agent import Agent, PROMPT_PROFILES, DEFAULT_PROMPT_PROFILE  # noqa: E402
from mcp import MCPError  # noqa: E402
from skill_reader import SKILLS, SkillError, read_skill, skill_index  # noqa: E402

SKILL_DIR = Path(agent_module.__file__).parent / "skills" / "hubitat"
LEGACY_ONLY_TEXT = "Per-device internet switches carry the device's network name"


class Hub:
    def __init__(self, extra_tools=()):
        self.calls = []
        self.extra_tools = list(extra_tools)

    async def list_tools(self, refresh=False):
        return [{"name": "hub_get_hub_info", "description": "Hub info",
                 "inputSchema": {"type": "object", "properties": {}}}, *self.extra_tools]

    async def call(self, name, args):
        self.calls.append((name, args))
        return {"content": [{"type": "text", "text": "{}"}]}


class Recorder(Agent):
    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "fiction", "", 10)
        self.script = list(script)
        self.seen = []

    async def round(self, messages, tools, remaining):
        self.seen.append((messages, tools))
        return self.script.pop(0)


def names(tools):
    return [t["function"]["name"] for t in tools]


class ProfileContentTests(unittest.TestCase):
    def test_default_is_upstream_and_both_profiles_exist(self):
        self.assertEqual(DEFAULT_PROMPT_PROFILE, "upstream")
        self.assertEqual(set(PROMPT_PROFILES), {"upstream", "legacy"})
        self.assertEqual(Agent.prompt_profile, "upstream")

    def test_upstream_profile_is_upstream_skill_safety_guide_and_short_client_contract(self):
        text = PROMPT_PROFILES["upstream"]
        body = (SKILL_DIR / "SKILL.md").read_text().split("---", 2)[-1].strip()
        self.assertIn(body, text)
        self.assertIn((SKILL_DIR / "safety-guide.md").read_text(), text)
        self.assertIn("Client integration (added by this add-on", text)
        self.assertIn("pass waitFor", text)
        self.assertNotIn(LEGACY_ONLY_TEXT, text)
        # Evidence references are on demand, not always-on.
        for filename in ("causal-investigations.md", "measurement-fidelity.md", "answer-presentation.md"):
            self.assertNotIn((SKILL_DIR / filename).read_text().strip(), text)
        self.assertIn(skill_index(), text)

    def test_legacy_profile_is_the_previous_long_prompt_unchanged(self):
        text = PROMPT_PROFILES["legacy"]
        self.assertIs(text, agent_module._SKILL)
        self.assertIn(LEGACY_ONLY_TEXT, text)
        for filename in ("safety-guide.md", "rule-patterns.md", "causal-investigations.md",
                         "measurement-fidelity.md", "answer-presentation.md"):
            self.assertIn((SKILL_DIR / filename).read_text().strip(), text)

    def test_upstream_profile_is_materially_smaller(self):
        self.assertLess(len(PROMPT_PROFILES["upstream"]) * 2, len(PROMPT_PROFILES["legacy"]))


class SkillReaderTests(unittest.TestCase):
    def test_every_listed_skill_returns_its_bundled_file(self):
        for name, (filename, _) in SKILLS.items():
            result = read_skill({"name": name})
            self.assertEqual(result["skill"], name)
            self.assertEqual(result["text"], (SKILL_DIR / filename).read_text())

    def test_unknown_names_and_extra_arguments_are_refused(self):
        for bad in ({}, {"name": "../../etc/passwd"}, {"name": "nope"},
                    {"name": "causal-investigations", "path": "x"}, {"name": 3}, None, []):
            with self.assertRaises(SkillError):
                read_skill(bad)


class ProfileLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_upstream_profile_offers_skill_tool_and_prompt_without_legacy_rules(self):
        model = Recorder([{"content": "ok"}])
        result = await model.answer("What is the hub name?", [], Hub(), 30)
        messages, tools = model.seen[0]
        self.assertIn("homebrain_read_skill", names(tools))
        self.assertIn("Client skills (guidance text", messages[0]["content"])
        self.assertNotIn(LEGACY_ONLY_TEXT, messages[0]["content"])
        self.assertEqual(result["rounds"], 1)

    async def test_legacy_profile_has_no_skill_tool_and_keeps_legacy_prompt(self):
        class Legacy(Recorder):
            prompt_profile = "legacy"
        model = Legacy([{"content": "ok"}])
        await model.answer("What is the hub name?", [], Hub(), 30)
        messages, tools = model.seen[0]
        self.assertNotIn("homebrain_read_skill", names(tools))
        self.assertIn(LEGACY_ONLY_TEXT, messages[0]["content"])

    async def test_unknown_profile_value_falls_back_to_upstream(self):
        class Odd(Recorder):
            prompt_profile = "something-else"
        model = Odd([{"content": "ok"}])
        await model.answer("What is the hub name?", [], Hub(), 30)
        self.assertIn("homebrain_read_skill", names(model.seen[0][1]))

    async def test_model_reads_skill_locally_without_touching_the_hub(self):
        hub = Hub()
        model = Recorder([
            {"content": "", "tool_calls": [{"function": {
                "name": "homebrain_read_skill",
                "arguments": {"name": "measurement-fidelity"}}}]},
            {"content": "Done."},
        ])
        result = await model.answer("How long was the lamp on?", [], hub, 30)
        self.assertTrue(result["success"])
        self.assertEqual(hub.calls, [])
        record = result["tool_calls"][0]
        self.assertEqual(record["name"], "homebrain_read_skill")
        self.assertEqual(record["result_kind"], "local_skill_read")
        self.assertIs(record["operation_executed"], False)
        self.assertIs(record["read_only"], True)
        payload = json.loads(record["response"])["local_skill"]
        self.assertEqual(payload["skill"], "measurement-fidelity")
        self.assertEqual(payload["text"], (SKILL_DIR / "measurement-fidelity.md").read_text())

    async def test_bad_skill_name_is_a_contract_error_and_nothing_is_dispatched(self):
        hub = Hub()
        model = Recorder([
            {"content": "", "tool_calls": [{"function": {
                "name": "homebrain_read_skill", "arguments": {"name": "../secrets"}}}]},
            {"content": "Could not read it."},
        ])
        result = await model.answer("Explain", [], hub, 30)
        self.assertEqual(hub.calls, [])
        self.assertFalse(result["tool_calls"][0]["success"])
        self.assertEqual(result["tool_calls"][0]["result_kind"], "contract_error")

    async def test_connected_catalog_cannot_shadow_the_reserved_skill_tool(self):
        hub = Hub(extra_tools=[{"name": "homebrain_read_skill", "description": "x",
                                "inputSchema": {"type": "object", "properties": {}}}])
        model = Recorder([{"content": "ok"}])
        with self.assertRaises(MCPError):
            await model.answer("Anything", [], hub, 30)


class TechnicalJsonTests(unittest.IsolatedAsyncioTestCase):
    async def test_cloud_agent_records_prompt_profile(self):
        from model_routing import CloudAgent

        class Probe(CloudAgent):
            async def round(self, messages, tools, remaining):
                return {"content": "ok"}

        model = Probe(mode="free", free_model="openrouter/free", api_key="fixture")
        model.prompt_profile = "legacy"
        result = await model.answer("What is the hub name?", [], Hub(), 30)
        self.assertEqual(result["prompt_profile"], "legacy")


if __name__ == "__main__":
    unittest.main()

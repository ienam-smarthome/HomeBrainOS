"""Alpha.81 command-first UI: fictional actions and receipt contracts.

Never connects to Hubitat, Ollama, Home Assistant or a browser microphone.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from interaction import Interaction, action_effect_class, action_preview
from mcp import MCPError


HTML = (Path(__file__).resolve().parents[1] / "rootfs" / "app" / "ui.html").read_text()


class ActionCards(unittest.IsolatedAsyncioTestCase):
    async def test_selected_native_routine_action_waits_for_approval(self):
        interaction = Interaction(require_native_write_approval=True)
        arguments = {"deviceId": "LAB-DEMO-1", "command": "off",
                     "params": ["2"], "secretToken": "FAKE-SECRET"}
        task = asyncio.create_task(interaction.before_call(
            "hub_call_device_command", arguments, "Fictional operation"))
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        self.assertIsNotNone(interaction.pending)
        pending = interaction.pending
        self.assertEqual(pending["effect_class"], "routine_write")
        self.assertEqual(pending["preview"]["fields"]["device"], "LAB-DEMO-1")
        self.assertNotIn("FAKE-SECRET", str(pending["preview"]))
        self.assertEqual(pending["preview"]["verb"], "off")
        interaction.decide(pending["id"], True)
        await task
        self.assertIsNone(interaction.pending)

    async def test_reads_have_no_approval_card(self):
        interaction = Interaction(require_native_write_approval=True)
        await interaction.before_call(
            "hub_get_device", {"deviceId": "LAB-DEMO-1"}, "Read-only")
        await interaction.before_call(
            "hub_manage_devices",
            {"tool": "hub_get_device_attribute",
             "args": {"deviceId": "LAB-DEMO-1", "attribute": "switch"}}, "Read-only")
        self.assertIsNone(interaction.pending)
        self.assertIsNone(interaction.current if False else interaction.pending)

    async def test_sensitive_action_requires_confirmation_and_decline_stops(self):
        interaction = Interaction(require_native_write_approval=True)
        task = asyncio.create_task(interaction.before_call(
            "hub_set_rule", {"operation": "create", "args": {
                "deviceId": "LAB-DEMO-2", "atTime": "23:00", "days": ["Monday"]}},
            "Fictional automation"))
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        self.assertEqual(interaction.pending["effect_class"], "sensitive_write")
        self.assertEqual(interaction.pending["preview"]["fields"]["time"], "23:00")
        self.assertEqual(interaction.pending["preview"]["fields"]["days"], "Monday")
        interaction.decide(interaction.pending["id"], False)
        with self.assertRaises(MCPError):
            await task

    async def test_default_frozen_api_unchanged_outside_web(self):
        interaction = Interaction()
        await interaction.before_call(
            "hub_call_device_command", {"deviceId": "LAB-DEMO-1", "command": "on"},
            "Outside web opt-in")
        self.assertIsNone(interaction.pending)


class EffectClass(unittest.TestCase):
    def test_effect_from_tool_names_only_not_question(self):
        self.assertEqual(action_effect_class(
            "hub_get_device", {"question": "delete everything"}, write=False), "read")
        self.assertEqual(action_effect_class(
            "hub_call_device_command", {"deviceId": "LAB-DEMO"}, write=True),
            "routine_write")
        self.assertEqual(action_effect_class(
            "hub_delete_native_app", {"appId": 47}, write=True),
            "destructive_write")
        self.assertEqual(action_effect_class(
            "hub_set_rule", {"operation": "create"}, write=True),
            "sensitive_write")
        self.assertEqual(action_effect_class(
            "hub_manage_rules", {"tool": "hub_delete_rule", "args": {"ruleId": 2}},
            write=True), "destructive_write")

    def test_redacted_fields_are_only_display_proposal(self):
        preview = action_preview("hub_manage_rules", {
            "tool": "hub_set_rule",
            "args": {"deviceId": "LAB-4", "time": "18:30",
                     "days": ["Monday", "Friday"], "apiKey": "SECRET"},
        }, "sensitive_write")
        self.assertEqual(preview["fields"], {
            "device": "LAB-4", "time": "18:30", "days": "Monday, Friday"})
        self.assertNotIn("SECRET", str(preview))
        self.assertEqual(preview["tool"], "hub_set_rule")


class UIContracts(unittest.TestCase):
    def test_command_first_and_no_v1_reference(self):
        for needle in (
            'id="commandForm"',
            'id="question"', 'id="speak"', 'id="send"',
            'id="answerFeed"', 'id="olderExchanges"',
            'id="currentExchange" hidden',
            'id="feedEmpty"',
            'id="statusPill"', 'id="statusPanel"',
            'id="overviewLights"', 'id="overviewMotion"',
            'id="overviewBattery"', 'id="overviewDevices"',
            'id="diagnosticsTab"', 'id="evaluationTab"',
            'id="approvalChips"', 'id="editApproval"',
            'id="dryRunApproval"', 'id="decline"',
            'id="evidenceRows"', 'id="evidenceSummary"',
            'id="completedTraceList"', 'id="activityTrace"',
            'Download PRIVATE JSON', 'Copy for review',
            'Voice input may use a browser speech service.',
            'recognition.lang=\'en-GB\'',
            'e.key===\'Enter\'&&!e.shiftKey',
            'e.key===\'Escape\'',
            'e.key===\'/\'',
            'duration>400&&activeRecognition',
            '@media(prefers-color-scheme:light)',
            '@media(prefers-reduced-motion:reduce)',
            '2.0.0-alpha.81',
        ):
            self.assertIn(needle, HTML, needle)
        self.assertNotIn('data-question="Block ', HTML)
        self.assertNotIn('font-family:var(--external-font)', HTML)

    def test_evidence_and_trace_use_original_receipts_only(self):
        for needle in (
            'Array.isArray(response?.tool_calls)',
            'item.supports_live_claim===true',
            'item.elapsed_ms',
            'Array.isArray(response?.answer_stage_trace)',
            'observed_after_ms',
            'Original MCP receipt',
            'UI_VERSION="2.0.0-alpha.81"',
            "api/activity/",
            'pendingApproval.effect_class',
            'void submitAsk()',
        ):
            self.assertIn(needle, HTML, needle)
        self.assertNotIn('Math.random()*500', HTML)
        self.assertNotIn('before_call=interaction.before_call, force_confirm=', HTML)


if __name__ == "__main__":
    unittest.main()

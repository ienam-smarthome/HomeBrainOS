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

    async def test_verified_name_and_string_timing_visible_during_live_approval(self):
        from native_action_contract import verified_device_details
        import json
        source = {"name": "hub_get_device", "arguments": {"deviceId": "TEST-42"},
                  "success": True, "result_kind": "tool_result", "response": json.dumps({
                      "content": [{"type": "text", "text": json.dumps({
                          "id": "TEST-42", "label": "Fictional Policy Controller",
                          "commands": [{"name": "disconnectInMinutes"}]
                      })}]
                  })}
        interaction = Interaction(require_native_write_approval=True)
        interaction.register_current_native_device_details([source])
        args = {"deviceId": "TEST-42", "command": "disconnectInMinutes",
                "parameters": ["5"]}
        task = asyncio.create_task(interaction.before_call(
            "hub_call_device_command", args, "Fictional delayed internet action"))
        await asyncio.sleep(0)
        preview = interaction.pending["preview"]
        self.assertEqual(preview["fields"]["device"],
                         "Fictional Policy Controller")
        self.assertEqual(preview["fields"]["device_id"], "TEST-42")
        self.assertEqual(preview["fields"]["parameters"], "5")
        self.assertIn("After 5 minutes", preview["fields"]["timing"])
        self.assertIn("device_id", HTML)
        self.assertIn("approvalSummary", HTML)
        interaction.decide(interaction.pending["id"], False)
        with self.assertRaises(MCPError):
            await task

    async def test_numeric_native_parameters_visible_without_write(self):
        interaction = Interaction(require_native_write_approval=True)
        args = {"deviceId": "LAB-DEMO-TIMER", "command": "delayPolicy",
                "parameters": [10]}
        task = asyncio.create_task(interaction.before_call(
            "hub_call_device_command", args, "Fictional future action"))
        await asyncio.sleep(0)
        self.assertIsNotNone(interaction.pending)
        self.assertEqual(
            interaction.pending["preview"]["fields"]["parameters"], "10")
        self.assertEqual(
            interaction.pending["preview"]["verb"], "delayPolicy")
        interaction.decide(interaction.pending["id"], False)
        with self.assertRaises(MCPError):
            await task

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
            'id="healthAttention"', 'id="healthActive"',
            'id="healthRefreshStatus"', 'id="refreshOverview"',
            'id="diagnosticsTab"',
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
            '2.0.0-alpha.186',
        ):
            self.assertIn(needle, HTML, needle)
        # System Health owns the inventory; chat stays a full-width conversation.
        ask = HTML.split('<section id="ask"')[1].split('<section id="systemHealth"')[0]
        health = HTML.split('<section id="systemHealth"')[1].split('<section id="diagnostics"')[0]
        self.assertNotIn('class="overview-aside"', ask)
        self.assertNotIn('id="healthInventoryDetails"', health)
        self.assertNotIn('class="overview-aside"', health)
        self.assertIn('id="healthRuntime"', health)
        self.assertIn('id="refreshOverview"', health)
        self.assertIn('<h2>Latest answer</h2>', ask)
        self.assertIn('grid-row:2', HTML)
        self.assertNotIn('data-question="Block ', HTML)
        self.assertNotIn('font-family:var(--external-font)', HTML)

    def test_long_question_scrollbar_is_thin_accessible_and_does_not_change_ask_flow(self):
        # Native desktop scrollbars can be visually oversized. Keep text
        # editable, scrollable by keyboard, wheel or touch and never conceal
        # content merely to hide the scrollbar.
        for needle in (
            '#ask #question{overflow-y:auto;scrollbar-width:thin',
            '#ask #question::-webkit-scrollbar{width:7px}',
            '#ask #question::-webkit-scrollbar-thumb{',
            '#ask #question::-webkit-scrollbar-button{display:none',
            '@media(forced-colors:active){#ask #question{scrollbar-color:auto}}',
            'max-height:138px',
            "q.style.height=Math.min(138,Math.max(47,q.scrollHeight||47))+'px'",
            "byId('question').addEventListener('input',syncCommandBar)",
            'onsubmit="event.preventDefault();submitAsk()"',
        ):
            self.assertIn(needle, HTML)
        self.assertNotIn('#ask #question{scrollbar-width:none', HTML)
        self.assertNotIn('#ask #question::-webkit-scrollbar{display:none', HTML)

    def test_evidence_and_trace_use_original_receipts_only(self):
        for needle in (
            'Array.isArray(response?.tool_calls)',
            'item.supports_live_claim===true',
            'item.elapsed_ms',
            'Array.isArray(response?.answer_stage_trace)',
            'observed_after_ms',
            'Original MCP receipt',
            'UI_VERSION="2.0.0-alpha.186"',
            "api/activity/",
            'pendingApproval.effect_class',
            'void submitAsk()',
        ):
            self.assertIn(needle, HTML, needle)
        self.assertNotIn('Math.random()*500', HTML)
        self.assertNotIn('before_call=interaction.before_call, force_confirm=', HTML)




class UnqueuedActionChoices(unittest.TestCase):
    def test_finished_text_confirmation_has_safe_selection_not_fake_approval(self):
        for token in (
            'id="unpreparedAction"', 'id="prepareUnqueued"',
            'id="editUnqueued"', 'id="dismissUnqueued"',
            "function prepareUnqueuedAction()",
            "function editUnqueuedAction()",
            "function dismissUnqueuedAction()",
            "response?.action_lifecycle?.status===\'not_prepared\'", "lastUnpreparedQuestion",
            "void submitAsk(true)",
            "proceed|yes|confirm|go ahead|do it",
        ):
            self.assertIn(token, HTML)
        self.assertIn("A real write still requires separate approval.", HTML)
        self.assertIn("prepare_action:prepareAction", HTML)
        self.assertNotIn("preparedActionQuestion(original)", HTML)
        self.assertIn("response?.action_lifecycle?.status==='not_prepared'", HTML)
        self.assertIn("response?.action_selection?.native_write_queued===false", HTML)
        self.assertIn("actionState==='native_write_not_submitted'", HTML)
        self.assertIn("No command sent.", HTML)
        self.assertNotIn("const unprepared=response?.action_selection?.status", HTML)
        self.assertIn("if(activeRequest||!lastUnpreparedQuestion)return;", HTML)
    def test_currently_reported_counts_are_coloured_only_when_state_reports_exist(self):
        self.assertIn(".health-card.has-reported:not(.needs-review) .health-count{color:#4ade80", HTML)
        self.assertIn("else if(count!==null&&count>0&&covered>0)article.classList.add('has-reported')", HTML)

    def test_reported_offline_count_is_red_only_when_above_zero(self):
        self.assertIn("if(key==='reported_offline')article.classList.add('is-offline')", HTML)
        self.assertIn(".health-card.needs-review.is-offline .health-count{color:#ff6b6b}", HTML)

    def test_light_theme_overrides_dark_hardcoded_health_surfaces(self):
        light = HTML[HTML.index("alpha.174: light-theme colour fixes"):]
        for rule in ('.health-banner[data-level="attention"]{background:#fff4dc',
                     '.network-card{background:#fff',
                     '.health-card.needs-review.is-offline .health-count{color:#c62828}',
                     '.health-card.has-reported:not(.needs-review) .health-count{color:#17794a}'):
            self.assertIn(rule, light)

    def test_question_set_card_is_read_only_and_labelled_private(self):
        card = HTML.split('id="questionSetCard"')[1].split('<h3>Troubleshooting</h3>')[0]
        for needle in ("Run question set", "Copy report", "never prepares or sends a write", "private"):
            self.assertIn(needle, card)
        self.assertIn("prepare_action:false", HTML.split("async function runQuestionSet")[1])


if __name__ == "__main__":
    unittest.main()
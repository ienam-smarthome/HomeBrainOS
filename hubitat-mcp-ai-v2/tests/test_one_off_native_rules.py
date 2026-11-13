"""Synthetic one-off Rule Machine safety contracts. No live Hubitat writes."""
import asyncio
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from one_off_rule_policy import (
    requested_temporal_scope, rule_pre_dispatch_issue,
    validate_one_off_native_switch, verified_native_parent,
    decode_mcp_payload, is_native_rule_read, native_rule_inventory_status,
)
from one_off_cleanup import OneOffCleanup, _named_candidate, _attested_read


def mcp_response(value):
    return json.dumps({
        "content": [{"type": "text", "text": json.dumps(value)}]
    })


def source(name, value, args=None):
    return {
        "name": name, "arguments": args or {}, "success": True,
        "response": mcp_response(value),
    }


WHEN = datetime(2026, 11, 13, 18, 50, tzinfo=ZoneInfo("Europe/London"))
NOW = datetime(2026, 11, 13, 18, 40, tzinfo=timezone.utc)
LABEL = "HB one-shot | Block Test (One-time 2026-11-13 18:50)"


def native_document(action_off=True, parent=169, label=LABEL):
    return {
        "operation": "create",
        "args": {
            "parent_id": parent,
            "name": label,
            "changes": [
                {"part": "trigger", "value": {
                    "capability": "Certain Time (and optional date)",
                    "fields": [
                        {"name": "time#", "type": "enum",
                         "value": "A specific time"},
                        {"name": "atTime#", "type": "time",
                         "value": "2026-11-13T18:50:00.000+0000"},
                        {"name": "date#", "type": "bool", "value": True},
                        {"name": "atDate#", "type": "date", "value": "2026-11-13"},
                    ],
                }},
                {"part": "action", "value": {
                    "type": "switchActs", "subtype": "getOnOffSwitch",
                    "fields": [
                        {"name": "onOffSwitch.#", "type": "capability.switch",
                         "value": ["8899"]},
                        {"name": "onOff.#", "type": "bool",
                         "value": not action_off},
                    ]
                }},
            ]
        }
    }


def fresh_sources():
    return [
        source("hub_get_app_config", {
            "app": {
                "id": 169, "appType": {
                    "namespace": "hubitat", "name": "Rule Machine"
                },
            }
        }, {"appId": 169}),
        source("hub_list_rules", {
            "success": True, "rules": [], "total": 0
        }),
        source("hub_get_device", {
            "id": "8899", "label": "Fictional Action Target",
            "commands": [{"name": "on"}, {"name": "off"}],
            "attributes": [{"name": "switch", "value": "on"}],
        }, {"deviceId": "8899"}),
    ]


class OneOffPolicyTests(unittest.TestCase):
    def test_clock_without_recurring_is_one_off(self):
        for question in [
            "block demo screen at 6.50pm", "Switch fictional light off at 18:50",
            "block demo after 2 minutes", "block demo after two minutes",
            "turn off demo once at 6:50 PM",
        ]:
            with self.subTest(question=question):
                self.assertEqual(requested_temporal_scope(question), "one_off")
        self.assertEqual(requested_temporal_scope(
            "Block demo every day at 6:50pm"), "recurring")
        self.assertEqual(requested_temporal_scope(
            "Add a daily automation at 8:00 PM"), "recurring")
        self.assertEqual(requested_temporal_scope(
            "Create a switch rule for my garage"), "unknown")

    def test_one_off_clock_rejects_recurring_visual_rule(self):
        wrong = {"confirm": True, "name": "Daily mistaken",
                 "definition": {
                     "triggers": [{"type": "timeOfDay",
                                   "config": {"timeOfDay": "1850"}}],
                     "thenActions": [{"type": "turnOn",
                                      "config": {"switches": [8899]}}],
                 }}
        for tool, args in [
            ("hub_set_visual_rule", wrong),
            ("hub_manage_rule_machine", {
                "tool": "hub_set_visual_rule", "args": wrong
            }),
        ]:
            issue = rule_pre_dispatch_issue(
                "Block Demo Screen at 6:50pm", tool, args,
                fresh_sources(), now=NOW
            )
            self.assertIn("repeats daily", issue)
        self.assertIsNone(rule_pre_dispatch_issue(
            "Block Demo Screen every day at 6:50pm",
            "hub_set_visual_rule", wrong, [], now=NOW,
        ))

    def test_valid_native_dated_switch_is_not_frozen(self):
        valid = native_document()
        self.assertIsNone(validate_one_off_native_switch(
            valid, fresh_sources(), now=NOW,
        ))
        self.assertIsNone(rule_pre_dispatch_issue(
            "Turn fictional device off at 6:50pm",
            "hub_manage_rule_machine",
            {"tool": "hub_set_rule", "args": valid},
            fresh_sources(), now=NOW,
        ))

    def test_native_duplicate_inventory_is_required_and_bounded(self):
        full = fresh_sources()
        self.assertEqual(native_rule_inventory_status(full, LABEL), "clear")
        self.assertIn("inventory", validate_one_off_native_switch(
            native_document(), full[:1] + full[2:], now=NOW
        ))
        duplicate = [source("hub_list_rules", {
            "success": True, "rules": [{"appId": 5544, "name": LABEL}], "total": 1
        })]
        self.assertIn("already exists", validate_one_off_native_switch(
            native_document(), full[:1] + duplicate + full[2:], now=NOW
        ))
        partial = [source("hub_list_rules", {
            "success": True, "rules": [], "total": 1,
            "hasMore": True, "nextCursor": "50"
        })]
        self.assertIn("incomplete", validate_one_off_native_switch(
            native_document(), full[:1] + partial + full[2:], now=NOW
        ))

    def test_missing_current_native_parent_never_authorizes(self):
        sources = fresh_sources()
        self.assertTrue(verified_native_parent(sources, 169))
        self.assertFalse(verified_native_parent(sources[1:], 169))
        self.assertIn("parent identity",
                      validate_one_off_native_switch(
                          native_document(), sources[1:], now=NOW))
        self.assertIn("parent identity",
                      validate_one_off_native_switch(
                          native_document(parent=168), sources, now=NOW))

    def test_invalid_daily_or_incomplete_native_trigger_fails_closed(self):
        doc = native_document()
        doc["args"]["changes"][0]["value"]["fields"][2]["value"] = False
        self.assertIsNotNone(validate_one_off_native_switch(
            doc, fresh_sources(), now=NOW))
        doc = native_document()
        doc["args"]["changes"][0]["value"]["fields"].pop()
        self.assertIsNotNone(validate_one_off_native_switch(
            doc, fresh_sources(), now=NOW))
        doc = native_document()
        doc["args"]["changes"].append({"part": "action", "value": {}})
        self.assertIn("exactly one", validate_one_off_native_switch(
            doc, fresh_sources(), now=NOW))

    def test_wrong_target_stale_or_missing_device_fails_closed(self):
        doc = native_document()
        doc["args"]["changes"][1]["value"]["fields"][0]["value"] = ["9900"]
        self.assertIn("target", validate_one_off_native_switch(
            doc, fresh_sources(), now=NOW))
        doc = native_document()
        self.assertIn("passed", validate_one_off_native_switch(
            doc, fresh_sources(),
            now=datetime(2026, 11, 13, 19, 0, tzinfo=timezone.utc),
        ))
        doc = native_document()
        doc["args"]["name"] = "Block Test (One-time 2026-11-13 18:50)"
        self.assertIn("HB one-shot", validate_one_off_native_switch(
            doc, fresh_sources(), now=NOW))

    def test_native_rule_machine_read_is_never_a_create(self):
        read = {"tool": "hub_set_rule", "args": {
            "operation": "read", "rule_id": 5544
        }}
        self.assertTrue(is_native_rule_read("hub_manage_rule_machine", read))
        self.assertIsNone(rule_pre_dispatch_issue(
            "Block fictional screen at 6:50pm",
            "hub_manage_rule_machine", read, [], now=NOW
        ))

    def test_mcp_wrappers_are_not_authoritative_when_failed(self):
        self.assertIsNone(decode_mcp_payload(
            {"isError": True, "content": [{"type": "text",
                                          "text": "{\"success\":true}"}]}
        ))


class CleanupMCP:
    def __init__(self, rules=None, *, bad_read=False, fail_delete=False,
                 bad_app=False):
        self.rules = rules if rules is not None else [{
            "appId": "5544", "name": LABEL,
            "type": "Rule-5.1",
        }]
        self.bad_read = bad_read
        self.fail_delete = fail_delete
        self.bad_app = bad_app
        self.calls = []

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_read_rules":
            return {"content": [{"type": "text",
                       "text": json.dumps({"success": True,
                                           "rules": self.rules})}]}
        if name == "hub_get_app_config":
            data = {"app": {
                "id": 5544, "label": LABEL if not self.bad_app
                else "An unrelated rule",
                "appType": {"namespace": "hubitat", "name": "Rule-5.1"},
                "parentAppId": 169,
            }}
            return {"content": [{"type": "text",
                                "text": json.dumps(data)}]}
        if name == "hub_manage_native_rules_and_apps":
            if args["tool"] == "hub_set_rule":
                doc = {
                    "rule_id": 5544,
                    "settings": [
                        {"name": "tCapab1", "type": "enum",
                         "value": "Certain Time (and optional date)"},
                        {"name": "date1", "type": "bool",
                         "value": not self.bad_read},
                        {"name": "atDate1", "type": "date",
                         "value": "2026-11-13"},
                        {"name": "time1", "type": "enum",
                         "value": "A specific time"},
                        {"name": "atTime1", "type": "time",
                         "value": "2026-11-13T18:50:00.000+0000"},
                        {"name": "actType.1", "type": "enum",
                         "value": "switchActs"},
                        {"name": "actSubType.1", "type": "enum",
                         "value": "getOnOffSwitch"},
                        {"name": "onOffSwitch.1", "type": "capability.switch",
                         "value": ["8899"]},
                        {"name": "onOff.1", "type": "bool",
                         "value": False},
                    ],
                }
                return {"content": [{"type": "text",
                                    "text": json.dumps(doc)}]}
            if args["tool"] == "hub_delete_native_app":
                if self.fail_delete:
                    raise TimeoutError("uncertain write")
                return {"content": [{"type": "text",
                                    "text": json.dumps({"success": True})}]}
        raise AssertionError((name, args))

class CleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_dry_run_attests_and_never_deletes(self):
        hub = CleanupMCP()
        cleaner = OneOffCleanup(
            hub, enabled=True, dry_run=True,
            timezone_name="Europe/London"
        )
        result = await cleaner.run_once(now=NOW + timedelta(hours=1))
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["confirmed"], 1)
        self.assertEqual(len(result["would_delete"]), 1)
        self.assertEqual(result["deleted"], [])
        self.assertNotIn("hub_delete_native_app",
                         [a.get("tool") for _, a in hub.calls])

    async def test_expired_rule_requires_native_read_and_exact_owner(self):
        hub = CleanupMCP(bad_read=True)
        cleaner = OneOffCleanup(hub, enabled=True, dry_run=False)
        result = await cleaner.run_once(now=NOW + timedelta(hours=1))
        self.assertEqual(result["confirmed"], 0)
        self.assertEqual(result["deleted"], [])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertFalse(any(a.get("tool") == "hub_delete_native_app"
                             for _, a in hub.calls))
        hub = CleanupMCP(rules=[
            {"appId": "5544", "name": "Manual Rule (One-time 2026-11-13 18:50)"},
            {"appId": "5545", "name": LABEL, "type": "Visual Rule"},
        ])
        cleaner = OneOffCleanup(hub, enabled=True, dry_run=False)
        result = await cleaner.run_once(now=NOW + timedelta(hours=1))
        self.assertEqual(result["eligible"], 0)
        self.assertFalse(any(a.get("tool") == "hub_delete_native_app"
                             for _, a in hub.calls))

    async def test_safe_soft_delete_only_after_two_attested_reads(self):
        hub = CleanupMCP()
        cleaner = OneOffCleanup(hub, enabled=True, dry_run=False)
        result = await cleaner.run_once(now=NOW + timedelta(hours=1))
        self.assertEqual(len(result["deleted"]), 1)
        self.assertEqual([name for name, _ in hub.calls], [
            "hub_read_rules",
            "hub_manage_native_rules_and_apps",
            "hub_get_app_config",
            "hub_manage_native_rules_and_apps",
        ])
        last = hub.calls[-1][1]
        self.assertEqual(last, {
            "tool": "hub_delete_native_app",
            "args": {"appId": "5544", "force": False, "confirm": True},
        })

    async def test_uncertain_delete_persists_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "cleanup.json"
            hub = CleanupMCP(fail_delete=True)
            cleaner = OneOffCleanup(
                hub, enabled=True, dry_run=False, state_file=state
            )
            result = await cleaner.run_once(now=NOW + timedelta(hours=1))
            self.assertEqual(result["deleted"], [])
            self.assertIn("5544", cleaner.uncertain_ids)
            self.assertTrue(state.exists())
            after = CleanupMCP()
            reloaded = OneOffCleanup(
                after, enabled=True, dry_run=False, state_file=state
            )
            result = await reloaded.run_once(now=NOW + timedelta(hours=2))
            self.assertEqual(result["deleted"], [])
            self.assertEqual([name for name, _ in after.calls],
                             ["hub_read_rules"])

    async def test_installed_child_mismatch_never_deletes(self):
        hub = CleanupMCP(bad_app=True)
        cleaner = OneOffCleanup(hub, enabled=True, dry_run=False)
        result = await cleaner.run_once(now=NOW + timedelta(hours=1))
        self.assertEqual(result["confirmed"], 0)
        self.assertEqual(result["deleted"], [])
        self.assertFalse(any(args.get("tool") == "hub_delete_native_app"
                             for _, args in hub.calls))

    async def test_disabled_cleanup_makes_no_mcp_calls(self):
        hub = CleanupMCP()
        cleaner = OneOffCleanup(hub, enabled=False, dry_run=False)
        result = await cleaner.run_once(now=NOW + timedelta(hours=1))
        self.assertEqual(hub.calls, [])
        self.assertIn("disabled", result["errors"][0])

    async def test_future_and_grace_protected(self):
        now = datetime(2026, 11, 13, 18, 55,
                       tzinfo=ZoneInfo("Europe/London"))
        row = {"name": LABEL, "appId": 5544}
        self.assertIsNone(_named_candidate(row, now, 15))
        self.assertIsNotNone(_named_candidate(
            row, now + timedelta(minutes=20), 15
        ))

    async def test_missing_rule_list_fails_closed(self):
        class Missing:
            async def call(self, name, args):
                return {"content": [{"type": "text", "text": "{\"count\":10}"}]}
        cleaner = OneOffCleanup(Missing(), enabled=True, dry_run=False)
        result = await cleaner.run_once(now=NOW + timedelta(hours=1))
        self.assertIn("Native rule list unavailable", result["errors"][0])
        self.assertEqual(result["deleted"], [])


if __name__ == "__main__":
    unittest.main()

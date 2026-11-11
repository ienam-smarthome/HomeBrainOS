"""Alpha.53 named light/motion/battery overview — fictional read-only source.

Tests are offline and use synthetic native MCP replies, no live devices or
Hubitat credentials. Counts are based on returned states, never inferred
completeness, health, lighting type without positive evidence, or freshness.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from home_overview import (
    OverviewUnavailable, read_overview, summarize_device_inventory
)


def inventory_reply(devices, **other):
    return {"content": [{"type": "text", "text": json.dumps({
        "devices": devices, **other,
    })}]}


DEVICES = [
    {"id": "101", "label": "Sample ceiling lamp", "currentStates": {
        "switch": "on", "battery": "17", "motion": "inactive",
    }},
    {"id": "102", "label": "Sample mains socket", "currentStates": {
        "switch": "on", "battery": "20", "motion": "active",
    }},
    {"id": "103", "label": "Sample motion sensor", "currentStates": [
        {"name": "motion", "value": "active"},
        {"name": "battery", "value": "5%"},
    ]},
    {"id": "104", "label": "Sample offline device", "currentStates": None},
    {"id": "105", "label": "Sample switch", "currentStates": {
        "switch": "off", "motion": "inactive", "battery": "stale",
    }},
    {"id": "106", "label": "Other device", "currentStates": {
        "battery": -10, "motion": "unknown",
    }},
]


class OverviewCountingTests(unittest.TestCase):
    def test_counts_require_positive_light_evidence_and_list_names(self):
        result = summarize_device_inventory(inventory_reply(
            DEVICES, unfilteredTotal=6, count=6,
        ))
        self.assertTrue(result["read_only"])
        self.assertTrue(result["inventory_full_coverage_verified"])
        self.assertEqual(result["returned_devices"], 6)
        self.assertEqual(result["source_declared_total"], 6)
        metrics = result["metrics"]
        self.assertEqual(metrics["lights_on"]["count"], 1)
        self.assertEqual(metrics["lights_on"]["devices_with_state"], 1)
        self.assertEqual(metrics["motion_active"]["count"], 2)
        self.assertEqual(metrics["motion_active"]["devices_with_state"], 4)
        self.assertEqual(metrics["battery_low"]["count"], 2)
        self.assertEqual(metrics["battery_low"]["devices_with_state"], 3)
        self.assertEqual(metrics["battery_low"]["threshold_exclusive_pct"], 20)
        self.assertEqual(result["unclassified_on_switches"], 1)
        self.assertEqual(metrics["lights_on"]["members"], [{"name": "Sample ceiling lamp"}])
        self.assertEqual(
            metrics["motion_active"]["members"],
            [{"name": "Sample mains socket"}, {"name": "Sample motion sensor"}],
        )
        self.assertEqual(
            metrics["battery_low"]["members"],
            [{"name": "Sample motion sensor", "battery_pct": 5.0},
             {"name": "Sample ceiling lamp", "battery_pct": 17.0}],
        )
        self.assertEqual(metrics["battery_low"]["members_omitted"], 0)
        self.assertIn("unidentified ON switches", result["notes"][0])
        self.assertNotIn("switch_on", metrics)

    def test_non_lights_and_misleading_label_are_excluded(self):
        fixture = [
            {"label": "Lab Sample Light 2", "currentStates": {"switch": "on"}},
            {"label": "Kitchen lamp", "currentStates": {"switch": "off"}},
            {"label": "Ceiling bulb", "currentStates": {"switch": "on"}},
            {"label": "Aqara Light Sensor", "currentStates": {"switch": "on"}},
            {"label": "Metering socket", "currentStates": {"switch": "on"},
             "capabilities": ["SwitchLevel"]},
            {"label": "Colour controller", "currentStates": {"switch": "on"},
             "capabilities": [{"name": "ColorControl"}]},
            {"label": "Hue Light", "currentStates": {"switch": "on"},
             "type": "Smart Plug"},
            {"label": "Unidentified relay", "currentStates": {"switch": "on"}},
            {"label": "Lab Motion A", "currentStates": {"motion": "active", "battery": 19.5}},
        ]
        result = summarize_device_inventory(inventory_reply(fixture, total=9))
        metrics = result["metrics"]
        self.assertEqual(metrics["lights_on"]["count"], 3)
        self.assertEqual(metrics["lights_on"]["devices_with_state"], 4)
        self.assertEqual([x["name"] for x in metrics["lights_on"]["members"]],
                         ["Ceiling bulb", "Colour controller", "Lab Sample Light 2"])
        self.assertEqual(result["unclassified_on_switches"], 4)
        self.assertEqual(metrics["motion_active"]["members"],
                         [{"name": "Lab Motion A"}])
        self.assertEqual(metrics["battery_low"]["members"],
                         [{"name": "Lab Motion A", "battery_pct": 19.5}])

    def test_bounded_all_active_names_and_values_not_only_five_examples(self):
        devices = [
            {"label": f"Light {i:03}", "currentStates": {"switch": "on"}}
            for i in range(17)
        ]
        devices += [
            {"label": f"Motion {i:03}", "currentStates": {"motion": "active"}}
            for i in range(13)
        ]
        result = summarize_device_inventory(inventory_reply(devices, total=30))
        self.assertEqual(result["metrics"]["lights_on"]["count"], 17)
        self.assertEqual(len(result["metrics"]["lights_on"]["members"]), 17)
        self.assertEqual(len(result["metrics"]["motion_active"]["members"]), 13)
        self.assertEqual(result["metrics"]["lights_on"]["members_omitted"], 0)
        large = [{"label": f"Light {i:03}", "currentStates": {"switch": "on"}}
                 for i in range(251)]
        limited = summarize_device_inventory(inventory_reply(large, total=251))
        self.assertEqual(limited["metrics"]["lights_on"]["count"], 251)
        self.assertEqual(len(limited["metrics"]["lights_on"]["members"]), 250)
        self.assertEqual(limited["metrics"]["lights_on"]["members_omitted"], 1)

    def test_partial_inventory_must_not_be_termed_complete(self):
        result = summarize_device_inventory(inventory_reply(
            DEVICES[:2], unfilteredTotal=210, count=2,
        ))
        self.assertFalse(result["inventory_full_coverage_verified"])
        self.assertEqual(result["source_declared_total"], 210)
        self.assertEqual(result["returned_devices"], 2)

    def test_missing_total_cannot_certify_full_inventory(self):
        result = summarize_device_inventory(inventory_reply(
            DEVICES[:1],
        ))
        self.assertIsNone(result["source_declared_total"])
        self.assertFalse(result["inventory_full_coverage_verified"])

    def test_untrusted_invalid_attribute_values_never_raise_false_alerts(self):
        result = summarize_device_inventory(inventory_reply([
            {"id": "100", "currentStates": {
                "battery": "-1", "motion": "unavailable", "switch": "unknown",
            }},
            {"id": "101", "currentStates": {
                "battery": "NaN", "motion": "", "switch": None,
            }},
            {"id": "102", "currentStates": {
                "battery": False, "motion": "active", "switch": "on",
            }},
        ], unfilteredTotal=3))
        self.assertEqual(result["metrics"]["battery_low"]["count"], 0)
        self.assertEqual(result["metrics"]["battery_low"]["devices_with_state"], 0)
        self.assertEqual(result["metrics"]["motion_active"]["count"], 1)
        self.assertEqual(result["metrics"]["lights_on"]["count"], 0)
        self.assertEqual(result["unclassified_on_switches"], 1)
        self.assertIn("stale", result["notes"][2])

    def test_missing_or_error_inventory_not_interpreted_as_empty_hub(self):
        for bad in (
            {}, {"isError": True, "content": []},
            {"content": [{"type": "text", "text": '{"foo":true}'}]},
            {"content": [{"type": "text", "text": "not JSON"}]},
        ):
            with self.subTest(response=bad), self.assertRaises(OverviewUnavailable):
                summarize_device_inventory(bad)

    def test_source_limit_rejected_without_unbounded_processing(self):
        response = inventory_reply([{} for _ in range(3001)], unfilteredTotal=3001)
        with self.assertRaisesRegex(OverviewUnavailable, "supported overview"):
            summarize_device_inventory(response)


class FakeCatalog:
    def __init__(self, catalog, response):
        self.catalog = catalog
        self.response = response
        self.calls = []
        self.list_count = 0

    async def list_tools(self, refresh=False):
        self.list_count += 1
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, args))
        return self.response


class OverviewMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_flat_read_invokes_only_exact_inventory_method(self):
        fake = FakeCatalog([
            {"name": "hub_list_devices", "inputSchema": {"type": "object"}},
            {"name": "hub_set_switch", "inputSchema": {}},
        ], inventory_reply(DEVICES, unfilteredTotal=6))
        data = await read_overview(fake)
        self.assertEqual(fake.list_count, 1)
        self.assertEqual(fake.calls, [("hub_list_devices", {})])
        self.assertEqual(data["metrics"]["lights_on"]["count"], 1)

    async def test_nested_gateway_uses_only_schema_advertised_read_leaf(self):
        fake = FakeCatalog([{
            "name": "hub_read_devices", "inputSchema": {
                "type": "object", "properties": {
                    "tool": {"type": "string", "enum": [
                        "hub_list_devices", "hub_list_device_events",
                    ]},
                    "args": {"type": "object"},
                },
            },
        }], inventory_reply(DEVICES, unfilteredTotal=6))
        data = await read_overview(fake)
        self.assertEqual(fake.calls, [("hub_read_devices", {
            "tool": "hub_list_devices", "args": {},
        })])
        self.assertEqual(data["metrics"]["motion_active"]["count"], 2)

    async def test_ambiguous_or_write_catalog_never_executed(self):
        for catalog in (
            [{"name": "hub_set_switch", "inputSchema": {}}],
            [{"name": "hub_read_devices", "inputSchema": {
                "type": "object", "properties": {
                    "tool": {"type": "string", "enum": ["hub_set_switch"]},
                    "args": {"type": "object"},
                },
            }}],
            [{"name": "hub_read_devices", "inputSchema": {
                "type": "object", "properties": {
                    "tool": {"type": "string"}, "args": {"type": "object"},
                },
            }}],
        ):
            fake = FakeCatalog(catalog, inventory_reply(DEVICES, unfilteredTotal=6))
            with self.subTest(catalog=catalog), self.assertRaises(OverviewUnavailable):
                await read_overview(fake)
            self.assertEqual(fake.calls, [])


class OverviewHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_origin_header_and_no_model_or_ha_writes(self):
        import app as runtime
        previous = runtime.app.state._state.copy()
        fake = FakeCatalog([{"name": "hub_list_devices"}],
                           inventory_reply(DEVICES, unfilteredTotal=6))
        runtime.app.state.mcp = fake
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=runtime.app),
                base_url="http://test",
            ) as client:
                denied = await client.get("/api/overview")
                self.assertEqual(denied.status_code, 403)
                self.assertEqual(fake.calls, [])
                allowed = await client.get("/api/overview",
                    headers={"X-Homebrain-Request": "1"})
                self.assertEqual(allowed.status_code, 200)
                data = allowed.json()
                self.assertTrue(data["available"])
                self.assertEqual(data["metrics"]["battery_low"]["count"], 2)
                self.assertTrue(data["read_only"])
                self.assertEqual(fake.calls, [("hub_list_devices", {})])
                self.assertNotIn("token", allowed.text.lower())
        finally:
            runtime.app.state._state.clear()
            runtime.app.state._state.update(previous)

    async def test_connection_failure_is_not_reported_as_zero_devices(self):
        import app as runtime
        previous = runtime.app.state._state.copy()
        runtime.app.state.mcp = FakeCatalog([], inventory_reply([], total=0))
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=runtime.app),
                base_url="http://test",
            ) as client:
                result = await client.get("/api/overview",
                    headers={"X-Homebrain-Request": "1"})
                data = result.json()
                self.assertFalse(data["available"])
                self.assertNotIn("metrics", data)
                self.assertIn("unavailable", data["reason"].lower())
        finally:
            runtime.app.state._state.clear()
            runtime.app.state._state.update(previous)


if __name__ == "__main__":
    unittest.main()

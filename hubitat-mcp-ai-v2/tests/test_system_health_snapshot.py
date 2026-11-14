"""Alpha.83: fictional System Health summaries from ONE native inventory response.

No real Hubitat, Home Assistant, cloud models or background polling.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from home_overview import summarize_device_inventory, read_overview


def fixture(devices, **metadata):
    return {"content": [{"type": "text", "text": json.dumps({
        "devices": devices, **metadata,
    })}]}


DEVICES = [
    {"id": "LAB-1", "label": "Demo Front Door", "currentStates": {
        "contact": "open", "battery": "9", "healthStatus": "online"}},
    {"id": "LAB-2", "label": "Demo Utility Sensor", "currentStates": [
        {"name": "water", "value": "wet"},
        {"name": "contact", "value": "closed"},
        {"name": "healthStatus", "value": "online"},
    ]},
    {"id": "LAB-3", "label": "Demo Heating Valve", "currentStates": {
        "thermostatOperatingState": "heating",
        "contact": "unknown", "water": "unknown",
        "healthStatus": "online"}},
    {"id": "LAB-4", "label": "Demo Mesh Device", "currentStates": {
        "healthStatus": "offline", "switch": "on"}},
    {"id": "LAB-5", "label": "Demo Lounge Lamp", "currentStates": {
        "switch": "on", "motion": "active"}},
    {"id": "LAB-6", "label": "Demo No Report", "currentStates": {
        "contact": "ajar", "water": "unknown",
        "thermostatOperatingState": "strange", "healthStatus": "lastseen-old"}},
    {"id": "LAB-7", "label": "Demo Unknown Attribute", "currentStates": None},
]


class SystemHealthSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.response = summarize_device_inventory(
            fixture(DEVICES, total=len(DEVICES))
        )

    def test_all_extra_categories_only_use_supported_returned_values(self):
        metrics = self.response["metrics"]
        expected = {
            "contact_open": (1, 2, ["Demo Front Door"]),
            "water_wet": (1, 1, ["Demo Utility Sensor"]),
            "heating_active": (1, 1, ["Demo Heating Valve"]),
            "reported_offline": (1, 4, ["Demo Mesh Device"]),
            "other_switches_on": (1, 1, ["Demo Mesh Device"]),
            "lights_on": (1, 1, ["Demo Lounge Lamp"]),
            "motion_active": (1, 1, ["Demo Lounge Lamp"]),
            "battery_low": (1, 1, ["Demo Front Door"]),
        }
        for key, (count, covered, names) in expected.items():
            with self.subTest(key=key):
                self.assertEqual(metrics[key]["count"], count)
                self.assertEqual(metrics[key]["devices_with_state"], covered)
                self.assertEqual(
                    [item["name"] for item in metrics[key]["members"]], names
                )

    def test_missing_does_not_mean_healthy(self):
        result = summarize_device_inventory(fixture([
            {"id": "LAB-U", "label": "Demo Unavailable", "currentStates": None},
            {"id": "LAB-X", "label": "Demo Invalid", "currentStates": {
                "contact": "ajar", "water": "moist",
                "healthStatus": "unavailable",
                "thermostatOperatingState": "unknown",
            }},
        ], total=2))
        for key in ("contact_open", "water_wet", "heating_active",
                    "reported_offline", "other_switches_on"):
            self.assertEqual(result["metrics"][key]["count"], 0)
            self.assertEqual(result["metrics"][key]["devices_with_state"], 0)
        self.assertTrue(any("absent reading" in note for note in result["notes"]))

    def test_positive_identification_required_for_lights(self):
        result = summarize_device_inventory(fixture([
            {"id": "LAB-5", "label": "Demo Socket", "currentStates": {"switch": "on"}},
            {"id": "LAB-6", "label": "Demo Light Switch", "currentStates": {"switch": "off"}},
        ], total=2))
        self.assertEqual(result["metrics"]["lights_on"]["count"], 0)
        self.assertEqual(result["metrics"]["other_switches_on"]["count"], 1)
        self.assertEqual(result["unclassified_on_switches"], 1)
        self.assertEqual(result["metrics"]["other_switches_on"]["members"],
                         [{"name": "Demo Socket"}])

    def test_names_are_bounded_and_excess_reported(self):
        huge = [
            {"id": f"LAB-{i}", "label": f"Demo Contact {i:03d}",
             "currentStates": {"contact": "open"}}
            for i in range(301)
        ]
        result = summarize_device_inventory(fixture(huge, total=301))
        contact = result["metrics"]["contact_open"]
        self.assertEqual(contact["count"], 301)
        self.assertEqual(contact["devices_with_state"], 301)
        self.assertEqual(len(contact["members"]), 250)
        self.assertEqual(contact["members_omitted"], 51)


class OneInventoryCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_extra_native_tools_for_new_metrics(self):
        class MCP:
            def __init__(self):
                self.calls = []
                self.catalog_calls = 0

            async def list_tools(self):
                self.catalog_calls += 1
                return [{"name": "hub_list_devices", "inputSchema": {
                    "type": "object", "properties": {}}}]

            async def call(self, name, arguments):
                self.calls.append((name, arguments))
                return fixture(DEVICES, total=len(DEVICES))

        mcp = MCP()
        result = await read_overview(mcp)
        self.assertTrue(result["read_only"])
        self.assertEqual(mcp.catalog_calls, 1)
        self.assertEqual(mcp.calls, [("hub_list_devices", {})])
        self.assertEqual(result["metrics"]["reported_offline"]["count"], 1)
        self.assertEqual(result["metrics"]["water_wet"]["count"], 1)


if __name__ == "__main__":
    unittest.main()

"""Offline native one-time compiler regression, no hub calls or writes.

Fixture is an illustrative *hypothetical native dated read*, not a claim
that an equivalent real Hubitat one-off document has yet been captured.
"""
from __future__ import annotations

import copy
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai" / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

from native_one_time_rule_compiler import compile_native_one_time_switch  # noqa: E402
from test_native_rule_document_preflight_0_18_362 import (  # noqa: E402
    NATIVE_GUIDE, SCHEMA, PARENT,
)

TZ = ZoneInfo("Europe/London")
NOW = datetime(2026, 11, 2, 17, 0, tzinfo=TZ)
WHEN = NOW + timedelta(minutes=15)
NAME = "Block Sample Switch (One-time 2026-11-02 17:15)"

DOCUMENT = {
    "rule_id": 123,
    "validation": {"structuralIssues": [], "uiChecked": False},
    "nativeHealth": {"available": True, "broken": False, "stopped": False},
    "actions": [{"id": "1", "value": {"method": "getOnOffSwitch"}}],
    "triggers": {"1": "When time is 6:30 PM on Nov 1"},
    "conditions": {}, "expressions": {},
    "settings": [
        {"name": "origLabel", "type": "text",
         "value": "Block Sample Switch (One-time 2026-11-01 18:30)"},
        {"name": "tCapab1", "type": "enum",
         "value": "Certain Time (and optional date)"},
        {"name": "time1", "type": "enum", "value": "A specific time"},
        {"name": "atTime1", "type": "time",
         "value": "2026-11-01T18:30:00"},
        {"name": "actType.1", "type": "enum", "value": "switchActs"},
        {"name": "actSubType.1", "type": "enum", "value": "getOnOffSwitch"},
        {"name": "onOff.1", "type": "bool", "value": "false"},
        {"name": "onOffSwitch.1", "type": "capability.switch",
         "multiple": True, "device_ids": ["22"]},
    ],
}


def draft(**kwargs):
    fields = dict(guide=NATIVE_GUIDE, schema_reply=SCHEMA, parent=PARENT,
                  reference_document=DOCUMENT, name=NAME, device_id=34,
                  command="off", scheduled_at=WHEN, hub_now=NOW)
    fields.update(kwargs)
    return compile_native_one_time_switch(**fields)


def test_dated_existing_template_can_yield_new_native_shape_only_not_authority():
    item = draft()
    assert item.reference_rule_id == 123
    assert item.gaps == ("approved_native_write_and_readback_not_implemented",)
    assert not item.write_ready
    assert item.request == {
        "tool": "hub_set_rule",
        "args": {"operation": "create", "args": {
            "parent_id": 21,
            "name": NAME,
            "changes": [
                {"part": "trigger", "value": {
                    "capability": "Certain Time (and optional date)",
                    "fields": [
                        {"name": "time#", "type": "enum",
                         "value": "A specific time"},
                        {"name": "atTime#", "type": "time",
                         "value": "2026-11-02T17:15:00"},
                    ],
                }},
                {"part": "action", "value": {
                    "type": "switchActs",
                    "subtype": "getOnOffSwitch",
                    "fields": [
                        {"name": "onOffSwitch.#", "type": "capability.switch",
                         "value": ["34"]},
                        {"name": "onOff.#", "type": "bool", "value": False},
                    ],
                }},
            ],
        }},
    }
    assert "confirm" not in item.request["args"]


def test_switch_on_has_opposite_bool_without_changing_trigger_or_identity():
    off = draft()
    on = draft(command="on")
    assert not on.write_ready
    assert on.request["args"]["args"]["changes"][0] == off.request["args"]["args"]["changes"][0]
    assert on.request["args"]["args"]["changes"][1]["value"]["fields"][1]["value"] is True


@pytest.mark.parametrize("sample,reason", [
    ({**DOCUMENT, "rule_id": 0}, "native_one_time_reference_unmatched"),
    ({**DOCUMENT, "validation": {"structuralIssues": ["broken"]}},
     "native_one_time_reference_health_unverified"),
    ({**DOCUMENT, "nativeHealth": {"broken": True}},
     "native_one_time_reference_health_unverified"),
    ({**DOCUMENT, "triggers": {"1": "Every day at 10PM"},
     "settings": [dict(row, value="22:00") if row["name"] == "atTime1" else row
                  for row in DOCUMENT["settings"]]},
     "native_one_time_reference_not_dated"),
    ({**DOCUMENT, "actions": [{"id": "1", "value": {"method": "getLogMsg"}}]},
     "native_one_time_reference_action_unverified"),
    ({**DOCUMENT, "conditions": {"1": "Switch on"}},
     "native_one_time_reference_structure_unverified"),
    ({**DOCUMENT, "settings": [dict(row, value="secret", redacted=True)
                             if row["name"] == "time1" else row
                             for row in DOCUMENT["settings"]]},
     "native_one_time_reference_settings_unverified"),
    ({**DOCUMENT, "settings": [dict(row, value="Other method")
                             if row["name"] == "actSubType.1" else row
                             for row in DOCUMENT["settings"]]},
     "native_one_time_reference_action_unverified"),
    ({**DOCUMENT, "settings": [dict(row, value="2026-11-02T18:30:00")
                             if row["name"] == "atTime1" else row
                             for row in DOCUMENT["settings"]]},
     "native_one_time_reference_label_mismatch"),
    ({**DOCUMENT, "settings": [*DOCUMENT["settings"],
                              {"name": "date1", "type": "date",
                               "value": "2026-11-01"}]},
     "native_one_time_reference_extra_fields"),
    ({**DOCUMENT, "settings": [dict(row, device_ids=[])
                             if row["name"] == "onOffSwitch.1" else row
                             for row in DOCUMENT["settings"]]},
     "native_one_time_reference_action_unverified"),
])
def test_unverified_or_mismatched_native_template_refuses(sample, reason):
    result = draft(reference_document=sample)
    assert result.request is None and reason in result.gaps
    assert not result.write_ready


@pytest.mark.parametrize("change,expected", [
    ({"parent": {"id": 21, "appType": {"namespace": "user", "name": "Rule Machine"}}},
     "native_rule_machine_parent_unverified"),
    ({"parent": {"id": 21, "appType": {"namespace": "hubitat", "name": "Rule-5.1"}}},
     "native_rule_machine_parent_unverified"),
    ({"parent": {"id": "21", "appType": {"namespace": "hubitat", "name": "Rule Machine"}}},
     "native_rule_machine_parent_unverified"),
    ({"schema_reply": {}}, "native_create_schema_unverified"),
    ({"guide": {"content": "legacy name addTrigger addAction hub_set_rule"}},
     "installed_native_contract_unverified"),
    ({"device_id": 0}, "verified_switch_target_and_command_unavailable"),
    ({"command": "blockInternet"}, "verified_switch_target_and_command_unavailable"),
    ({"scheduled_at": NOW}, "fresh_same_hub_timezone_one_time_clock_unverified"),
    ({"scheduled_at": NOW + timedelta(days=8)},
     "fresh_same_hub_timezone_one_time_clock_unverified"),
    ({"scheduled_at": datetime(2026, 11, 2, 17, 15)},
     "fresh_same_hub_timezone_one_time_clock_unverified"),
    ({"name": "Block Sample Switch (One-time 2026-11-03 17:15)"},
     "one_time_name_clock_mismatch"),
    ({"name": "Block Sample Switch"}, "homebrain_one_time_name_unverified"),
])
def test_contract_identity_time_and_naming_fail_closed(change, expected):
    item = draft(**change)
    assert item.request is None and expected in item.gaps
    assert not item.write_ready


def test_does_not_mutate_original_attested_objects_or_time():
    input_data = copy.deepcopy((NATIVE_GUIDE, SCHEMA, PARENT, DOCUMENT))
    result = draft()
    assert not result.write_ready
    assert input_data == (NATIVE_GUIDE, SCHEMA, PARENT, DOCUMENT)


def test_simple_daily_native_rule_does_not_prove_dated_one_time_semantics():
    daily = copy.deepcopy(DOCUMENT)
    daily["settings"] = [
        {**row, "value": "22:00"} if row["name"] == "atTime1" else row
        for row in daily["settings"]
    ]
    result = draft(reference_document=daily)
    assert "native_one_time_reference_not_dated" in result.gaps
    assert result.request is None


@pytest.mark.parametrize("now,when", [
    (datetime(2027, 3, 28, 0, 45, tzinfo=TZ),
     datetime(2027, 3, 28, 1, 30, tzinfo=TZ)),  # missing BST spring hour
    (datetime(2027, 10, 31, 0, 45, tzinfo=TZ),
     datetime(2027, 10, 31, 1, 30, tzinfo=TZ)),  # repeated GMT fall hour
])
def test_dated_native_candidate_rejects_dst_gap_and_fold(now, when):
    name = f"Block Sample Switch (One-time {when:%Y-%m-%d %H:%M})"
    item = draft(hub_now=now, scheduled_at=when, name=name)
    assert item.request is None
    assert "fresh_same_hub_timezone_one_time_clock_unverified" in item.gaps
    assert not item.write_ready

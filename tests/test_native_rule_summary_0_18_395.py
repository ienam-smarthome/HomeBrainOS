"""Rule Machine readable summary: generic, safe, zero additional source reads."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from native_rule_summary import describe_native_rule


def packet(*, dated=False, with_conditional=False):
    settings = [
        {"name": "time1", "type": "enum", "value": "A specific time"},
        {"name": "atTime1", "type": "time", "value": "08:00"},
        {"name": "date1", "type": "bool", "value": dated},
        {"name": "onOff.1", "type": "bool", "value": False},
        {"name": "onOffSwitch.1", "type": "capability.switch",
         "value": "unavailable", "device_ids": ["650"]},
        {"name": "delayAct.3", "type": "enum", "value": "hrs:min:sec"},
        {"name": "delayMin.3", "type": "number", "value": 15},
        {"name": "delaySec.3", "type": "decimal", "value": ""},
        {"name": "onOff.4", "type": "bool", "value": True},
        {"name": "onOffSwitch.4", "type": "capability.switch",
         "value": "unavailable", "device_ids": ["650"]},
        {"name": "secretToken", "type": "text", "value": "NEVER-SHARE"},
    ]
    if dated:
        settings.append({"name": "atDate1", "type": "date", "value": "2026-11-12"})
    return {
        "rule_id": 1234, "settings": settings, "triggers": {"1": "at 8:00 AM"},
        "actions": [
            {"id": "1", "value": {"method": "getOnOffSwitch"}},
            {"id": "3", "value": {"method": "getWaitEvents"}},
            {"id": "4", "value": {"method": "getOnOffSwitch"}},
        ],
        "conditions": {"1": "unverified"} if with_conditional else {},
        "expressions": {},
    }


def methods():
    return [("1", "getOnOffSwitch"), ("3", "getWaitEvents"),
            ("4", "getOnOffSwitch")]


def test_compact_summary_is_generic_and_retains_safety_disclaimers():
    summary = describe_native_rule(packet(), app_id="1234", methods=methods())
    assert "**08:00**" in summary
    assert "no dated one-time trigger verified" in summary
    assert summary.index("Set switch **OFF**") < summary.index("15 minutes configured")
    assert summary.index("15 minutes configured") < summary.index("Set switch **ON**")
    assert summary.count("device ID(s) **650**") == 2
    assert "11 setting(s) returned; 1 settings redacted or unsupported" in summary
    assert "NEVER-SHARE" not in summary and "secretToken" not in summary
    assert "scheduled future job" in summary
    assert "actual device/network effect" in summary
    assert "TV" not in summary and "Internet is blocked" not in summary


def test_dated_one_time_only_with_both_date_flag_and_valid_date():
    item = packet(dated=True)
    yes = describe_native_rule(item, app_id="1234", methods=methods())
    assert "**2026-11-12 at 08:00**" in yes
    assert "no dated one-time trigger verified" not in yes
    item["settings"][3] = {"name": "date1", "type": "bool", "value": ""}
    no = describe_native_rule(item, app_id="1234", methods=methods())
    assert "no dated one-time trigger verified" in no


def test_unverified_switch_fields_and_unknown_method_do_not_invent_effects():
    item = packet()
    item["settings"] = [x for x in item["settings"] if x["name"] != "onOffSwitch.1"]
    result = describe_native_rule(item, app_id="1234", methods=[
        ("1", "getOnOffSwitch"), ("9", "getCustomAction")
    ])
    assert "target or ON/OFF value not verified" in result
    assert "Native action" in result
    assert "Set switch **OFF**" not in result


def test_conditional_graph_never_claims_certain_execution():
    item = packet(with_conditional=True)
    summary = describe_native_rule(item, app_id="1234", methods=methods())
    assert "may be conditional" in summary
    assert "execution path is not verified" in summary


def test_no_leak_on_invalid_trigger_or_wrong_id():
    item = packet()
    item["triggers"]["1"] = "api_key=SECRET"
    assert describe_native_rule(item, app_id="1234", methods=methods()) is None
    item = packet()
    assert describe_native_rule(item, app_id="4321", methods=methods()) is None

"""v0.18.73 partial, typed persisted Rule Machine evidence without writes."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder
from existing_rule_claim_guard import calibrate_existing_rule_verification
from existing_rule_settings_evidence import (
    project_installed_app_settings, prefetch_installed_app_settings,
)
from investigation_intelligence import plan_investigation, assess_investigation


def config(ident="4246", settings=None):
    return {
        "success": True, "app": {"id": int(ident), "type": "Rule-5.1"},
        "settings": settings if settings is not None else {
            "delayMinute.3": "10",
            "cancelAct.3": "true",
            "onOffSwitch.5": {"7805": "PRIVATE_LIGHT_LABEL"},
            "onOff.5": False,
            "tCapab3": "Motion changed",
            "apiToken": "PRIVATE_CREDENTIAL",
            "callbackUrl": "https://private.invalid/SECRET_VALUE",
            "password": "PRIVATE_PASS",
        },
        "page": {"sections": [{"paragraphs": [
            "Sensitive: INTERNAL UI content should not be in receipts."
        ]}]},
    }


def test_indexed_fields_are_bounded_redacted_and_not_compiled_actions():
    result = project_installed_app_settings(config(), "4246")
    assert result["settingsReadable"] is True
    assert result["indexedFields"] == [
        {"key": "delayMinute.3", "minutes": 10},
        {"key": "cancelAct.3", "value": True},
        {"key": "onOffSwitch.5", "deviceIds": ["7805"]},
        {"key": "onOff.5", "value": False},
    ]
    assert result["orderedActionsValidated"] is False
    assert result["semanticFieldsValidated"] is False
    assert result["conditionsValidated"] is False
    for private in ("PRIVATE_", "private.invalid", "INTERNAL UI", "Motion changed"):
        assert private not in str(result)


def test_controller_partial_values_never_turn_into_unsupported_timer_assertions():
    settings = {
        "inactiveAction": "off",
        "inactiveOffDelaySeconds": 30,
        "backupOffDelayMinutes": "5",
        "scheduledOffEnabled": False,
        "manualOverrideEnabled": "false",
        "motionLockoutMinutes": 208,
        "authPassword": "DO_NOT_LEAK",
    }
    result = project_installed_app_settings(config("4019", settings), "4019")
    assert result["indexedFields"] == []
    assert result["controllerFields"] == [
        {"key": "inactiveAction", "value": "off"},
        {"key": "inactiveOffDelaySeconds", "numericValue": 30,
         "unitFromKey": "seconds"},
        {"key": "backupOffDelayMinutes", "numericValue": 5,
         "unitFromKey": "minutes"},
        {"key": "scheduledOffEnabled", "value": False},
        {"key": "manualOverrideEnabled", "value": False},
    ]
    assert "208" not in str(result)
    assert "DO_NOT_LEAK" not in str(result)


@pytest.mark.parametrize("payload,ident", [
    (config("4246"), "4019"),
    ({"success": False, "app": {"id": "4246"},
      "settings": {"delayMinute.3": 10}}, "4246"),
    ({"success": True, "app": None,
      "settings": {"delayMinute.3": 10}}, "4246"),
    ({"success": True, "app": {"id": "4246"}}, "4246"),
])
def test_wrong_id_failed_or_missing_settings_never_promote_facts(payload, ident):
    result = project_installed_app_settings(payload, ident)
    assert result["settingsReadable"] is False
    assert result["indexedFields"] == []
    assert result["controllerFields"] == []


def test_invalid_values_and_excess_settings_fail_closed():
    data = config(settings={
        "delayMinute.3": "not-a-number",
        "cancelAct.3": "unknown",
        "onOff.5": "enable",
        "onOffSwitch.5": {"not-a-device-id": "X"},
        "inactiveOffDelaySeconds": "password",
        "backupOffDelayMinutes": -3,
        "noise": "PRIVATE_SECRET",
    })
    projection = project_installed_app_settings(data, "4246")
    assert projection["settingsReadable"] is True
    assert projection["indexedFields"] == []
    assert projection["controllerFields"] == []
    assert "PRIVATE" not in str(projection)
    too_many = config(settings={f"unrecognised{i}": "SECRET" for i in range(400)})
    result = project_installed_app_settings(too_many, "4246")
    assert result["settingsTruncated"] is True
    assert "SECRET" not in str(result)


class ConfigMCP:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if self.fail:
            return SimpleNamespace(is_error=True, data={"success": False})
        ident = args["args"]["appId"]
        return SimpleNamespace(is_error=False, data=config(ident))


@pytest.mark.asyncio
async def test_prefetch_keeps_safe_receipts_and_no_write_gateway():
    mcp = ConfigMCP()
    rec = EvidenceRecorder()
    token = rec.begin()
    try:
        messages = []
        assert await prefetch_installed_app_settings(
            mcp, rec, app_id="4246", available_names={"hub_read_apps_code"},
            messages=messages,
        )
        assert mcp.calls == [("hub_read_apps_code", {
            "tool": "hub_get_app_config",
            "args": {"appId": "4246", "includeSettings": True},
        })]
        evidence = rec.receipts()
        assert len(evidence) == 1
        assert evidence[0]["evidence_kind"] == "typed_existing_rule_partial_settings"
        assert evidence[0]["mutates"] is False
        assert evidence[0]["effect"] == "read"
        assert evidence[0]["details"]["indexedFields"][0] == {
            "key": "delayMinute.3", "minutes": 10,
        }
        plan = plan_investigation(
            "Verify existing Rule Machine app 4246 persisted actions. "
            "Do not create another rule."
        )
        score = assess_investigation(plan, evidence)
        assert score["evidenceComplete"] is False
        assert {r["key"]: r["state"] for r in score["requirements"]}[
            "stored_logic"
        ] == "checked-unverified"
        answer = calibrate_existing_rule_verification(
            "10-minute delay is proven complete.", evidence, score,
        )
        assert "delayMinute.3=10 minutes" in answer
        assert "onOffSwitch.5 device IDs 7805" in answer
        assert "complete executable action tree" in answer
        assert "proven complete" not in answer
        assert "PRIVATE_" not in answer
        assert "PRIVATE_" not in json.dumps(messages)
    finally:
        rec.reset(token)


@pytest.mark.asyncio
async def test_prefetch_failure_stays_read_only_and_no_typed_value():
    mcp = ConfigMCP(fail=True)
    rec = EvidenceRecorder()
    token = rec.begin()
    try:
        messages = []
        assert not await prefetch_installed_app_settings(
            mcp, rec, app_id="4246", available_names={"hub_read_apps_code"},
            messages=messages,
        )
        assert messages == []
        assert rec.receipts()[0]["success"] is False
        assert rec.receipts()[0]["details"]["settingsReadable"] is False
    finally:
        rec.reset(token)


@pytest.mark.asyncio
async def test_no_gateway_does_not_make_remote_calls():
    mcp = ConfigMCP()
    rec = EvidenceRecorder()
    assert not await prefetch_installed_app_settings(
        mcp, rec, app_id="4246", available_names=set(), messages=[],
    )
    assert mcp.calls == []

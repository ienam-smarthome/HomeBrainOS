"""0.18.211 general-purpose intent boundary: understand directives, not keywords.

Regression suite spans diverse Hubitat goals and mixed-action requests.
No real MCP or model provider is contacted in the HTTP test.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from control_intent_guard import (
    explicitly_read_only_request, independent_affirmative_mutation_clause)
from investigation_v2.intent_boundary import incompatible_v2_control_request
from mcp_agent_orchestrator import _explicit_mutation_request

TOKEN="test-general-v2-intent-token-9876543210"

SCREENSHOT_REQUEST=(
    "Investigate the Google Nest Hub (device 7934) excessive hub-load "
    "warnings around 09:00 on 29 October 2026. Identify the strongest "
    "source-supported explanation using the warning cluster, device events, "
    "command issuers and available performance statistics. If device "
    "configuration or app/driver source inspection fails or returns no "
    "usable code, distinguish a failed inspection from an untried one. "
    "Do not mistake zero commands at one warning timestamp for zero "
    "commands around the warning cluster. Clearly separate plausible "
    "contributors from verified root cause. Read-only investigation; "
    "change nothing."
)

READ_QUESTIONS=[
    SCREENSHOT_REQUEST,
    "Investigate the Google Nest Hub. Read-only; change nothing.",
    "Investigate why Livingroom Light 1 stayed on; change nothing.",
    "Compare bedroom temperature and humidity. Do not set anything.",
    "Explain why the hallway motion controller keeps switching. No changes.",
    "Review all apps and their last execution; create no rules.",
    "Create a report of paused Rule Machine apps, read-only.",
    "Summarise historical commands and create a timeline, read only.",
    "How do I turn the bedroom light off using HomeBrain?",
    "Why did the dimmer turn on and change brightness?",
    "Why did the dimmer turn on, and change brightness?",
    "How many devices are offline across the hub?",
    "Audit energy consumption by appliance; without making changes.",
    "Read-only: determine why the Internet blocker disabled a device.",
    "Verify the thermostat rule and do not enable anything.",
    "Find which app caused the 04:00 fan boost. Read-only.",
    "Check whether Bedroom 3 Mesh came online; change no settings.",
    "Investigate Tasmota MQTT errors; no device changes.",
    "Check scheduled jobs without deleting or updating any rules.",
    "Explain what would happen if I restarted the hub; do not restart it.",
    "Please compare the two dehumidifier meters, no changes.",
    "Why did the app send an OFF command; did the device turn off?",
    "Read-only. Generate a summary about which rules block internet.",
    "Assess hub health; make no changes to any devices.",
    "Review button 1 behaviour and tell me how to configure it.",
]

WRITE_REQUESTS=[
    "Turn on Livingroom Light 2.",
    "Please switch Bedroom 1 Light off.",
    "Can you set Hallway Light 1 to 20%?",
    "Set the fan speed to 50%.",
    "Restart the Hubitat hub.",
    "Block Internet for the TV.",
    "Create an automation to turn Livingroom Light 2 on at dusk.",
    "Delete the rule for Internet access.",
    "Disable app 4080.",
    "Check current TV status. Then turn it off.",
    "Investigate why the light is on; then switch it off.",
    "Read-only diagnosis. Then block the TV.",
    "Read-only verification; please change the device settings.",
    "Read-only inspection; also create a rule to power down the socket.",
    "Review the rule. Instead disable it.",
    "Investigate the fan, then disable its app.",
    "Check the lights, now turn them off.",
    "Why did the motion light turn on? Then turn it off.",
    "Investigate whether the gateway is offline, and reboot it.",
]

@pytest.mark.parametrize("question",READ_QUESTIONS)
def test_general_read_only_tasks_are_not_device_writes(question):
    assert not incompatible_v2_control_request(question),question

@pytest.mark.parametrize("question",WRITE_REQUESTS)
def test_independent_positive_mutations_still_denied_by_read_only_v2(question):
    assert incompatible_v2_control_request(question),question

def test_shared_production_no_write_guard_understands_noop_clauses():
    for prompt in [
        SCREENSHOT_REQUEST,
        "Read-only, change nothing.",
        "Read-only; turn no devices on.",
        "Read-only, create no automations.",
        "Read-only. Set nothing and disable no apps.",
        "Read only. Create an assessment and leave the hub unchanged.",
    ]:
        assert explicitly_read_only_request(prompt),prompt
        assert not _explicit_mutation_request(prompt),prompt

def test_read_only_does_not_hide_later_independent_write():
    for prompt in [
        "Read-only; then turn on the TV.",
        "Read-only. Also disable the app.",
        "Read-only review. Then restart the hub.",
        "Read-only investigation; change nothing; then create a rule.",
    ]:
        assert independent_affirmative_mutation_clause(prompt),prompt
        assert not explicitly_read_only_request(prompt),prompt

def test_inquiry_command_words_do_not_become_mutation_approval():
    for prompt in [
        "Why did the light switch on and change level?",
        "How can I block TV access without changing any settings?",
        "Can you explain when to restart the Hubitat hub?",
        "Compare what happens before and after an automation turns on a switch.",
    ]:
        assert not incompatible_v2_control_request(prompt),prompt

def _api(monkeypatch,tmp_path):
    options=tmp_path/"v2-intent-options.json"
    options.write_text(json.dumps({
        "investigation_v2_testing_enabled":True,
        "investigation_v2_test_token":TOKEN,
        "morning_health_check_enabled":False,
        "one_time_rule_cleanup_enabled":False,
    }),encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH",str(options))
    sys.modules.pop("app",None)
    return importlib.import_module("app")

def test_exact_screenshot_query_is_admitted_to_native_model_and_no_writes(
        monkeypatch,tmp_path):
    module=_api(monkeypatch,tmp_path)
    calls=[]
    async def fake_native(*,question,chat,mcp,executor,**kw):
        assert question==SCREENSHOT_REQUEST
        calls.append("native_model")
        return {
            "answer_mode":"native_mcp_investigation",
            "answer":{"text":"Verified read-only test response."},
            "report":{"text":"Verified read-only test response."},
            "native_diagnostics":{"reads_executed":0,"successful_reads":0},
            "resolved_devices":[],
            "resolution_method":"model_native_mcp_reads",
            "test_mode":"explicit_read_only",
        }
    async def never_inventory(*a,**kw):
        raise AssertionError("V2 native mode should not prefetch inventory")
    monkeypatch.setattr(module,"run_native_read_agent",fake_native)
    monkeypatch.setattr(module.mcp,"get_audit_devices",never_inventory)
    with TestClient(module.app) as client:
        response=client.post("/api/v2/test",json={
            "question":SCREENSHOT_REQUEST,
            "explicit_opt_in":True,"agent_mode":"native_reads"},
            headers={"X-HomeBrain-V2-Test-Token":TOKEN,
                     "X-HomeBrain-V2-Request":"read-only"})
    assert response.status_code==200,response.text
    assert response.json()["answer_mode"]=="native_mcp_investigation"
    assert calls==["native_model"]

def test_mixed_write_refused_before_model_inventory_or_mcp(monkeypatch,tmp_path):
    module=_api(monkeypatch,tmp_path)
    async def forbidden(*a,**kw):
        raise AssertionError("Admission must refuse explicit writes before tools")
    monkeypatch.setattr(module,"run_native_read_agent",forbidden)
    monkeypatch.setattr(module.mcp,"get_audit_devices",forbidden)
    with TestClient(module.app) as client:
        for question in [
            "Read-only; now turn on the bathroom light.",
            "Investigate the fan, then disable its app.",
            "Create an automation to switch TV off at 9pm.",
        ]:
            response=client.post("/api/v2/test",json={
                "question":question,"explicit_opt_in":True,
                "agent_mode":"native_reads"},
                headers={"X-HomeBrain-V2-Test-Token":TOKEN})
            assert response.status_code==409,(question,response.text)
            assert response.json()["detail"]["code"]=="v2_control_not_supported"

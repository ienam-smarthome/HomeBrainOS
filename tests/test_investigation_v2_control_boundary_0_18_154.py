"""v0.18.154: V2 is read-only even when a question is a direct command.

End-to-end HTTP tests enforce rejection *before* inventory, AI or tool calls.
No live Hubitat, network, device commands, or model provider is accessed.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from mcp_agent_orchestrator import _explicit_mutation_request
from investigation_v2.intent_boundary import incompatible_v2_control_request
from investigation_v2.test_webui import render_v2_test_page


TOKEN = "long-unit-test-secret-0123456789"


def _app(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text(json.dumps({
        "investigation_v2_testing_enabled": True,
        "investigation_v2_test_token": TOKEN,
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False,
    }), encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(options))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


DIRECT_CONTROL = (
    "Turn Livingroom Light 2 on",
    "Please switch Livingroom Light 2 off",
    "Can you turn Livingroom Light 2 on?",
    "Would you please switch Livingroom Light 2 off?",
    "Set Livingroom Light 2 to 50 percent",
    "Turn Livingroom Light 2 on and tell me its current power",
    "Check the status of Livingroom Light 2. Then turn it on.",
    "Create an automation to turn Livingroom Light 2 on at sunset",
)

READ_ONLY = (
    "Why did Livingroom Light 2 turn on?",
    "Investigate why Livingroom Light 2 turned on overnight.",
    "Is Livingroom Light 2 on?",
    "Check whether Livingroom Light 2 is on.",
    "Explain how to turn Livingroom Light 2 on, but do not change anything.",
    "Review commands issued to Livingroom Light 2 without changing anything.",
)


@pytest.mark.parametrize("question", DIRECT_CONTROL)
def test_v2_denies_direct_and_compound_control_without_write_permission(question):
    assert incompatible_v2_control_request(question) is True, question


@pytest.mark.parametrize("question", READ_ONLY)
def test_existing_classifier_keeps_questions_about_commands_read_only(question):
    assert _explicit_mutation_request(question) is False, question
    assert incompatible_v2_control_request(question) is False, question


@pytest.mark.parametrize("question", DIRECT_CONTROL)
def test_v2_rejects_control_before_device_inventory_or_model_calls(
        monkeypatch, tmp_path, question):
    module = _app(monkeypatch, tmp_path)
    attempted = []

    async def forbidden_inventory(*args, **kwargs):
        attempted.append("inventory")
        raise AssertionError("V2 control intent must not fetch inventory")

    async def forbidden_semantic(*args, **kwargs):
        attempted.append("semantic")
        raise AssertionError("V2 control intent must not ask AI")

    async def forbidden_evaluate(*args, **kwargs):
        attempted.append("evaluate")
        raise AssertionError("V2 control intent must not issue reads/writes")

    monkeypatch.setattr(module.mcp, "get_audit_devices", forbidden_inventory)
    monkeypatch.setattr(module.mcp, "get_cached_devices", forbidden_inventory)
    monkeypatch.setattr(module, "semantic_plan", forbidden_semantic)
    monkeypatch.setattr(module, "evaluate_v2_with_model", forbidden_evaluate)

    with TestClient(module.app) as client:
        result = client.post(
            "/api/v2/test",
            json={"question": question, "explicit_opt_in": True,
                  "device_ids": ["7828"]},
            headers={"X-HomeBrain-V2-Test-Token": TOKEN,
                     "X-HomeBrain-V2-Request": "read-only"},
        )
    assert result.status_code == 409, result.text
    detail = result.json()["detail"]
    assert detail["code"] == "v2_control_not_supported"
    assert "No Hubitat command was sent" in detail["message"]
    assert "main Ask/Chat interface" in detail["message"]
    assert attempted == []


def test_v2_control_guard_follows_authentication_not_pre_auth_leak(
        monkeypatch, tmp_path):
    module = _app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        result = client.post(
            "/api/v2/test",
            json={"question": "Turn Livingroom Light 2 on",
                  "explicit_opt_in": True},
            headers={"X-HomeBrain-V2-Test-Token": "wrong-token"},
        )
    assert result.status_code == 403
    assert "v2_control_not_supported" not in result.text


def test_v2_test_page_labels_control_boundary_and_handles_incompatible_action():
    page = render_v2_test_page()
    assert "main HomeBrain Ask interface" in page
    assert "This V2 panel tests" in page
    assert "response.status===409&&data?.detail?.code==='v2_control_not_supported'" in page
    assert "No command was sent" in page
    # No direct forwarding of V2 requests into production write endpoint.
    assert "fetch(authUrl('api/chat')" not in page

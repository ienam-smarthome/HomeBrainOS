"""Read-only API contract: native V2 bypasses all device-first inventory gates."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
TOKEN = "native-read-test-token-123456789"


def test_native_v2_api_uses_tool_agent_without_inventory_preflight(monkeypatch, tmp_path):
    config = tmp_path / "options.json"
    config.write_text(json.dumps({
        "investigation_v2_testing_enabled": True,
        "investigation_v2_test_token": TOKEN,
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False,
    }))
    monkeypatch.setenv("CONFIG_PATH", str(config))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    seen = []
    async def fake_agent(*, question, chat, mcp, executor, **kwargs):
        seen.append(question)
        assert executor is module.agent.executor
        return {
            "answer_mode": "native_mcp_investigation",
            "answer": {"text": "Source-backed hub audit",
                       "displayed_record_ids": [], "omitted_material_record_ids": [],
                       "validation_issues": [], "root_cause_verified": False,
                       "human_review_required": False},
            "report": {"text": "Source-backed hub audit",
                       "technical_answer_retained": True},
            "native_diagnostics": {"reads_executed": 2, "successful_reads": 2},
            "resolved_devices": [], "resolution_method": "model_native_mcp_reads",
            "test_mode": "explicit_read_only",
        }
    async def never_inventory(*args, **kwargs):
        raise AssertionError("Native READ agent must not prefetch device inventory")
    monkeypatch.setattr(module, "run_native_read_agent", fake_agent)
    monkeypatch.setattr(module.mcp, "get_audit_devices", never_inventory)
    with TestClient(module.app) as client:
        response = client.post(
            "/api/v2/test",
            json={"question": "check hub logs for any issues",
                  "agent_mode": "native_reads", "explicit_opt_in": True},
            headers={"X-HomeBrain-V2-Test-Token": TOKEN,
                     "X-HomeBrain-V2-Request": "read-only"},
        )
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["answer_mode"] == "native_mcp_investigation"
    assert seen == ["check hub logs for any issues"]
    assert value["resolved_devices"] == []


def test_native_mode_requires_same_auth_and_control_boundary(monkeypatch, tmp_path):
    config = tmp_path / "options.json"
    config.write_text(json.dumps({
        "investigation_v2_testing_enabled": True,
        "investigation_v2_test_token": TOKEN,
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False,
    }))
    monkeypatch.setenv("CONFIG_PATH", str(config))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    with TestClient(module.app) as client:
        unsigned = client.post("/api/v2/test", json={
            "question": "check hub logs for any issues",
            "agent_mode": "native_reads", "explicit_opt_in": True})
        assert unsigned.status_code == 403
        blocked = client.post(
            "/api/v2/test",
            json={"question": "turn off Livingroom Light 2",
                  "agent_mode": "native_reads", "explicit_opt_in": True},
            headers={"X-HomeBrain-V2-Test-Token": TOKEN,
                     "X-HomeBrain-V2-Request": "read-only"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["code"] == "v2_control_not_supported"

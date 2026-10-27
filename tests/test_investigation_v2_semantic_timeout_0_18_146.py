"""v0.18.146: semantic timeouts recover read-only verified device evidence.

All tests are synthetic and must never contact an actual Hubitat installation
or incur an external model call.
"""
from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2.evaluate import evaluate_v2_with_model, V2Evaluation
from investigation_v2.evidence import CaseFile
from investigation_v2.read_loop import InvestigationResult
from investigation_v2.synthesis import GroundedAnswer


class FakeMCP:
    def __init__(self):
        self.tools = [MCPTool(
            "hub_read_devices", "Read-only source",
            {"type": "object", "properties": {
                "tool": {"type": "string", "enum": ["hub_get_device"]},
                "args": {"type": "object", "properties": {
                    "deviceId": {"type": "string"},
                }, "required": ["deviceId"], "additionalProperties": False},
            }, "required": ["tool", "args"], "additionalProperties": False},
            annotations={"readOnlyHint": True},
        )]

    async def list_tools(self):
        return self.tools


class FakeExecutor:
    def __init__(self, mcp):
        self.mcp = mcp
        self.calls = []

    async def execute(self, name, args, *, tool, record_evidence):
        assert name == "hub_read_devices"
        assert args == {"tool": "hub_get_device", "args": {"deviceId": "7103"}}
        assert record_evidence is False
        self.calls.append((name, args))
        response = MCPToolResult(
            name, args, raw={}, text="SECRET_NEVER_OUTPUT", is_error=False,
            data={"id": "7103", "attributes": {
                "healthStatus": "offline", "mqttStatus": "connected",
                "brokerPassword": "SECRET_NEVER_OUTPUT",
            }},
        )
        return ToolExecution(
            name=name, arguments=args, effect=ToolEffect.READ,
            success=True, elapsed_ms=1, content="SECRET_NEVER_OUTPUT",
            result=response,
        )


@pytest.mark.asyncio
async def test_timeout_host_only_path_reads_device_and_never_calls_model():
    hub = FakeMCP()
    executor = FakeExecutor(hub)

    async def forbidden_chat(messages, tools):
        raise AssertionError("Semantic fallback must not call the timed-out model")

    result = await evaluate_v2_with_model(
        explicitly_authorised=True,
        question="Investigate why Bedroom 3 Mesh is offline while MQTT is connected",
        chat=forbidden_chat,
        mcp=hub, executor=executor, verified_entity_ids=("7103",),
        bootstrap_device_context=True,
        semantic_unavailable_reason="timeout",
        enable_atomic_claim_validation=True,
        enable_evidence_narrative=True,
    )
    assert len(executor.calls) == 1
    assert result.investigation.stopped_because == "semantic_intent_unavailable"
    assert result.investigation.case.device_snapshots[0]["attributes"] == {
        "healthStatus": "offline", "mqttStatus": "connected"}
    assert "Limited evidence recovery" in result.report
    assert "not a full investigation" in result.report
    assert result.answer.root_cause_verified is False
    assert "semantic_plan_timeout" in result.answer.validation_issues
    assert result.to_dict()["production_answer_used"] is False
    assert "SECRET_NEVER_OUTPUT" not in json.dumps(result.to_dict())


@pytest.mark.asyncio
async def test_fallback_requires_one_independently_verified_device():
    hub=FakeMCP()
    executor=FakeExecutor(hub)
    async def forbidden_chat(*args, **kwargs):
        raise AssertionError("No model call permitted")
    with pytest.raises(ValueError, match="one verified device"):
        await evaluate_v2_with_model(
            explicitly_authorised=True, question="What is wrong?",
            chat=forbidden_chat, mcp=hub, executor=executor,
            verified_entity_ids=("7103", "9999"),
            semantic_unavailable_reason="timeout",
        )
    assert executor.calls == []


def _test_app(monkeypatch, tmp_path):
    config = tmp_path / "options.json"
    config.write_text(json.dumps({
        "investigation_v2_testing_enabled": True,
        "investigation_v2_test_token": "unit-test-secret-0123456789",
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False,
    }), encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(config))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_browser_semantic_timeout_recovery_and_broad_scope_safety(monkeypatch, tmp_path):
    mod = _test_app(monkeypatch, tmp_path)
    async def fake_inventory(*, identity_only=False):
        return ([{"id":"7103", "label":"Bedroom 3 Mesh"},
                 {"id":"7104", "label":"Bedroom 3 PC"},
                 {"id":"5000", "label":"Fridge"}], {"complete": True})

    async def timeout(*args, **kwargs):
        raise asyncio.TimeoutError()

    calls = []
    async def fake_evaluate(**kwargs):
        calls.append(kwargs)
        case = CaseFile(kwargs["question"])
        return V2Evaluation(
            investigation=InvestigationResult(
                case=case, hypotheses=[], rounds=1, executed_reads=0,
                stopped_because="semantic_intent_unavailable",
            ),
            answer=GroundedAnswer(
                text="Read-only partial evidence only.",
                displayed_record_ids=(), omitted_material_record_ids=(),
                validation_issues=("semantic_plan_timeout",),
            ),
            report="Limited evidence recovery: no root cause established.",
        )

    monkeypatch.setattr(mod.mcp, "get_audit_devices", fake_inventory)
    monkeypatch.setattr(mod, "semantic_plan", timeout)
    monkeypatch.setattr(mod, "evaluate_v2_with_model", fake_evaluate)
    headers = {"X-HomeBrain-V2-Test-Token": "unit-test-secret-0123456789",
               "X-HomeBrain-V2-Request": "read-only"}
    body = {"question": "Investigate why Bedroom 3 Mesh is offline",
            "explicit_opt_in": True}
    with TestClient(mod.app) as browser:
        recovered = browser.post("/api/v2/test", json=body, headers=headers)
        broad = browser.post("/api/v2/test",
            json={**body, "question":"Which five devices use the most power?"},
            headers=headers)

    assert recovered.status_code == 200, recovered.text
    data = recovered.json()
    assert data["answer_mode"] == "verified_device_investigation"
    assert data["resolved_devices"][0]["id"] == "7103"
    assert data["semantic_diagnostics"]["model_intent_planning_skipped"] is True
    assert data["semantic_diagnostics"]["target_verified"] is True
    assert data["semantic_diagnostics"]["model_investigation_attempted"] is True
    assert data["semantic_diagnostics"]["inventory_devices"] == 3
    assert calls[0]["semantic_unavailable_reason"] is None
    assert calls[0]["verified_entity_ids"] == ("7103",)
    assert calls[0]["bootstrap_device_context"] is True
    assert broad.status_code == 200
    assert broad.json()["answer_mode"] == "semantic_unavailable"
    assert len(calls) == 1


def test_duplicate_device_names_do_not_bypass_semantic_failure(monkeypatch, tmp_path):
    mod = _test_app(monkeypatch, tmp_path)
    async def fake_inventory(*, identity_only=False):
        return ([{"id": "7103", "label": "Bedroom 3 Mesh"},
                 {"id": "9103", "label": "Bedroom 3 Mesh"}], {"complete": True})
    async def timeout(*args, **kwargs):
        raise asyncio.TimeoutError()
    async def forbidden_evaluate(**kwargs):
        raise AssertionError("Ambiguous name must not lead to a device read")
    monkeypatch.setattr(mod.mcp, "get_audit_devices", fake_inventory)
    monkeypatch.setattr(mod, "semantic_plan", timeout)
    monkeypatch.setattr(mod, "evaluate_v2_with_model", forbidden_evaluate)
    with TestClient(mod.app) as client:
        outcome = client.post("/api/v2/test", json={
            "question": "Investigate Bedroom 3 Mesh going offline",
            "explicit_opt_in": True,
        }, headers={"X-HomeBrain-V2-Test-Token":
                    "unit-test-secret-0123456789"})
    assert outcome.status_code == 200
    assert outcome.json()["answer_mode"] == "semantic_unavailable"
    assert outcome.json()["resolved_devices"] == []

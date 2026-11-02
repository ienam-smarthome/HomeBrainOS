"""Source-complete native document read; no model-selected write authority.

Uses a synthetic subset of a real native rule document structure. No device
names or private values. Neither model tools nor Hubitat are called live.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from native_rule_document_source import (  # noqa: E402
    prefetch_native_rule_document, project_native_document,
)
from investigation_intelligence import assess_investigation, plan_investigation  # noqa: E402
from existing_rule_claim_guard import calibrate_existing_rule_verification  # noqa: E402


DOC = {
    "rule_id": 42,
    "validation": {"structuralIssues": [], "uiChecked": False},
    "nativeHealth": {"available": True, "broken": False,
                     "paused": False, "stopped": False},
    "triggers": {"1": "When time is 10:00 PM"},
    "actions": [{"id": "1", "value": {"quick": True,
                                    "method": "getOnOffSwitch"}}],
    "conditions": {},
    "settings": [
        {"name": "tCapab1", "type": "enum", "value": "Certain Time (and optional date)"},
        {"name": "time1", "type": "enum", "value": "A specific time"},
        {"name": "atTime1", "type": "time", "value": "22:00"},
        {"name": "actType.1", "type": "enum", "value": "switchActs"},
        {"name": "onOff.1", "type": "bool", "value": "false"},
        {"name": "onOffSwitch.1", "type": "capability.switch",
         "value": None, "device_ids": ["12", "13"]},
    ],
}


class FakeMCP:
    def __init__(self, data=DOC, error=False):
        self.calls = []
        self.data = data
        self.error = error

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        assert gateway == "hub_manage_native_rules_and_apps"
        assert args == {"tool": "hub_set_rule", "args": {
            "operation": "read", "rule_id": 42,
        }}
        return MCPToolResult(gateway, args, {}, "", self.data, is_error=self.error)


@pytest.mark.asyncio
async def test_target_scoped_native_document_read_resolves_stored_logic():
    client = FakeMCP()
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        messages = []
        ok = await prefetch_native_rule_document(
            client, evidence, app_id="42",
            available_names={"hub_manage_native_rules_and_apps"},
            messages=messages,
        )
        assert ok
        assert len(client.calls) == 1
        receipt = evidence.receipts()[0]
        assert receipt["evidence_kind"] == "typed_native_rule_document"
        assert receipt["effect"] == "read" and receipt["mutates"] is False
        assert receipt["success"] is True
        assert receipt["sub_tool"] == "hub_set_rule"
        assert receipt["details"]["orderedActions"] == [
            {"id": "1", "method": "getOnOffSwitch"},
        ]
        assert receipt["details"]["settings"][2]["value"] == "22:00"
        assert "22:00" in messages[-1]["content"]
        assert "No parent ID" in messages[-1]["content"]
        plan = plan_investigation(
            "Read-only: verify existing Rule Machine rule ID 42's "
            "complete native configuration, triggers and actions."
        )
        assert plan is not None and plan.domain == "existing_rule_verification"
        coverage = assess_investigation(plan, evidence.receipts())
        requirements = {r["key"]: r["state"] for r in coverage["requirements"]}
        assert requirements["stored_logic"] == "observed"
        assert requirements["health"] == "observed"
        draft = ("Rule 42 has a 22:00 daily time trigger and a stored "
                 "Switch OFF action; parent ID and one-time semantics unknown.")
        final = calibrate_existing_rule_verification(
            draft, evidence.receipts(), coverage, request="Inspect rule 42"
        )
        assert draft in final
        assert "comparison controller" not in final
    finally:
        evidence.reset(token)


@pytest.mark.parametrize("bad", [
    {**DOC, "rule_id": 43},
    {k: v for k, v in DOC.items() if k != "actions"},
    {**DOC, "actions": [{"id": "1", "value": {}}]},
    {**DOC, "triggers": {"1": 10}},
    {**DOC, "actions": [
        {"id": "1", "value": {"method": "off"}},
        {"id": "1", "value": {"method": "on"}},
    ]},
    {**DOC, "settings": [
        {"name": "password", "type": "text", "value": "secret"},
    ]},
    {**DOC, "settings": [{"name": "time1", "type": "time",
                          "value": "my-api-key-123"}]},
    {**DOC, "nextCursor": "pending"},
    {**DOC, "truncated": True},
])
def test_incomplete_wrong_id_or_sensitive_native_docs_never_verify(bad):
    assert project_native_document(bad, "42") is None


@pytest.mark.asyncio
async def test_no_native_read_gateway_means_no_calls_and_no_fake_evidence():
    client = FakeMCP()
    evidence = EvidenceRecorder()
    messages = []
    assert not await prefetch_native_rule_document(
        client, evidence, app_id="42",
        available_names={"hub_read_rules"}, messages=messages,
    )
    assert client.calls == [] and messages == []


@pytest.mark.asyncio
async def test_native_read_failure_remains_unverified_never_retried():
    client = FakeMCP(data={"error": "source unavailable"}, error=True)
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        messages = []
        ok = await prefetch_native_rule_document(
            client, evidence, app_id="42",
            available_names={"hub_manage_native_rules_and_apps"},
            messages=messages,
        )
        assert not ok
        assert len(client.calls) == 1
        receipt = evidence.receipts()[0]
        assert not receipt["success"] and not receipt["supports_live_claim"]
        assert receipt["effect"] == "read" and receipt["mutates"] is False
        assert "settings" not in receipt.get("details", {})
        assert messages == []
    finally:
        evidence.reset(token)


def test_projection_does_not_mutate_native_source_document():
    before = copy.deepcopy(DOC)
    projected = project_native_document(DOC, "42")
    assert DOC == before
    assert projected["nativeEditorChecked"] is False
    assert "parentId" not in projected

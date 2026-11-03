"""Explicit native document read: real-source-shaped and fail-closed tests.

No Hubitat, cloud model, write gateway, or user credentials are accessed.
"""
from __future__ import annotations

from pathlib import Path
import sys
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder
from mcp_client import MCPToolResult
from native_rule_document_source import (
    parse_explicit_native_read, read_explicit_native_rule_document,
)

PROMPT = (
    'Read existing Rule Machine rule 4259. '
    'Call hub_set_rule with operation="read", rule_id=4259, '
    'args={"sections":["actions"]}. Return raw action IDs and value.method.'
)


class FakeMCP:
    def __init__(self, data=None, *, error=False, exception=None):
        self.calls = []
        self.data = data if data is not None else {
            "rule_id": 4259,
            "validation": {"structuralIssues": []},
            "nativeHealth": {"available": True, "broken": False},
            "actions": [
                {"id": "1", "value": {"method": "getDelay", "quick": False}},
                {"id": "2", "value": {"method": "getOnOffSwitch", "quick": True}},
            ],
        }
        self.error = error
        self.exception = exception

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        if self.exception is not None:
            raise self.exception
        return MCPToolResult(gateway, args, {}, "", self.data, is_error=self.error)


def test_parser_requires_explicit_native_read_section_and_single_exact_id():
    assert parse_explicit_native_read(PROMPT) == ("4259", ("actions",))
    assert parse_explicit_native_read(PROMPT.replace("4259", "8621")) == (
        "8621", ("actions",)
    )
    for prompt in [
        "Why did rule 4259 turn a switch off?",
        'Read rule_id=4259 with hub_set_rule, operation="create", sections=["actions"]',
        'Read rule_id=4259 with hub_set_rule, operation="read"',
        'hub_set_rule operation="read" rule_id=4259 sections=["actions","actions"]',
        'hub_set_rule operation="read" rule_id=4259 sections=["actions","secrets"]',
        'hub_set_rule operation="read" rule_id=4259 rule_id=4258 sections=["actions"]',
        'hub_set_rule operation="read" rule_id=4259 sections=[]',
    ]:
        assert parse_explicit_native_read(prompt) is None


@pytest.mark.asyncio
async def test_exact_native_action_read_returns_ordered_methods_not_faux_subtypes():
    source = FakeMCP()
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        text = await read_explicit_native_rule_document(
            source, evidence, prompt=PROMPT,
            available_names={"hub_manage_native_rules_and_apps"},
        )
        assert "id=1; value.method=getDelay" in text
        assert "id=2; value.method=getOnOffSwitch" in text
        assert "Action order and methods" in text
        assert len(source.calls) == 1
        gateway, args = source.calls[0]
        assert gateway == "hub_manage_native_rules_and_apps"
        assert args == {
            "tool": "hub_set_rule",
            "args": {
                "operation": "read", "rule_id": 4259,
                "args": {"sections": ["actions"]},
            },
        }
        receipt = evidence.receipts()[0]
        assert receipt["mutates"] is False
        assert receipt["success"] is True
        assert receipt["details"]["sourceSuccess"] is True
        assert receipt["details"]["projectionVerified"] is True
        assert receipt["details"]["orderedActions"] == [
            {"id": "1", "method": "getDelay"},
            {"id": "2", "method": "getOnOffSwitch"},
        ]
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_native_error_exposed_without_hallucinated_rule_absence():
    source = FakeMCP(
        {"success": False, "error": {
            "code": "NATIVE_READ_REFUSED", "message": "Native sections are unavailable",
        }}, error=True)
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        text = await read_explicit_native_rule_document(
            source, evidence, prompt=PROMPT,
            available_names={"hub_manage_native_rules_and_apps"},
        )
        assert "NATIVE_READ_REFUSED" in text
        assert "Native sections are unavailable" in text
        assert "does not prove the rule is missing" in text
        r = evidence.receipts()[0]
        assert r["success"] is False
        assert r["details"]["sourceSuccess"] is False
        assert r["details"]["errorCode"] == "NATIVE_READ_REFUSED"
        assert len(source.calls) == 1
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_source_succeeded_but_projection_unverified_is_distinct_error():
    source = FakeMCP({"rule_id": 4259, "actions": [
        {"id": "1", "value": {"method": "getDelay"}},
        {"id": "1", "value": {"method": "getOnOffSwitch"}},
    ]})
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        message = await read_explicit_native_rule_document(
            source, evidence, prompt=PROMPT,
            available_names={"hub_manage_rule_machine"},
        )
        assert "native_actions_invalid" in message
        details = evidence.receipts()[0]["details"]
        assert details["sourceSuccess"] is True
        assert details["projectionVerified"] is False
    finally:
        evidence.reset(token)


@pytest.mark.parametrize("data,code", [
    ({"rule_id": 9999, "actions": []}, "target_document_unverified"),
    ({"rule_id": 4259}, "requested_section_missing"),
    ({"rule_id": 4259, "actions": [], "nextCursor": "more"}, "native_section_incomplete"),
    ({"rule_id": 4259, "actions": [{"id": 1, "subtype": "getDelay"}]}, "native_actions_invalid"),
    ({"rule_id": 4259, "actions": [{"id": "1", "value": {}}]}, "native_actions_invalid"),
    ({"rule_id": 4259, "actions": "incorrect"}, "native_actions_invalid"),
])
@pytest.mark.asyncio
async def test_malformed_read_results_do_not_qualify_as_verified(data, code):
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        response = await read_explicit_native_rule_document(
            FakeMCP(data), evidence, prompt=PROMPT,
            available_names={"hub_manage_native_rules_and_apps"},
        )
        assert code in response
        assert evidence.receipts()[0]["success"] is False
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_exception_exposes_safe_failure_type_without_retry():
    source = FakeMCP(exception=TimeoutError("MCP read timeout"))
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        text = await read_explicit_native_rule_document(
            source, evidence, prompt=PROMPT,
            available_names={"hub_manage_native_rules_and_apps"},
        )
        assert "mcp_call_exception" in text
        assert "TimeoutError" in text
        assert len(source.calls) == 1
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_unavailable_gateway_and_nonexplicit_prompt_issue_no_calls():
    source = FakeMCP()
    assert "gateway" in (
        await read_explicit_native_rule_document(
            source, EvidenceRecorder(), prompt=PROMPT, available_names=set()
        )
    )
    assert await read_explicit_native_rule_document(
        source, EvidenceRecorder(),
        prompt="Explain this rule machine configuration",
        available_names={"hub_manage_native_rules_and_apps"},
    ) is None
    assert not source.calls


@pytest.mark.asyncio
async def test_settings_values_redacted_and_only_requested_section_used():
    source = FakeMCP({
        "rule_id": 4259,
        "settings": [
            {"name": "delayMinute.1", "type": "number", "value": 2},
            {"name": "password", "type": "text", "value": "sensitive"},
        ],
    })
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        text = await read_explicit_native_rule_document(
            source, evidence,
            prompt='hub_set_rule operation="read" rule_id=4259 sections=["settings"]',
            available_names={"hub_manage_native_rules_and_apps"},
        )
        assert "delayMinute.1" in text and "value=2" in text
        assert "sensitive" not in text and "password" not in text
        assert source.calls[0][1]["args"]["args"]["sections"] == ["settings"]
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_error_details_hide_embedded_credentials():
    source = FakeMCP({"error": {"code": "FORBIDDEN",
                               "message": "token=very-secret-secret unauthorized"}})
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        text = await read_explicit_native_rule_document(
            source, evidence, prompt=PROMPT,
            available_names={"hub_manage_native_rules_and_apps"},
        )
        assert "FORBIDDEN" in text
        assert "very-secret-secret" not in text
    finally:
        evidence.reset(token)

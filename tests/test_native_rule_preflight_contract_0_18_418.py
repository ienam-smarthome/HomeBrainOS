"""0.18.418: source-attested native parent and date-contract preflight.

Synthetic MCP fixtures only. The source guide contains a deliberately secret
acknowledgement token that must never enter public evidence or final text.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder
from mcp_client import MCPTool, MCPToolResult
from mcp_agent_orchestrator import UnifiedMCPAgent
from native_rule_readiness_source import (
    is_native_rule_readiness_question, _extra_requested_checks,
    _guide_contract_projection, _native_parent_projection,
    native_rule_readiness_coverage, read_native_rule_readiness,
)

QUESTION = (
    "Perform a READ-ONLY native Rule Machine one-time scheduling preflight. "
    "Verify the installed MCP Rule Server version. "
    "Verify that app 169 is the correct native Rule Machine parent using its "
    "app identity and built-in app-type relationship. "
    "Read the native hub_set_rule tool guide. "
    "Determine whether the installed MCP Server supports creating a Rule Machine "
    "rule with a Certain Time (and optional date) trigger. "
    "Identify the documented date format, required typed trigger fields, "
    "parent ID requirements and supported creation operations. "
    "Do not create, modify, execute or delete rules, open editor forms or "
    "change devices. Keep native rule-writing authorisation disabled. "
    "Include Technical JSON."
)

SECRET = "PRIVATE-TOKEN-DO-NOT-PUBLISH"
GUIDE = (
    "I-HAVE-READ-THE-GUIDE-set_rule_reference-a12f109e\n"
    + SECRET + "\n"
    + "hub_set_rule operation=create accepts parent_id for Rule Machine.\n"
    + "Certain Time (and optional date) trigger:\n"
    + "time# type=enum\n"
    + "atTime# type=time\n"
    + "date# type=bool\n"
    + "atDate# type=date yyyy-MM-dd\n"
)

INST = {"apps": [
    {"id": 169, "name": "Rule Machine", "type": "Rule Machine",
     "user": False, "appTypeId": 18, "parentId": None},
    {"id": 777, "name": SECRET, "type": "Rule-5.1", "parentId": 169},
], "count": 2, "totalOnHub": 2}
TYPES = {"apps": [
    {"id": 18, "name": "Rule Machine", "system": True,
     "isBuiltIn": True},
], "count": 1}
SUMMARY = {"success": True, "id": 169, "type": "Rule Machine",
           "name": "Rule Machine", "namespace": "hubitat",
           "appTypeId": 18, "user": False}
CONFIG = {"success": True, "app": {"id": 169, "parentAppId": None},
          "childApps": [{"id": 2020, "name": SECRET}]}


class SourceOnly:
    def __init__(self, *, guide=GUIDE, typ=TYPES, summary=SUMMARY,
                 config=CONFIG, instances=INST):
        self.calls = []
        self.server_info = {"name": "hubitat-mcp-rule-server",
                            "version": "5.1.6"}
        self.guide, self.types = guide, typ
        self.summary, self.config, self.instances = summary, config, instances

    async def list_tools(self):
        return [
            MCPTool("hub_read_apps_code", "read only", {"type": "object"}),
            MCPTool("hub_get_tool_guide", "read only", {"type": "object"}),
        ]

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        assert gateway in {"hub_read_apps_code", "hub_get_tool_guide"}
        if gateway == "hub_get_tool_guide":
            sec = arguments["section"]
            assert sec in {"set_rule_reference", "builtin_app_tools_rules"}
            content = (self.guide if sec == "set_rule_reference" else
                       "I-HAVE-READ-THE-GUIDE-builtin_app_tools_rules-a12f109e")
            data = {"success": True, "content": content}
        else:
            tool = arguments["tool"]
            args = arguments["args"]
            if tool == "hub_list_backups":
                assert args == {"scope": "hub_local"}
                data = {"scope": "hub_local", "hubLocalBackups": [
                    {"createTimeOrig": "2026-11-05T03:02:31+00:00"}
                ]}
            elif tool == "hub_list_apps":
                assert args["scope"] in {"instances", "types"}
                data = (self.instances if args["scope"] == "instances"
                        else self.types)
            elif tool == "hub_get_app_config":
                assert str(args["appId"]) == "169"
                data = (self.summary if args.get("summary") is True
                        else self.config)
            else:
                raise AssertionError("Unexpected source tool: " + tool)
        return MCPToolResult(gateway, arguments, {}, "", data)


class NeverModel:
    async def chat(self, *args, **kwargs):
        raise AssertionError("Preflight must not call an AI model")


def _run(source, question=QUESTION):
    recorder = EvidenceRecorder()
    token = recorder.begin()
    import asyncio
    try:
        message, details = asyncio.run(read_native_rule_readiness(
            source, recorder,
            available_names={"hub_read_apps_code", "hub_get_tool_guide"},
            question=question,
        ))
        evidence = recorder.receipts()
        coverage = native_rule_readiness_coverage(question, evidence)
        return message, details, evidence, coverage
    finally:
        recorder.reset(token)


def test_live_preflight_intent_requires_distinct_parent_and_contract_checks():
    assert is_native_rule_readiness_question(QUESTION)
    assert _extra_requested_checks(QUESTION) == (False, True, False, True, True)


def test_preflight_exact_id_built_in_parent_and_guide_contract_are_source_attested():
    source = SourceOnly()
    message, details, evidence, coverage = _run(source)
    assert details["mcpServerVersion"] == "5.1.6"
    assert details["preflightEvidenceComplete"] is True
    assert details["nativeParentIdentity"] == {
        "appId": "169", "verified": True, "appTypeId": "18",
        "childRowsObserved": 1, "failureCode": None,
    }
    assert details["nativeDatedFieldGuideAttested"] is True
    assert details["nativeCreateContractGuideAttested"] is True
    assert coverage["evidenceComplete"] is True
    assert coverage["readinessForMutation"] is False
    assert "exact built-in type and parent role verified" in message
    assert "guide contract: documented" not in message.lower()  # no authorisation wording
    assert "documented (guide only; runtime untested)" in message
    assert len(source.calls) == 7
    assert [a.get("tool", "guide") for _, a in source.calls] == [
        "hub_list_backups", "guide", "guide", "hub_list_apps",
        "hub_list_apps", "hub_get_app_config", "hub_get_app_config",
    ]
    assert all(row["effect"] == "read" and row["mutates"] is False
               for row in evidence)
    assert all("hub_manage" not in gateway and a.get("tool") not in {
        "hub_set_rule", "hub_set_native_app",
    } for gateway, a in source.calls)
    for output in (message, str(details), str(evidence), str(coverage)):
        assert SECRET not in output
        assert "I-HAVE-READ-THE-GUIDE-" not in output


@pytest.mark.parametrize("broken,expected", [
    (dict(typ={"apps": [{"id": 18, "name": "Rule Machine",
                         "system": False, "isBuiltIn": False}]}),
     "native_type_conflict_or_unverified"),
    (dict(summary={**SUMMARY, "namespace": "community"}),
     "app_summary_identity_conflict"),
    (dict(config={**CONFIG, "app": {"id": 169, "parentAppId": 100}}),
     "parent_role_unverified"),
])
def test_bad_parent_class_or_role_never_certified(broken, expected):
    source = SourceOnly(**broken)
    message, details, evidence, coverage = _run(source)
    assert details["nativeParentIdentity"]["verified"] is False
    assert details["nativeParentIdentity"]["failureCode"] == expected
    assert coverage["evidenceComplete"] is False
    assert coverage["readinessForMutation"] is False
    assert "unverified" in message
    assert all(r["mutates"] is False for r in evidence)


def test_partial_guide_names_cannot_attest_unseen_date_type_or_creator():
    partial = (GUIDE.replace("atDate# type=date yyyy-MM-dd",
                              "atDate# optional input: secret")
               .replace("operation=create", "read-only guide"))
    contract = _guide_contract_projection(partial)
    assert contract["atDateNamed"] is True
    assert contract["atDateTypeDateDeclared"] is False
    assert contract["dateFormatDeclared"] is False
    assert "atdate_input_type_not_declared" in contract["gapCodes"]
    assert contract["createContractDocumented"] is False
    message, details, evidence, coverage = _run(SourceOnly(guide=partial))
    assert "atDate# type=date declared=false" in message
    assert details["nativeDatedFieldGuideAttested"] is False
    assert coverage["evidenceComplete"] is False
    assert SECRET not in str(evidence)


def test_no_exact_parent_id_refuses_identity_instead_of_guessing_169():
    question = QUESTION.replace("app 169", "an installed app")
    source = SourceOnly()
    message, details, _, coverage = _run(source, question)
    assert details["nativeParentIdentity"]["appId"] is None
    assert details["nativeParentIdentity"]["failureCode"] == "explicit_parent_id_required"
    assert len(source.calls) == 3
    assert coverage["evidenceComplete"] is False
    assert "ID not unambiguously supplied" in message


@pytest.mark.asyncio
async def test_native_preflight_router_uses_source_without_model_or_rule_writes():
    mcp = SourceOnly()
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b",
                            ai_client=NeverModel())
    result = await agent.process_user_request_result(
        QUESTION, session_id="native-418-parent-date-contract",
    )
    assert result.request_class == "live-read"
    assert result.investigation_coverage["domain"] == "native_rule_readiness"
    assert result.investigation_coverage["readinessForMutation"] is False
    assert "app 169" in result.message
    assert "MCP Rule Server version" in result.message
    assert len(mcp.calls) == 7
    assert all(row["mutates"] is False for row in result.evidence)
    assert SECRET not in str(result.evidence)
